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


# 【微博热搜】
def parse_weibo(db):
    try:
        url = 'https://s.weibo.com/top/summary?cate=realtimehot'
        hearders = {
            'User-Agent': '',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'max-age=0',
            'cookie': '',
            'referer': 'https://passport.weibo.com/'
        }
        hotTxt = requests.get(url, headers=hearders).content.decode()
        newHotTxt = hotTxt.replace('\n', '')
        newHotTxt = newHotTxt.replace(" ", "")
        noTdTxt = re.findall("<tbody>(.*?)</tbody>", newHotTxt)[0]
        arrayTxt = re.findall('ranktop">(.*?)<tdclass="td-03">', noTdTxt)
        # 保存数据
        for x in range(5):
            try:
                ft = arrayTxt[x]
                # rank = arrayTxt[0:x.rfind("</")] #热搜排名
                urlTxt = ft.split('"') #热搜链接
                hotName = ft.split(">")  # 热搜名称
                title = re.sub(r'</a', "", hotName[3])
                span = re.sub(r'</span', "", hotName[5])
                label = re.sub(r'\d|\s', "", span)
                if label=='综艺' or label=='剧集' or label=='电影' or label=='音乐':
                    continue
                hot = re.sub(r'\D', "", span)
                emojis = re.findall(r"<imgsrc=\"(.+?)\"",ft)
                emoji = emojis[0] if emojis else ''
                contents = re.findall(r"title=\"(.+?)\"",ft)
                content = contents[0] if contents else ''
                result = []
                result.append(
                    ('微博','热搜', str(x + 1), title, 'https://s.weibo.com/' + urlTxt[3], emoji, hot, label, content))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,category,rank,title,link,cover,hot,label,content) values (%s, %s, %s, %s, %s, %s, %s, %s, %s) on duplicate key update times = times + 1"
                cursor = db.cursor()
                cursor.executemany(inesrt_re, result)
                db.commit()
            except Exception as e:
                db.rollback()
                print(str(e))
                break
        # 查询输出
        rssItems=db_query("微博")
        makeRss("微博热搜", url, "微博热点排行榜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))


# 【百度热搜】
def parse_baidu(db):
    try:
        url = 'https://top.baidu.com/board?platform=pc&sa=pcindex_a_right'
        hearders = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.4997.0 Safari/537.36'
        }
        res = requests.get(url, headers=hearders)
        html = etree.HTML(res.content.decode())
        data = html.xpath(
            '//*[@id="sanRoot"]/main/div[1]/div[1]/div[2]/a[*]/div[2]/div[2]/div/div/text()')
        linkList = html.xpath('//*[@id="sanRoot"]/main/div[1]/div[1]/div[2]/a/@href')
        coverList = html.xpath('//div[@class="active-item_1Em2h"]/img/@src')
        # 保存数据
        for i, title in enumerate(data):
            try:
                if i > 4:
                    break
                title = title.strip()
                result = []
                result.append(
                    ('百度','热搜', i, title, linkList[i], coverList[i]))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,category,rank,title,link,cover) values (%s, %s, %s, %s, %s, %s) on duplicate key update times = times + 1"
                cursor = db.cursor()
                cursor.executemany(inesrt_re, result)
                db.commit()
            except Exception as e:
                db.rollback()
                print(str(e))
                break
        # 查询输出
        rssItems=db_query("百度")
        makeRss("百度热搜", url, "百度热搜风云榜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【知乎热榜】
def parse_zhihu(db):
    try:
        url = 'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true'
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/86.0.4240.198 Safari/537.36'}
        allResponse = requests.get(url, headers=headers).text
        jsonDecode = json.loads(allResponse)
        # 保存数据
        for i in range(3):
            try:
                title = jsonDecode["data"][i]["target"]["title"]
                link = 'https://www.zhihu.com/question/' + str(jsonDecode["data"][i]["target"]["id"])
                cover = jsonDecode["data"][i]["children"][0]["thumbnail"]
                content = jsonDecode["data"][i]["target"]["excerpt"]
                result = []
                result.append(('知乎', str(i + 1), title, link, cover, content))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,rank,title,link,cover,content) values (%s, %s, %s, %s, %s, %s) on duplicate key update times = times + 1"
                cursor = db.cursor()
                cursor.executemany(inesrt_re, result)
                db.commit()
            except Exception as e:
                db.rollback()
                print(str(e))
                break
        rssItems=db_query("知乎")
        makeRss("知乎热榜", url, "知乎热门排行榜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

# 【B站热榜】
def parse_bilibili(db):
    try:
        url = 'https://www.bilibili.com/v/popular/rank/all'
        hearders = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
        }
        res = requests.get(url, headers=hearders)
        response = etree.HTML(res.content.decode())
        rank_lists=response.xpath('//ul[@class="rank-list"]/li')
        # 读取屏蔽关键词
        config = ConfigParser()
        config.read('huiNews.ini')
        blackTitle = config.get('black','title')
        blackAuthor = config.get('black','author')
        blackTitleList = blackTitle.split(',')
        blackAuthorList = blackAuthor.split(',')
        for rank_list in rank_lists:
            rank_num=rank_list.xpath('div/div/i/span/text()')
            if int(rank_num[0]) > 50:
                break
            title=rank_list.xpath('div/div[@class="info"]/a[@class="title"]/text()')
            link=rank_list.xpath('div/div[@class="info"]/a/@href')
            author=rank_list.xpath('div/div[@class="info"]/div[@class="detail"]/a/span/text()')
            if author in blackAuthorList:
                continue
            if any(s in title for s in blackTitleList):
                continue
            try:
                result = []
                result.append(('B站', rank_num[0], title[0], 'https:' + link[0], author[0].strip()))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,rank,title,link,label) values (%s, %s, %s, %s, %s) on duplicate key update times = times + 1"
                cursor = db.cursor()
                cursor.executemany(inesrt_re, result)
                db.commit()
            except Exception as e:
                db.rollback()
                print(str(e))
                break
        # 获取视频封面
        sql = "SELECT * FROM huinews \
            WHERE TO_DAYS( news_time ) = TO_DAYS(NOW()) \
            AND cover IS NULL AND source = %s" % ("'B站'")
        try:
            # 执行SQL语句
            cursor.execute(sql)
            # 获取所有记录列表
            results = cursor.fetchall()
            rssItems=[]
            for row in results:
                link=row[5]
                time.sleep(1)
                res = requests.get(link, headers=hearders)
                response = etree.HTML(res.content.decode())
                cover=response.xpath('/html/head/meta[15]/@content')
                try:
                    update_re = "UPDATE huinews SET cover = '%s' WHERE link = '%s'" % (cover[0], link)
                    cursor.execute(update_re)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(str(e))
        except Exception as e:
            print("查询B站无封面视频失败！" + str(e))

        rssItems=db_query("B站")
        makeRss("B站热榜", url, "B站热门排行榜", rssItems)
    except Exception as e:
        print(sys._getframe().f_code.co_name+"采集错误，请及时更新规则！" + str(e))

#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def db_query(name):
    # 查询数据
    sql = "SELECT * FROM huinews \
        WHERE TO_DAYS( news_time ) = TO_DAYS(NOW()) \
        AND source = %s" % ("'" + name + "'")
    try:
        # 执行SQL语句
        cursor.execute(sql)
        # 获取所有记录列表
        results = cursor.fetchall()
        rssItems=[]
        for row in results:
            source = row[1]
            category = row[2]
            rank = row[3]
            titleStr = row[4] + '🔝' if rank<=1 else row[4]
            hot = ' ' + str(row[6]) if row[6] else ''
            times = ' x' + str(row[7])
            img = '<img src="' + str(row[8]) + '" referrerpolicy="no-referrer"> ' if row[8] else ''
            label = ' 『' + str(row[9]) + '』' if row[9] else ''
            content = ' ' + str(row[10]) if row[10] else ''
            
            rssItem=PyRSS2Gen.RSSItem(
            title=titleStr if rank>3 else titleStr + '🔥',
            link=row[5],
            description=img + str(rank) + times + label + hot + content,
            pubDate=row[11]
            )
            rssItems.append(rssItem)
        return rssItems
    except Exception as e:
        print("查询数据失败！" + str(e))

def makeRss(title, url, description, rssItems):
	rss = PyRSS2Gen.RSS2(
	title = title, 
	link = url,
	description = description, 
	lastBuildDate = datetime.datetime.now(),
	items = rssItems)
	rss.write_xml(open('Z:\\' + title + '_Rss.xml', "w",encoding='utf-8'),encoding='utf-8') 
	pass

# 打开数据库连接
def db_connect():
    config = ConfigParser()
    config.read('huiNews.ini')
    host = config.get('mysql','host')
    port = config.getint('mysql','port')
    user = config.get('mysql','user')
    password = config.get('mysql','password')
    database = config.get('mysql','database')
    db = pymysql.connect(host=host,
                         port=port,
                         user=user,
                         password=password,
                         database=database)
    return db

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
