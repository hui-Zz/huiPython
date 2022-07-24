# -*- coding:utf-8 -*-
import base64
import datetime
# import feedparser
import json
import os
import pymysql
import PyRSS2Gen
import re
import requests
import sys
import time
from configparser import ConfigParser
from curses.ascii import isdigit
from lxml import etree
from threading import Thread

# 单线程，多线程采集方式选择(多线程采集速度快但机器负载短时高)
# thread = 'multi'
thread = 'single'
# 采集数据保存目录,为了安全请修改本程序名字,或移动到其他目录,并修改以下路径,默认与程序同目录
dir = os.path.dirname(os.path.abspath(__file__)) + "/json/"
iniPath = "huiNews.ini"
if(os.path.exists('/home/huinews/huiNews.ini')):
    iniPath = '/home/huinews/huiNews.ini'
config = ConfigParser()
config.read(iniPath)
rssPath = config.get('config', 'rss_path')
userAgent = config.get('hearders', 'User-Agent')
# 【微博热搜】
def parse_weibo(db):
    try:
        url = 'https://s.weibo.com/top/summary?cate=realtimehot'
        weiboCookie = config.get('hearders', 'weibo_cookie')
        hearders = {
            'User-Agent': userAgent,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'max-age=0',
            'cookie': weiboCookie,
            'referer': 'https://passport.weibo.com/'
        }
        hotTxt = requests.get(url, headers=hearders).content.decode()
        newHotTxt = hotTxt.replace('\n', '')
        newHotTxt = newHotTxt.replace(" ", "")
        noTdTxt = re.findall("<tbody>(.*?)</tbody>", newHotTxt)[0]
        arrayTxt = re.findall('ranktop">(.*?)<tdclass="td-03">', noTdTxt)
        # 遍历数据
        for x in range(5):
            ft = arrayTxt[x]
            # rank = arrayTxt[0:x.rfind("</")] #热搜排名
            urlTxt = ft.split('"')  # 热搜链接
            hotName = ft.split(">")  # 热搜名称
            title = re.sub(r'</a', "", hotName[3])
            span = re.sub(r'</span', "", hotName[5])
            label = re.sub(r'\d|\s', "", span)
            if label == '综艺' or label == '剧集' or label == '电影' or label == '音乐':
                continue
            hot = re.sub(r'\D', "", span)
            emojis = re.findall(r"<imgsrc=\"(.+?)\"", ft)
            emoji = emojis[0] if emojis else ''
            contents = re.findall(r"title=\"(.+?)\"", ft)
            content = contents[0] if contents else ''
            # 保存数据
            db_insert('微博', '热搜', str(x + 1), title, 'https://s.weibo.com/' + urlTxt[3], hot, emoji, label, '', content)
        # 查询输出
        rssItems = db_query("微博")
        makeRss("微博热搜", url, "微博热点排行榜", "热搜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))


# 【百度热搜】
def parse_baidu(db):
    try:
        url = 'https://top.baidu.com/board?platform=pc&sa=pcindex_a_right'
        hearders = {'User-Agent': userAgent}
        res = requests.get(url, headers=hearders)
        html = etree.HTML(res.content.decode())
        data = html.xpath('//*[@id="sanRoot"]/main/div[1]/div[1]/div[2]/a[*]/div[2]/div[2]/div/div/text()')
        linkList = html.xpath('//*[@id="sanRoot"]/main/div[1]/div[1]/div[2]/a/@href')
        coverList = html.xpath('//div[@class="active-item_1Em2h"]/img/@src')
        # 遍历数据
        for i, title in enumerate(data):
            if i > 4:
                break
            # 保存数据
            db_insert('百度', '热搜', i, title.strip(), linkList[i], '', coverList[i], '', '', '')
        # 查询输出
        rssItems = db_query("百度")
        makeRss("百度热搜", url, "百度热搜风云榜", "热搜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【知乎热榜】
def parse_zhihu(db):
    try:
        url = 'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true'
        headers = {'user-agent': userAgent}
        allResponse = requests.get(url, headers=headers).text
        jsonDecode = json.loads(allResponse)
        # 遍历数据
        for i in range(3):
            title = jsonDecode["data"][i]["target"]["title"]
            link = 'https://www.zhihu.com/question/' + str(jsonDecode["data"][i]["target"]["id"])
            cover = jsonDecode["data"][i]["children"][0]["thumbnail"]
            content = jsonDecode["data"][i]["target"]["excerpt"]
            hot = jsonDecode["data"][i]["detail_text"]
            # 保存数据
            db_insert('知乎', '', str(i + 1), title, link, hot, cover, '', '', content)
        # 查询输出
        rssItems = db_query("知乎")
        makeRss("知乎热榜", url, "知乎热门排行榜", "", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【B站热榜】
def parse_bilibili(db):
    try:
        url = 'https://www.bilibili.com/v/popular/rank/all'
        hearders = {'User-Agent': userAgent}
        res = requests.get(url, headers=hearders)
        response = etree.HTML(res.content.decode())
        rank_lists = response.xpath('//ul[@class="rank-list"]/li')
        # 读取屏蔽关键词
        blackTitle = config.get('black', 'title')
        blackAuthor = config.get('black', 'author')
        blackKeyword = config.get('black', 'keyword')
        blackGame = config.get('black', 'game')
        blackTitleList = blackTitle.split(',')
        blackAuthorList = blackAuthor.split(',')
        blackKeywordList = blackKeyword.split(',')
        blackGameList = blackGame.split(',')
        for rank_list in rank_lists:
            rank_num = rank_list.xpath('div/div/i/span/text()')
            if int(rank_num[0]) > 80:
                break
            title = rank_list.xpath('div/div[@class="info"]/a[@class="title"]/text()')
            link = rank_list.xpath('div/div[@class="info"]/a/@href')
            author = rank_list.xpath('div/div[@class="info"]/div[@class="detail"]/a/span/text()')
            hot = rank_list.xpath('div/div[@class="info"]/div[@class="detail"]/div/span[1]/text()')
            if author in blackAuthorList:
                continue
            if any(s in title for s in blackTitleList):
                continue
            bv = link[0].split('/video/')[-1]
            content = '<iframe src="https://player.bilibili.com/player.html?bvid=' + bv + \
                '&high_quality=1" width="650" height="477" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>'
            # 保存数据
            db_insert('B站', '', rank_num[0], title[0], 'https:' + link[0], hot[0].strip(), '', '', author[0].strip(), content)
        # 获取视频封面
        sql = "SELECT * FROM huinews \
            WHERE TO_DAYS( news_time ) = TO_DAYS(NOW()) \
            AND cover IS NULL AND source = %s" % ("'B站'")
        try:
            # 执行SQL语句
            cursor.execute(sql)
            # 获取所有记录列表
            results = cursor.fetchall()
            rssItems = []
            for row in results:
                title = row[4]
                link = row[5]
                time.sleep(1)
                res = requests.get(link, headers=hearders)
                response = etree.HTML(res.content.decode())
                keywords = response.xpath('/html/head/meta[@name="keywords"]/@content')
                keyword = keywords[0].replace(title + ",", "")
                keyword = keyword.replace(",哔哩哔哩,Bilibili,B站,弹幕", "")
                keywordList = keyword.split(',')
                hui = 1
                if any(s in keyword for s in blackKeywordList):
                    hui = 0
                if '游戏' in keyword:
                    if any(s in keyword for s in blackGameList):
                        hui = 0
                description = response.xpath('/html/head/meta[@name="description"]/@content')
                imageUrl = response.xpath('/html/head/meta[@itemprop="image"]/@content')
                try:
                    update_re = "UPDATE huinews SET cover = '%s', label = '%s', hui = '%d', content=CONCAT(content,'%s') \
                                 WHERE link = '%s'" % (imageUrl[0], keyword, hui, description[0], link)
                    cursor.execute(update_re)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(str(e))
        except Exception as e:
            print("查询B站无封面视频失败！" + str(e))
        # 查询输出
        rssItems = db_query("B站")
        makeRss("B站热榜", url, "B站热门排行榜", "", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【IT之家】
def parse_ithome(db):
    try:
        # 屏蔽词
        blackIT = config.get('black', 'it')
        blackITList = blackIT.split(',')
        # [获取小米资讯]
        url = 'https://m.ithome.com/search/%E5%B0%8F%E7%B1%B3.htm'
        hearders = {'User-Agent': userAgent}
        res = requests.get(url, headers=hearders)
        response = etree.HTML(res.content.decode())
        rank_lists = response.xpath('//div[@class="placeholder one-img-plc"]')
        for i, rank_list in enumerate(rank_lists):
            if i > 10:
                break
            title = rank_list.xpath('a/div[@class="plc-con"]/p[@class="plc-title"]/text()')
            link = rank_list.xpath('a/@href')
            cover = rank_list.xpath('a/div[@class="plc-image"]/img/@data-original')
            # 保存数据
            db_insert('IT之家', '', str(i + 1), title[0], link[0], '', cover[0], '小米', '', '')
        # [获取热榜]
        url = 'https://m.ithome.com/rankm'
        hearders = {'User-Agent': userAgent}
        res = requests.get(url, headers=hearders)
        response = etree.HTML(res.content.decode())
        rank_lists = response.xpath('//div[@class="placeholder one-img-plc"]')
        for i, rank_list in enumerate(rank_lists):
            if i > 10:
                break
            title = rank_list.xpath('a/div[@class="plc-con"]/p[@class="plc-title"]/text()')
            if any(s in title[0] for s in blackITList):
                continue
            link = rank_list.xpath('a/@href')
            cover = rank_list.xpath('a/div[@class="plc-image"]/img/@data-original')
            # 保存数据
            db_insert('IT之家', '', str(i + 1), title[0], link[0], '', cover[0], '', '', '')
        # 查询输出
        rssItems = db_query("IT之家")
        makeRss("IT之家热榜", url, "IT之家热榜", "", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【今日热榜-榜中榜】
def parse_tophub(db):
    try:
        url = 'https://tophub.today/hot'
        tophubCookie = config.get('hearders', 'tophub_cookie')
        hearders = {'cookie': tophubCookie, 'User-Agent': userAgent}
        res = requests.get(url, headers=hearders)
        response = etree.HTML(res.content.decode())
        rank_lists = response.xpath('//div[@id="hotrank"]/div/div[@class="rank-section"][2]/ul/li[@class="child-item"]')
        for i, rank_list in enumerate(rank_lists):
            title = rank_list.xpath('div[@class="center-item"]/div/div/p[@class="medium-txt"]/a/text()')
            link = rank_list.xpath('div[@class="center-item"]/div/div/p[@class="medium-txt"]/a/@href')
            sourceStr = rank_list.xpath('div[@class="center-item"]/div/div/p[@class="small-txt"]/text()')
            sourceList = sourceStr[0].split(" ‧ ")
            # 保存数据
            db_insert(sourceList[0], '', str(i + 1), title[0], link[0], sourceList[1], '', '榜中榜', '', '')
        # 查询输出
        rssItems = db_query("虎扑社区")
        makeRss("虎扑社区", url, "虎扑社区", "", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# ---------------------------------------------------------------------------------------------------------------------------------------------------

def db_query(name):
    # 查询数据
    sql = "SELECT * FROM huinews \
        WHERE TO_DAYS( news_time ) = TO_DAYS(NOW()) \
        AND hui = 1 AND source = %s" % ("'" + name + "'")
    try:
        # 执行SQL语句
        cursor.execute(sql)
        # 获取所有记录列表
        results = cursor.fetchall()
        rssItems = []
        for row in results:
            source = row[1]
            rank = row[3]
            titleStr = row[4] + '🔝' if rank <= 1 else row[4]
            hot = ' ' + str(row[6]) if row[6] else ''
            times = ' x' + str(row[7])
            img = ' <img src="' + str(row[8]) + '" referrerpolicy="no-referrer"> ' if row[8] else ''
            label = ' 『' + str(row[9]) + '』' if row[9] else ''
            content = ' ' + str(row[11]) if row[11] else ''

            rssItem = PyRSS2Gen.RSSItem(
                title=titleStr if rank > 3 else titleStr + '🔥',
                link=row[5],
                description=str(rank) + times + label + hot + content + img,
                author = row[10],
                categories = row[2],
                pubDate=row[12]
            )
            rssItems.append(rssItem)
        return rssItems
    except Exception as e:
        print("查询"+ name +"数据失败！" + str(e))

def db_insert(source,categories,rank,title,link,hot,cover,label,author,content):
    try:
        result = []
        result.append((source,categories,rank,title,link,hot,cover,label,author,content))
        # print(result)
        inesrt_re = "insert ignore into huinews (source,categories,rank,title,link,hot,cover,label,author,content) \
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on duplicate key update times = times + 1"
        cursor = db.cursor()
        cursor.executemany(inesrt_re, result)
        db.commit()
    except Exception as e:
        db.rollback()
        print("插入"+ source +"数据失败！" + str(e))

# 打开数据库连接
def db_connect():
    host = config.get('mysql', 'host')
    port = config.getint('mysql', 'port')
    user = config.get('mysql', 'user')
    password = config.get('mysql', 'password')
    database = config.get('mysql', 'database')
    db = pymysql.connect(host=host,
                         port=port,
                         user=user,
                         password=password,
                         database=database)
    return db

def makeRss(title, url, description, categories, rssItems):
    rss = PyRSS2Gen.RSS2(
        title=title,
        link=url,
        description=description,
        categories=categories,
        lastBuildDate=datetime.datetime.now(),
        items=rssItems)
    rss.write_xml(open(rssPath + title + '_Rss.xml', "w", encoding='utf-8'), encoding='utf-8')
    pass

# 字符替换加密(默认为大小写反转),修改此处顺序和添加数字替换可实现不同密码加密(并同时修改get/index.php内密码)
def multiple_replace(text):
    dic = {"a": "A", "b": "B", "c": "C", "d": "D", "e": "E", "f": "F", "g": "G", "h": "H", "i": "I", "j": "J", "k": "K", "l": "L", "m": "M", "n": "N", "o": "O", "p": "P", "q": "Q", "r": "R", "s": "S", "t": "T", "u": "U", "v": "V", "w": "W", "x": "X", "y": "Y", "z": "Z",
           "A": "a", "B": "b", "C": "c", "D": "d", "E": "e", "F": "f", "G": "g", "H": "h", "I": "i", "J": "j", "K": "k", "L": "l", "M": "m", "N": "n", "O": "o", "P": "p", "Q": "q", "R": "r", "S": "s", "T": "t", "U": "u", "V": "v", "W": "w", "X": "x", "Y": "y", "Z": "z"}
    pattern = "|".join(map(re.escape, list(dic.keys())))
    return re.sub(pattern, lambda m: dic[m.group()], text)

def single_run(db):
    # 单线程运行
    print("单线程采集开始", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    t1 = time.time()
    parse_weibo(db)
    parse_baidu(db)
    parse_zhihu(db)
    parse_bilibili(db)
    parse_ithome(db)
    parse_tophub(db)
    print("单线程采集完成", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    print("耗时:", time.time() - t1)

def multi_run(db):
    # 多线程抓取
    print("多线程采集开始", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    t1 = time.time()
    threads = []
    ts1 = Thread(target=parse_weibo, args=(db,))
    ts2 = Thread(target=parse_baidu, args=(db,))
    ts3 = Thread(target=parse_zhihu, args=(db,))
    threads.append(ts1)
    threads.append(ts2)
    threads.append(ts3)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("多线程采集完成", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    print("耗时:", time.time() - t1)

if __name__ == "__main__":
    db = db_connect()
    # 使用cursor()方法获取操作游标
    cursor = db.cursor()

    if thread == 'single':
        # while True:
        single_run(db)
    if thread == 'multi':
        # while True:
        multi_run(db)

    # 关闭数据库连接
    db.close()
