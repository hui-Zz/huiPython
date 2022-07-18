# -*- coding:utf-8 -*-
import os
import re
import sys
import time
import json
import base64
import datetime
import requests
import pymysql
import PyRSS2Gen
from configparser import ConfigParser
from lxml import etree
from threading import Thread
from curses.ascii import isdigit

# 单线程，多线程采集方式选择(多线程采集速度快但机器负载短时高)
# thread = 'multi'
thread = 'single'

# 采集数据保存目录,为了安全请修改本程序名字,或移动到其他目录,并修改以下路径,默认与程序同目录
dir = os.path.dirname(os.path.abspath(__file__)) + "/json/"


def parse_weibo(db):
    # 微博热点排行榜
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
                    ('微博', str(x + 1), title, 'https://s.weibo.com/' + urlTxt[3], emoji, hot, label, content))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,rank,title,link,cover,hot,label,content) values (%s, %s, %s, %s, %s, %s, %s, %s)"
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


def parse_baidu(db):
    # 百度热搜
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
                if i > 5:
                    break
                title = title.strip()
                result = []
                result.append(
                    ('百度', i, title, linkList[i], coverList[i]))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,rank,title,link,cover) values (%s, %s, %s, %s, %s)"
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

# 【知乎热搜】
def parse_zhihu(db):
    try:
        url = 'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true'
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/86.0.4240.198 Safari/537.36'}
        allResponse = requests.get(url, headers=headers).text
        jsonDecode = json.loads(allResponse)
        # 保存数据
        for i in range(5):
            try:
                title = jsonDecode["data"][i]["target"]["title"]
                link = 'https://www.zhihu.com/question/' + str(jsonDecode["data"][i]["target"]["id"])
                cover = jsonDecode["data"][i]["children"][0]["thumbnail"]
                content = jsonDecode["data"][i]["target"]["excerpt"]
                result = []
                result.append(('知乎', str(i + 1), title, link, cover, content))
                # print(result)
                inesrt_re = "insert ignore into huinews (source,rank,title,link,cover,content) values (%s, %s, %s, %s, %s, %s)"
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
            rank = row[2]
            hot = ' ' + str(row[5]) if row[5] else ''
            img = '<img src="' + str(row[6]) + '" referrerpolicy="no-referrer"> ' if row[6] else ''
            label = ' 『' + str(row[7]) + '』' if row[7] else ''
            content = ' ' + str(row[8]) if row[8] else ''
            
            rssItem=PyRSS2Gen.RSSItem(
            title=row[3] if rank>3 else row[3] + '🔥',
            link=row[4],
            description=img + str(rank) + label + hot + content,
            pubDate=row[10]
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
    config.read('pymysql.ini')
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
