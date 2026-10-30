# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import base64
import copy
import multiprocessing
import queue
import signal
import subprocess
import threading
import time
import urllib.parse
import json
import glob
import re
import yaml
import random
import string
import httpx
import asyncio
from itertools import chain
from typing import Dict, List, Optional
import sys
import requests
import zipfile
import gzip
import shutil
import platform
import os
from datetime import datetime
from asyncio import Semaphore
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
import warnings

warnings.filterwarnings('ignore')
from requests_html import HTMLSession
import psutil

# TEST_URL = "http://www.gstatic.com/generate_204"
TEST_URL = "http://www.pinterest.com"
CLASH_API_PORTS = [9090]
CLASH_API_HOST = "127.0.0.1"
CLASH_API_SECRET = ""
TIMEOUT = 3
# 抓取订阅源/文件的网络超时（连接, 读取），防止单个源挂起拖死整条流水线
FETCH_TIMEOUT = (5, 30)
# 存储所有节点的速度测试结果
SPEED_TEST = False
SPEED_TEST_LIMIT = 5  # 只测试前30个节点的下行速度，每个节点测试5秒
results_speed = []
MAX_CONCURRENT_TESTS = 100
LIMIT = 10000  # 最多保留LIMIT个节点
CONFIG_FILE = 'clash_config.yaml'
INPUT = "input"  # 从文件中加载代理节点，支持yaml/yml、txt(每条代理链接占一行)
BAN = ["中国", "China", "CN", "电信", "移动", "联通"]
headers = {
    'Accept-Charset': 'utf-8',
    'Accept': 'text/html,application/x-yaml,*/*',
    'User-Agent': 'Clash Verge/1.7.7'
}

# Clash 配置文件的基础结构
clash_config_template = {
    "port": 7890,
    "socks-port": 7891,
    "redir-port": 7892,
    "allow-lan": True,
    "mode": "rule",
    "log-level": "info",
    "external-controller": "127.0.0.1:9090",
    "geodata-mode": True,
    'geox-url': {'geoip': 'https://raw.githubusercontent.com/Loyalsoldier/geoip/release/geoip.dat',
                 'mmdb': 'https://raw.githubusercontent.com/Loyalsoldier/geoip/release/GeoLite2-Country.mmdb'},
    "dns": {
        "enable": True,
        "ipv6": False,
        "default-nameserver": [
            "223.5.5.5",
            "119.29.29.29"
        ],
        "enhanced-mode": "fake-ip",
        "fake-ip-range": "198.18.0.1/16",
        "use-hosts": True,
        "nameserver": [
            "https://doh.pub/dns-query",
            "https://dns.alidns.com/dns-query"
        ],
        "fallback": [
            "https://doh.dns.sb/dns-query",
            "https://dns.cloudflare.com/dns-query",
            "https://dns.twnic.tw/dns-query",
            "tls://8.8.4.4:853"
        ],
        "fallback-filter": {
            "geoip": True,
            "ipcidr": [
                "240.0.0.0/4",
                "0.0.0.0/32"
            ]
        }
    },
    "proxies": [],
    "proxy-groups": [
        {
            "name": "节点选择",
            "type": "select",
            "proxies": [
                "自动选择",
                "故障转移",
                "DIRECT",
                "手动选择"
            ]
        },
        {
            "name": "自动选择",
            "type": "url-test",
            "exclude-filter": "(?i)中国|China|CN|电信|移动|联通",
            "proxies": [],
            # "url": "http://www.gstatic.com/generate_204",
            "url": "http://www.pinterest.com",
            "interval": 300,
            "tolerance": 50
        },
        {
            "name": "故障转移",
            "type": "fallback",
            "exclude-filter": "(?i)中国|China|CN|电信|移动|联通",
            "proxies": [],
            "url": "http://www.gstatic.com/generate_204",
            "interval": 300
        },
        {
            "name": "手动选择",
            "type": "select",
            "proxies": []
        },
    ],
    "rules": [
        "DOMAIN,app.adjust.com,DIRECT",
        "DOMAIN,bdtj.tagtic.cn,DIRECT",
        "DOMAIN,log.mmstat.com,DIRECT",
        "DOMAIN,sycm.mmstat.com,DIRECT",
        "DOMAIN-SUFFIX,blog.google,DIRECT",
        "DOMAIN-SUFFIX,googletraveladservices.com,DIRECT",
        "DOMAIN,dl.google.com,DIRECT",
        "DOMAIN,dl.l.google.com,DIRECT",
        "DOMAIN,fonts.googleapis.com,DIRECT",
        "DOMAIN,fonts.gstatic.com,DIRECT",
        "DOMAIN,mtalk.google.com,DIRECT",
        "DOMAIN,alt1-mtalk.google.com,DIRECT",
        "DOMAIN,alt2-mtalk.google.com,DIRECT",
        "DOMAIN,alt3-mtalk.google.com,DIRECT",
        "DOMAIN,alt4-mtalk.google.com,DIRECT",
        "DOMAIN,alt5-mtalk.google.com,DIRECT",
        "DOMAIN,alt6-mtalk.google.com,DIRECT",
        "DOMAIN,alt7-mtalk.google.com,DIRECT",
        "DOMAIN,alt8-mtalk.google.com,DIRECT",
        "DOMAIN,fairplay.l.qq.com,DIRECT",
        "DOMAIN,livew.l.qq.com,DIRECT",
        "DOMAIN,vd.l.qq.com,DIRECT",
        "DOMAIN,analytics.strava.com,DIRECT",
        "DOMAIN,msg.umeng.com,DIRECT",
        "DOMAIN,msg.umengcloud.com,DIRECT",
        "PROCESS-NAME,com.ximalaya.ting.himalaya,节点选择",
        "DOMAIN-SUFFIX,himalaya.com,节点选择",
        "PROCESS-NAME,deezer.android.app,节点选择",
        "DOMAIN-SUFFIX,deezer.com,节点选择",
        "DOMAIN-SUFFIX,dzcdn.net,节点选择",
        "PROCESS-NAME,com.tencent.ibg.joox,节点选择",
        "PROCESS-NAME,com.tencent.ibg.jooxtv,节点选择",
        "DOMAIN-SUFFIX,joox.com,节点选择",
        "DOMAIN-KEYWORD,jooxweb-api,节点选择",
        "PROCESS-NAME,com.skysoft.kkbox.android,节点选择",
        "DOMAIN-SUFFIX,kkbox.com,节点选择",
        "DOMAIN-SUFFIX,kkbox.com.tw,节点选择",
        "DOMAIN-SUFFIX,kfs.io,节点选择",
        "PROCESS-NAME,com.pandora.android,节点选择",
        "DOMAIN-SUFFIX,pandora.com,节点选择",
        "PROCESS-NAME,com.soundcloud.android,节点选择",
        "DOMAIN-SUFFIX,p-cdn.us,节点选择",
        "DOMAIN-SUFFIX,sndcdn.com,节点选择",
        "DOMAIN-SUFFIX,soundcloud.com,节点选择",
        "PROCESS-NAME,com.spotify.music,节点选择",
        "DOMAIN-SUFFIX,pscdn.co,节点选择",
        "DOMAIN-SUFFIX,scdn.co,节点选择",
        "DOMAIN-SUFFIX,spotify.com,节点选择",
        "DOMAIN-SUFFIX,spoti.fi,节点选择",
        "DOMAIN-KEYWORD,spotify.com,节点选择",
        "DOMAIN-KEYWORD,-spotify-com,节点选择",
        "PROCESS-NAME,com.aspiro.tidal,节点选择",
        "DOMAIN-SUFFIX,tidal.com,节点选择",
        "PROCESS-NAME,com.google.android.apps.youtube.music,节点选择",
        "PROCESS-NAME,com.google.android.youtube.tvmusic,节点选择",
        "PROCESS-NAME,tv.abema,节点选择",
        "DOMAIN-SUFFIX,abema.io,节点选择",
        "DOMAIN-SUFFIX,abema.tv,节点选择",
        "DOMAIN-SUFFIX,ameba.jp,节点选择",
        "DOMAIN-SUFFIX,hayabusa.io,节点选择",
        "DOMAIN-KEYWORD,abematv.akamaized.net,节点选择",
        "PROCESS-NAME,com.channel4.ondemand,节点选择",
        "DOMAIN-SUFFIX,c4assets.com,节点选择",
        "DOMAIN-SUFFIX,channel4.com,节点选择",
        "PROCESS-NAME,com.amazon.avod.thirdp,节点选择",
        "DOMAIN-SUFFIX,aiv-cdn.net,节点选择",
        "DOMAIN-SUFFIX,aiv-delivery.net,节点选择",
        "DOMAIN-SUFFIX,amazonvideo.com,节点选择",
        "DOMAIN-SUFFIX,primevideo.com,节点选择",
        "DOMAIN-SUFFIX,media-amazon.com,节点选择",
        "DOMAIN,atv-ps.amazon.com,节点选择",
        "DOMAIN,fls-na.amazon.com,节点选择",
        "DOMAIN,avodmp4s3ww-a.akamaihd.net,节点选择",
        "DOMAIN,d25xi40x97liuc.cloudfront.net,节点选择",
        "DOMAIN,dmqdd6hw24ucf.cloudfront.net,节点选择",
        "DOMAIN,dmqdd6hw24ucf.cloudfront.net,节点选择",
        "DOMAIN,d22qjgkvxw22r6.cloudfront.net,节点选择",
        "DOMAIN,d1v5ir2lpwr8os.cloudfront.net,节点选择",
        "DOMAIN,d27xxe7juh1us6.cloudfront.net,节点选择",
        "DOMAIN-KEYWORD,avoddashs,节点选择",
        "DOMAIN,linear.tv.apple.com,节点选择",
        "DOMAIN,play-edge.itunes.apple.com,节点选择",
        "PROCESS-NAME,tw.com.gamer.android.animad,节点选择",
        "DOMAIN-SUFFIX,bahamut.com.tw,节点选择",
        "DOMAIN-SUFFIX,gamer.com.tw,节点选择",
        "DOMAIN,gamer-cds.cdn.hinet.net,节点选择",
        "DOMAIN,gamer2-cds.cdn.hinet.net,节点选择",
        "PROCESS-NAME,bbc.iplayer.android,节点选择",
        "DOMAIN-SUFFIX,bbc.co.uk,节点选择",
        "DOMAIN-SUFFIX,bbci.co.uk,节点选择",
        "DOMAIN-KEYWORD,bbcfmt,节点选择",
        "DOMAIN-KEYWORD,uk-live,节点选择",
        "PROCESS-NAME,com.dazn,节点选择",
        "DOMAIN-SUFFIX,dazn.com,节点选择",
        "DOMAIN-SUFFIX,dazn-api.com,节点选择",
        "DOMAIN,d151l6v8er5bdm.cloudfront.net,节点选择",
        "DOMAIN-KEYWORD,voddazn,节点选择",
        "PROCESS-NAME,com.disney.disneyplus,节点选择",
        "DOMAIN-SUFFIX,bamgrid.com,节点选择",
        "DOMAIN-SUFFIX,disneyplus.com,节点选择",
        "DOMAIN-SUFFIX,disney-plus.net,节点选择",
        "DOMAIN-SUFFIX,dssott.com,节点选择",
        "DOMAIN,cdn.registerdisney.go.com,节点选择",
        "PROCESS-NAME,com.dmm.app.movieplayer,节点选择",
        "DOMAIN-SUFFIX,dmm.co.jp,节点选择",
        "DOMAIN-SUFFIX,dmm.com,节点选择",
        "DOMAIN-SUFFIX,dmm-extension.com,节点选择",
        "PROCESS-NAME,com.tvbusa.encore,节点选择",
        "DOMAIN-SUFFIX,encoretvb.com,节点选择",
        "DOMAIN,edge.api.brightcove.com,节点选择",
        "DOMAIN,bcbolt446c5271-a.akamaihd.net,节点选择",
        "PROCESS-NAME,com.fox.now,节点选择",
        "DOMAIN-SUFFIX,fox.com,节点选择",
        "DOMAIN-SUFFIX,foxdcg.com,节点选择",
        "DOMAIN-SUFFIX,theplatform.com,节点选择",
        "DOMAIN-SUFFIX,uplynk.com,节点选择",
        "DOMAIN-SUFFIX,foxplus.com,节点选择",
        "DOMAIN,cdn-fox-networks-group-green.akamaized.net,节点选择",
        "DOMAIN,d3cv4a9a9wh0bt.cloudfront.net,节点选择",
        "DOMAIN,foxsports01-i.akamaihd.net,节点选择",
        "DOMAIN,foxsports02-i.akamaihd.net,节点选择",
        "DOMAIN,foxsports03-i.akamaihd.net,节点选择",
        "DOMAIN,staticasiafox.akamaized.net,节点选择",
        "PROCESS-NAME,com.hbo.hbonow,节点选择",
        "DOMAIN-SUFFIX,hbo.com,节点选择",
        "DOMAIN-SUFFIX,hbogo.com,节点选择",
        "DOMAIN-SUFFIX,hbonow.com,节点选择",
        "DOMAIN-SUFFIX,hbomax.com,节点选择",
        "PROCESS-NAME,hk.hbo.hbogo,节点选择",
        "DOMAIN-SUFFIX,hbogoasia.com,节点选择",
        "DOMAIN-SUFFIX,hbogoasia.hk,节点选择",
        "DOMAIN,bcbolthboa-a.akamaihd.net,节点选择",
        "DOMAIN,players.brightcove.net,节点选择",
        "DOMAIN,s3-ap-southeast-1.amazonaws.com,节点选择",
        "DOMAIN,dai3fd1oh325y.cloudfront.net,节点选择",
        "DOMAIN,44wilhpljf.execute-api.ap-southeast-1.amazonaws.com,节点选择",
        "DOMAIN,hboasia1-i.akamaihd.net,节点选择",
        "DOMAIN,hboasia2-i.akamaihd.net,节点选择",
        "DOMAIN,hboasia3-i.akamaihd.net,节点选择",
        "DOMAIN,hboasia4-i.akamaihd.net,节点选择",
        "DOMAIN,hboasia5-i.akamaihd.net,节点选择",
        "DOMAIN,cf-images.ap-southeast-1.prod.boltdns.net,节点选择",
        "DOMAIN-SUFFIX,5itv.tv,节点选择",
        "DOMAIN-SUFFIX,ocnttv.com,节点选择",
        "PROCESS-NAME,com.hulu.plus,节点选择",
        "DOMAIN-SUFFIX,hulu.com,节点选择",
        "DOMAIN-SUFFIX,huluim.com,节点选择",
        "DOMAIN-SUFFIX,hulustream.com,节点选择",
        "PROCESS-NAME,jp.happyon.android,节点选择",
        "DOMAIN-SUFFIX,happyon.jp,节点选择",
        "DOMAIN-SUFFIX,hjholdings.jp,节点选择",
        "DOMAIN-SUFFIX,hulu.jp,节点选择",
        "PROCESS-NAME,air.ITVMobilePlayer,节点选择",
        "DOMAIN-SUFFIX,itv.com,节点选择",
        "DOMAIN-SUFFIX,itvstatic.com,节点选择",
        "DOMAIN,itvpnpmobile-a.akamaihd.net,节点选择",
        "PROCESS-NAME,com.kktv.kktv,节点选择",
        "DOMAIN-SUFFIX,kktv.com.tw,节点选择",
        "DOMAIN-SUFFIX,kktv.me,节点选择",
        "DOMAIN,kktv-theater.kk.stream,节点选择",
        "PROCESS-NAME,com.linecorp.linetv,节点选择",
        "DOMAIN-SUFFIX,linetv.tw,节点选择",
        "DOMAIN,d3c7rimkq79yfu.cloudfront.net,节点选择",
        "PROCESS-NAME,com.litv.mobile.gp.litv,节点选择",
        "DOMAIN-SUFFIX,litv.tv,节点选择",
        "DOMAIN,litvfreemobile-hichannel.cdn.hinet.net,节点选择",
        "PROCESS-NAME,com.mobileiq.demand5,节点选择",
        "DOMAIN-SUFFIX,channel5.com,节点选择",
        "DOMAIN-SUFFIX,my5.tv,节点选择",
        "DOMAIN,d349g9zuie06uo.cloudfront.net,节点选择",
        "PROCESS-NAME,com.tvb.mytvsuper,节点选择",
        "DOMAIN-SUFFIX,mytvsuper.com,节点选择",
        "DOMAIN-SUFFIX,tvb.com,节点选择",
        "PROCESS-NAME,com.netflix.mediaclient,节点选择",
        "DOMAIN-SUFFIX,netflix.com,节点选择",
        "DOMAIN-SUFFIX,netflix.net,节点选择",
        "DOMAIN-SUFFIX,nflxext.com,节点选择",
        "DOMAIN-SUFFIX,nflximg.com,节点选择",
        "DOMAIN-SUFFIX,nflximg.net,节点选择",
        "DOMAIN-SUFFIX,nflxso.net,节点选择",
        "DOMAIN-SUFFIX,nflxvideo.net,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest0.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest1.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest2.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest3.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest4.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest5.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest6.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest7.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest8.com,节点选择",
        "DOMAIN-SUFFIX,netflixdnstest9.com,节点选择",
        "DOMAIN-KEYWORD,dualstack.api.disney-device-prod-nlb-,节点选择",
        "DOMAIN-KEYWORD,dualstack.ichnaea-web-,节点选择",
        "IP-CIDR,23.246.0.0/18,节点选择,no-resolve",
        "IP-CIDR,37.77.184.0/21,节点选择,no-resolve",
        "IP-CIDR,45.57.0.0/17,节点选择,no-resolve",
        "IP-CIDR,64.120.128.0/17,节点选择,no-resolve",
        "IP-CIDR,66.197.128.0/17,节点选择,no-resolve",
        "IP-CIDR,108.175.32.0/20,节点选择,no-resolve",
        "IP-CIDR,192.173.64.0/18,节点选择,no-resolve",
        "IP-CIDR,198.38.96.0/19,节点选择,no-resolve",
        "IP-CIDR,198.45.48.0/20,节点选择,no-resolve",
        "IP-CIDR,34.210.42.111/32,节点选择,no-resolve",
        "IP-CIDR,52.89.124.203/32,节点选择,no-resolve",
        "IP-CIDR,54.148.37.5/32,节点选择,no-resolve",
        "PROCESS-NAME,jp.nicovideo.android,节点选择",
        "DOMAIN-SUFFIX,dmc.nico,节点选择",
        "DOMAIN-SUFFIX,nicovideo.jp,节点选择",
        "DOMAIN-SUFFIX,nimg.jp,节点选择",
        "PROCESS-NAME,com.pccw.nowemobile,节点选择",
        "DOMAIN-SUFFIX,nowe.com,节点选择",
        "DOMAIN-SUFFIX,nowestatic.com,节点选择",
        "PROCESS-NAME,com.pbs.video,节点选择",
        "DOMAIN-SUFFIX,pbs.org,节点选择",
        "DOMAIN-SUFFIX,phncdn.com,节点选择",
        "DOMAIN-SUFFIX,phprcdn.com,节点选择",
        "DOMAIN-SUFFIX,pornhub.com,节点选择",
        "DOMAIN-SUFFIX,pornhubpremium.com,节点选择",
        "PROCESS-NAME,com.twgood.android,节点选择",
        "DOMAIN-SUFFIX,skyking.com.tw,节点选择",
        "DOMAIN,hamifans.emome.net,节点选择",
        "PROCESS-NAME,com.ss.android.ugc.trill,节点选择",
        "DOMAIN-SUFFIX,byteoversea.com,节点选择",
        "DOMAIN-SUFFIX,ibytedtos.com,节点选择",
        "DOMAIN-SUFFIX,muscdn.com,节点选择",
        "DOMAIN-SUFFIX,musical.ly,节点选择",
        "DOMAIN-SUFFIX,tiktok.com,节点选择",
        "DOMAIN-SUFFIX,tik-tokapi.com,节点选择",
        "DOMAIN-SUFFIX,tiktokcdn.com,节点选择",
        "DOMAIN-SUFFIX,tiktokv.com,节点选择",
        "DOMAIN-KEYWORD,-tiktokcdn-com,节点选择",
        "PROCESS-NAME,tv.twitch.android.app,节点选择",
        "DOMAIN-SUFFIX,jtvnw.net,节点选择",
        "DOMAIN-SUFFIX,ttvnw.net,节点选择",
        "DOMAIN-SUFFIX,twitch.tv,节点选择",
        "DOMAIN-SUFFIX,twitchcdn.net,节点选择",
        "PROCESS-NAME,com.hktve.viutv,节点选择",
        "DOMAIN-SUFFIX,viu.com,节点选择",
        "DOMAIN-SUFFIX,viu.tv,节点选择",
        "DOMAIN,api.viu.now.com,节点选择",
        "DOMAIN,d1k2us671qcoau.cloudfront.net,节点选择",
        "DOMAIN,d2anahhhmp1ffz.cloudfront.net,节点选择",
        "DOMAIN,dfp6rglgjqszk.cloudfront.net,节点选择",
        "PROCESS-NAME,com.google.android.youtube,节点选择",
        "PROCESS-NAME,com.google.android.youtube.tv,节点选择",
        "DOMAIN-SUFFIX,googlevideo.com,节点选择",
        "DOMAIN-SUFFIX,youtube.com,节点选择",
        "DOMAIN,youtubei.googleapis.com,节点选择",
        "DOMAIN-SUFFIX,biliapi.net,节点选择",
        "DOMAIN-SUFFIX,bilibili.com,节点选择",
        "DOMAIN,upos-hz-mirrorakam.akamaized.net,节点选择",
        "DOMAIN-SUFFIX,iq.com,节点选择",
        "DOMAIN,cache.video.iqiyi.com,节点选择",
        "DOMAIN,cache-video.iq.com,节点选择",
        "DOMAIN,intl.iqiyi.com,节点选择",
        "DOMAIN,intl-rcd.iqiyi.com,节点选择",
        "DOMAIN,intl-subscription.iqiyi.com,节点选择",
        "DOMAIN-KEYWORD,oversea-tw.inter.iqiyi.com,节点选择",
        "DOMAIN-KEYWORD,oversea-tw.inter.ptqy.gitv.tv,节点选择",
        "IP-CIDR,103.44.56.0/22,节点选择,no-resolve",
        "IP-CIDR,118.26.32.0/23,节点选择,no-resolve",
        "IP-CIDR,118.26.120.0/24,节点选择,no-resolve",
        "IP-CIDR,223.119.62.225/28,节点选择,no-resolve",
        "IP-CIDR,23.40.242.10/32,节点选择,no-resolve",
        "IP-CIDR,23.40.241.251/32,节点选择,no-resolve",
        "DOMAIN-SUFFIX,api.mgtv.com,节点选择",
        "DOMAIN-SUFFIX,wetv.vip,节点选择",
        "DOMAIN-SUFFIX,wetvinfo.com,节点选择",
        "DOMAIN,testflight.apple.com,节点选择",
        "DOMAIN-SUFFIX,appspot.com,节点选择",
        "DOMAIN-SUFFIX,blogger.com,节点选择",
        "DOMAIN-SUFFIX,getoutline.org,节点选择",
        "DOMAIN-SUFFIX,gvt0.com,节点选择",
        "DOMAIN-SUFFIX,gvt3.com,节点选择",
        "DOMAIN-SUFFIX,xn--ngstr-lra8j.com,节点选择",
        "DOMAIN-SUFFIX,ytimg.com,节点选择",
        "DOMAIN-KEYWORD,google,节点选择",
        "DOMAIN-KEYWORD,.blogspot.,节点选择",
        "DOMAIN-SUFFIX,aka.ms,节点选择",
        "DOMAIN-SUFFIX,onedrive.live.com,节点选择",
        "DOMAIN,az416426.vo.msecnd.net,节点选择",
        "DOMAIN,az668014.vo.msecnd.net,节点选择",
        "DOMAIN-SUFFIX,cdninstagram.com,节点选择",
        "DOMAIN-SUFFIX,facebook.com,节点选择",
        "DOMAIN-SUFFIX,facebook.net,节点选择",
        "DOMAIN-SUFFIX,fb.com,节点选择",
        "DOMAIN-SUFFIX,fb.me,节点选择",
        "DOMAIN-SUFFIX,fbaddins.com,节点选择",
        "DOMAIN-SUFFIX,fbcdn.net,节点选择",
        "DOMAIN-SUFFIX,fbsbx.com,节点选择",
        "DOMAIN-SUFFIX,fbworkmail.com,节点选择",
        "DOMAIN-SUFFIX,instagram.com,节点选择",
        "DOMAIN-SUFFIX,m.me,节点选择",
        "DOMAIN-SUFFIX,messenger.com,节点选择",
        "DOMAIN-SUFFIX,oculus.com,节点选择",
        "DOMAIN-SUFFIX,oculuscdn.com,节点选择",
        "DOMAIN-SUFFIX,rocksdb.org,节点选择",
        "DOMAIN-SUFFIX,whatsapp.com,节点选择",
        "DOMAIN-SUFFIX,whatsapp.net,节点选择",
        "DOMAIN-SUFFIX,pscp.tv,节点选择",
        "DOMAIN-SUFFIX,periscope.tv,节点选择",
        "DOMAIN-SUFFIX,t.co,节点选择",
        "DOMAIN-SUFFIX,twimg.co,节点选择",
        "DOMAIN-SUFFIX,twimg.com,节点选择",
        "DOMAIN-SUFFIX,twitpic.com,节点选择",
        "DOMAIN-SUFFIX,twitter.com,节点选择",
        "DOMAIN-SUFFIX,x.com,节点选择",
        "DOMAIN-SUFFIX,vine.co,节点选择",
        "DOMAIN-SUFFIX,telegra.ph,节点选择",
        "DOMAIN-SUFFIX,telegram.org,节点选择",
        "IP-CIDR,91.108.4.0/22,节点选择,no-resolve",
        "IP-CIDR,91.108.8.0/22,节点选择,no-resolve",
        "IP-CIDR,91.108.12.0/22,节点选择,no-resolve",
        "IP-CIDR,91.108.16.0/22,节点选择,no-resolve",
        "IP-CIDR,91.108.20.0/22,节点选择,no-resolve",
        "IP-CIDR,91.108.56.0/22,节点选择,no-resolve",
        "IP-CIDR,149.154.160.0/20,节点选择,no-resolve",
        "IP-CIDR,2001:b28:f23d::/48,节点选择,no-resolve",
        "IP-CIDR,2001:b28:f23f::/48,节点选择,no-resolve",
        "IP-CIDR,2001:67c:4e8::/48,节点选择,no-resolve",
        "DOMAIN-SUFFIX,line.me,节点选择",
        "DOMAIN-SUFFIX,line-apps.com,节点选择",
        "DOMAIN-SUFFIX,line-scdn.net,节点选择",
        "DOMAIN-SUFFIX,naver.jp,节点选择",
        "IP-CIDR,103.2.30.0/23,节点选择,no-resolve",
        "IP-CIDR,125.209.208.0/20,节点选择,no-resolve",
        "IP-CIDR,147.92.128.0/17,节点选择,no-resolve",
        "IP-CIDR,203.104.144.0/21,节点选择,no-resolve",
        "DOMAIN-SUFFIX,amazon.co.jp,节点选择",
        "DOMAIN,d3c33hcgiwev3.cloudfront.net,节点选择",
        "DOMAIN,payments-jp.amazon.com,节点选择",
        "DOMAIN,s3-ap-northeast-1.amazonaws.com,节点选择",
        "DOMAIN,s3-ap-southeast-2.amazonaws.com,节点选择",
        "DOMAIN,a248.e.akamai.net,节点选择",
        "DOMAIN,a771.dscq.akamai.net,节点选择",
        "DOMAIN-SUFFIX,4shared.com,节点选择",
        "DOMAIN-SUFFIX,9cache.com,节点选择",
        "DOMAIN-SUFFIX,9gag.com,节点选择",
        "DOMAIN-SUFFIX,abc.com,节点选择",
        "DOMAIN-SUFFIX,abc.net.au,节点选择",
        "DOMAIN-SUFFIX,abebooks.com,节点选择",
        "DOMAIN-SUFFIX,ao3.org,节点选择",
        "DOMAIN-SUFFIX,apigee.com,节点选择",
        "DOMAIN-SUFFIX,apkcombo.com,节点选择",
        "DOMAIN-SUFFIX,apk-dl.com,节点选择",
        "DOMAIN-SUFFIX,apkfind.com,节点选择",
        "DOMAIN-SUFFIX,apkmirror.com,节点选择",
        "DOMAIN-SUFFIX,apkmonk.com,节点选择",
        "DOMAIN-SUFFIX,apkpure.com,节点选择",
        "DOMAIN-SUFFIX,aptoide.com,节点选择",
        "DOMAIN-SUFFIX,archive.is,节点选择",
        "DOMAIN-SUFFIX,archive.org,节点选择",
        "DOMAIN-SUFFIX,archiveofourown.com,节点选择",
        "DOMAIN-SUFFIX,archiveofourown.org,节点选择",
        "DOMAIN-SUFFIX,arte.tv,节点选择",
        "DOMAIN-SUFFIX,artstation.com,节点选择",
        "DOMAIN-SUFFIX,arukas.io,节点选择",
        "DOMAIN-SUFFIX,ask.com,节点选择",
        "DOMAIN-SUFFIX,avg.com,节点选择",
        "DOMAIN-SUFFIX,avgle.com,节点选择",
        "DOMAIN-SUFFIX,badoo.com,节点选择",
        "DOMAIN-SUFFIX,bandwagonhost.com,节点选择",
        "DOMAIN-SUFFIX,bangkokpost.com,节点选择",
        "DOMAIN-SUFFIX,bbc.com,节点选择",
        "DOMAIN-SUFFIX,behance.net,节点选择",
        "DOMAIN-SUFFIX,bibox.com,节点选择",
        "DOMAIN-SUFFIX,biggo.com.tw,节点选择",
        "DOMAIN-SUFFIX,binance.com,节点选择",
        "DOMAIN-SUFFIX,bit.ly,节点选择",
        "DOMAIN-SUFFIX,bitcointalk.org,节点选择",
        "DOMAIN-SUFFIX,bitfinex.com,节点选择",
        "DOMAIN-SUFFIX,bitmex.com,节点选择",
        "DOMAIN-SUFFIX,bit-z.com,节点选择",
        "DOMAIN-SUFFIX,bloglovin.com,节点选择",
        "DOMAIN-SUFFIX,bloomberg.cn,节点选择",
        "DOMAIN-SUFFIX,bloomberg.com,节点选择",
        "DOMAIN-SUFFIX,blubrry.com,节点选择",
        "DOMAIN-SUFFIX,book.com.tw,节点选择",
        "DOMAIN-SUFFIX,booklive.jp,节点选择",
        "DOMAIN-SUFFIX,books.com.tw,节点选择",
        "DOMAIN-SUFFIX,boslife.net,节点选择",
        "DOMAIN-SUFFIX,box.com,节点选择",
        "DOMAIN-SUFFIX,brave.com,节点选择",
        "DOMAIN-SUFFIX,businessinsider.com,节点选择",
        "DOMAIN-SUFFIX,buzzfeed.com,节点选择",
        "DOMAIN-SUFFIX,bwh1.net,节点选择",
        "DOMAIN-SUFFIX,castbox.fm,节点选择",
        "DOMAIN-SUFFIX,cbc.ca,节点选择",
        "DOMAIN-SUFFIX,cdw.com,节点选择",
        "DOMAIN-SUFFIX,change.org,节点选择",
        "DOMAIN-SUFFIX,channelnewsasia.com,节点选择",
        "DOMAIN-SUFFIX,ck101.com,节点选择",
        "DOMAIN-SUFFIX,clarionproject.org,节点选择",
        "DOMAIN-SUFFIX,cloudcone.com,节点选择",
        "DOMAIN-SUFFIX,clyp.it,节点选择",
        "DOMAIN-SUFFIX,cna.com.tw,节点选择",
        "DOMAIN-SUFFIX,comparitech.com,节点选择",
        "DOMAIN-SUFFIX,conoha.jp,节点选择",
        "DOMAIN-SUFFIX,crucial.com,节点选择",
        "DOMAIN-SUFFIX,cts.com.tw,节点选择",
        "DOMAIN-SUFFIX,cw.com.tw,节点选择",
        "DOMAIN-SUFFIX,cyberctm.com,节点选择",
        "DOMAIN-SUFFIX,dailymotion.com,节点选择",
        "DOMAIN-SUFFIX,dailyview.tw,节点选择",
        "DOMAIN-SUFFIX,daum.net,节点选择",
        "DOMAIN-SUFFIX,daumcdn.net,节点选择",
        "DOMAIN-SUFFIX,dcard.tw,节点选择",
        "DOMAIN-SUFFIX,deadline.com,节点选择",
        "DOMAIN-SUFFIX,deepdiscount.com,节点选择",
        "DOMAIN-SUFFIX,depositphotos.com,节点选择",
        "DOMAIN-SUFFIX,deviantart.com,节点选择",
        "DOMAIN-SUFFIX,disconnect.me,节点选择",
        "DOMAIN-SUFFIX,discordapp.com,节点选择",
        "DOMAIN-SUFFIX,discordapp.net,节点选择",
        "DOMAIN-SUFFIX,disqus.com,节点选择",
        "DOMAIN-SUFFIX,dlercloud.com,节点选择",
        "DOMAIN-SUFFIX,dmhy.org,节点选择",
        "DOMAIN-SUFFIX,dns2go.com,节点选择",
        "DOMAIN-SUFFIX,dowjones.com,节点选择",
        "DOMAIN-SUFFIX,dropbox.com,节点选择",
        "DOMAIN-SUFFIX,dropboxapi.com,节点选择",
        "DOMAIN-SUFFIX,dropboxusercontent.com,节点选择",
        "DOMAIN-SUFFIX,duckduckgo.com,节点选择",
        "DOMAIN-SUFFIX,duyaoss.com,节点选择",
        "DOMAIN-SUFFIX,dw.com,节点选择",
        "DOMAIN-SUFFIX,dynu.com,节点选择",
        "DOMAIN-SUFFIX,earthcam.com,节点选择",
        "DOMAIN-SUFFIX,ebookservice.tw,节点选择",
        "DOMAIN-SUFFIX,economist.com,节点选择",
        "DOMAIN-SUFFIX,edgecastcdn.net,节点选择",
        "DOMAIN-SUFFIX,edx-cdn.org,节点选择",
        "DOMAIN-SUFFIX,elpais.com,节点选择",
        "DOMAIN-SUFFIX,enanyang.my,节点选择",
        "DOMAIN-SUFFIX,encyclopedia.com,节点选择",
        "DOMAIN-SUFFIX,esoir.be,节点选择",
        "DOMAIN-SUFFIX,etherscan.io,节点选择",
        "DOMAIN-SUFFIX,euronews.com,节点选择",
        "DOMAIN-SUFFIX,evozi.com,节点选择",
        "DOMAIN-SUFFIX,exblog.jp,节点选择",
        "DOMAIN-SUFFIX,feeder.co,节点选择",
        "DOMAIN-SUFFIX,feedly.com,节点选择",
        "DOMAIN-SUFFIX,feedx.net,节点选择",
        "DOMAIN-SUFFIX,firech.at,节点选择",
        "DOMAIN-SUFFIX,flickr.com,节点选择",
        "DOMAIN-SUFFIX,flipboard.com,节点选择",
        "DOMAIN-SUFFIX,flitto.com,节点选择",
        "DOMAIN-SUFFIX,foreignpolicy.com,节点选择",
        "DOMAIN-SUFFIX,fortawesome.com,节点选择",
        "DOMAIN-SUFFIX,freetls.fastly.net,节点选择",
        "DOMAIN-SUFFIX,friday.tw,节点选择",
        "DOMAIN-SUFFIX,ft.com,节点选择",
        "DOMAIN-SUFFIX,ftchinese.com,节点选择",
        "DOMAIN-SUFFIX,ftimg.net,节点选择",
        "DOMAIN-SUFFIX,gate.io,节点选择",
        "DOMAIN-SUFFIX,genius.com,节点选择",
        "DOMAIN-SUFFIX,getlantern.org,节点选择",
        "DOMAIN-SUFFIX,getsync.com,节点选择",
        "DOMAIN-SUFFIX,github.com,节点选择",
        "DOMAIN-SUFFIX,github.io,节点选择",
        "DOMAIN-SUFFIX,githubusercontent.com,节点选择",
        "DOMAIN-SUFFIX,globalvoices.org,节点选择",
        "DOMAIN-SUFFIX,goo.ne.jp,节点选择",
        "DOMAIN-SUFFIX,goodreads.com,节点选择",
        "DOMAIN-SUFFIX,gov.tw,节点选择",
        "DOMAIN-SUFFIX,greatfire.org,节点选择",
        "DOMAIN-SUFFIX,gumroad.com,节点选择",
        "DOMAIN-SUFFIX,hbg.com,节点选择",
        "DOMAIN-SUFFIX,heroku.com,节点选择",
        "DOMAIN-SUFFIX,hightail.com,节点选择",
        "DOMAIN-SUFFIX,hk01.com,节点选择",
        "DOMAIN-SUFFIX,hkbf.org,节点选择",
        "DOMAIN-SUFFIX,hkbookcity.com,节点选择",
        "DOMAIN-SUFFIX,hkej.com,节点选择",
        "DOMAIN-SUFFIX,hket.com,节点选择",
        "DOMAIN-SUFFIX,hootsuite.com,节点选择",
        "DOMAIN-SUFFIX,hudson.org,节点选择",
        "DOMAIN-SUFFIX,huffpost.com,节点选择",
        "DOMAIN-SUFFIX,hyread.com.tw,节点选择",
        "DOMAIN-SUFFIX,ibtimes.com,节点选择",
        "DOMAIN-SUFFIX,i-cable.com,节点选择",
        "DOMAIN-SUFFIX,icij.org,节点选择",
        "DOMAIN-SUFFIX,icoco.com,节点选择",
        "DOMAIN-SUFFIX,imgur.com,节点选择",
        "DOMAIN-SUFFIX,independent.co.uk,节点选择",
        "DOMAIN-SUFFIX,initiummall.com,节点选择",
        "DOMAIN-SUFFIX,inoreader.com,节点选择",
        "DOMAIN-SUFFIX,insecam.org,节点选择",
        "DOMAIN-SUFFIX,ipfs.io,节点选择",
        "DOMAIN-SUFFIX,issuu.com,节点选择",
        "DOMAIN-SUFFIX,istockphoto.com,节点选择",
        "DOMAIN-SUFFIX,japantimes.co.jp,节点选择",
        "DOMAIN-SUFFIX,jiji.com,节点选择",
        "DOMAIN-SUFFIX,jinx.com,节点选择",
        "DOMAIN-SUFFIX,jkforum.net,节点选择",
        "DOMAIN-SUFFIX,joinmastodon.org,节点选择",
        "DOMAIN-SUFFIX,justmysocks.net,节点选择",
        "DOMAIN-SUFFIX,justpaste.it,节点选择",
        "DOMAIN-SUFFIX,kadokawa.co.jp,节点选择",
        "DOMAIN-SUFFIX,kakao.com,节点选择",
        "DOMAIN-SUFFIX,kakaocorp.com,节点选择",
        "DOMAIN-SUFFIX,kik.com,节点选择",
        "DOMAIN-SUFFIX,kingkong.com.tw,节点选择",
        "DOMAIN-SUFFIX,knowyourmeme.com,节点选择",
        "DOMAIN-SUFFIX,kobo.com,节点选择",
        "DOMAIN-SUFFIX,kobobooks.com,节点选择",
        "DOMAIN-SUFFIX,kodingen.com,节点选择",
        "DOMAIN-SUFFIX,lemonde.fr,节点选择",
        "DOMAIN-SUFFIX,lepoint.fr,节点选择",
        "DOMAIN-SUFFIX,lihkg.com,节点选择",
        "DOMAIN-SUFFIX,linkedin.com,节点选择",
        "DOMAIN-SUFFIX,limbopro.xyz,节点选择",
        "DOMAIN-SUFFIX,listennotes.com,节点选择",
        "DOMAIN-SUFFIX,livestream.com,节点选择",
        "DOMAIN-SUFFIX,logimg.jp,节点选择",
        "DOMAIN-SUFFIX,logmein.com,节点选择",
        "DOMAIN-SUFFIX,mail.ru,节点选择",
        "DOMAIN-SUFFIX,mailchimp.com,节点选择",
        "DOMAIN-SUFFIX,marc.info,节点选择",
        "DOMAIN-SUFFIX,matters.news,节点选择",
        "DOMAIN-SUFFIX,maying.co,节点选择",
        "DOMAIN-SUFFIX,medium.com,节点选择",
        "DOMAIN-SUFFIX,mega.nz,节点选择",
        "DOMAIN-SUFFIX,mergersandinquisitions.com,节点选择",
        "DOMAIN-SUFFIX,mingpao.com,节点选择",
        "DOMAIN-SUFFIX,mixi.jp,节点选择",
        "DOMAIN-SUFFIX,mobile01.com,节点选择",
        "DOMAIN-SUFFIX,mubi.com,节点选择",
        "DOMAIN-SUFFIX,myspace.com,节点选择",
        "DOMAIN-SUFFIX,myspacecdn.com,节点选择",
        "DOMAIN-SUFFIX,nanyang.com,节点选择",
        "DOMAIN-SUFFIX,nationalinterest.org,节点选择",
        "DOMAIN-SUFFIX,naver.com,节点选择",
        "DOMAIN-SUFFIX,nbcnews.com,节点选择",
        "DOMAIN-SUFFIX,ndr.de,节点选择",
        "DOMAIN-SUFFIX,neowin.net,节点选择",
        "DOMAIN-SUFFIX,newstapa.org,节点选择",
        "DOMAIN-SUFFIX,nexitally.com,节点选择",
        "DOMAIN-SUFFIX,nhk.or.jp,节点选择",
        "DOMAIN-SUFFIX,nii.ac.jp,节点选择",
        "DOMAIN-SUFFIX,nikkei.com,节点选择",
        "DOMAIN-SUFFIX,nitter.net,节点选择",
        "DOMAIN-SUFFIX,nofile.io,节点选择",
        "DOMAIN-SUFFIX,notion.so,节点选择",
        "DOMAIN-SUFFIX,now.com,节点选择",
        "DOMAIN-SUFFIX,nrk.no,节点选择",
        "DOMAIN-SUFFIX,nuget.org,节点选择",
        "DOMAIN-SUFFIX,nyaa.si,节点选择",
        "DOMAIN-SUFFIX,nyt.com,节点选择",
        "DOMAIN-SUFFIX,nytchina.com,节点选择",
        "DOMAIN-SUFFIX,nytcn.me,节点选择",
        "DOMAIN-SUFFIX,nytco.com,节点选择",
        "DOMAIN-SUFFIX,nytimes.com,节点选择",
        "DOMAIN-SUFFIX,nytimg.com,节点选择",
        "DOMAIN-SUFFIX,nytlog.com,节点选择",
        "DOMAIN-SUFFIX,nytstyle.com,节点选择",
        "DOMAIN-SUFFIX,ok.ru,节点选择",
        "DOMAIN-SUFFIX,okex.com,节点选择",
        "DOMAIN-SUFFIX,on.cc,节点选择",
        "DOMAIN-SUFFIX,orientaldaily.com.my,节点选择",
        "DOMAIN-SUFFIX,overcast.fm,节点选择",
        "DOMAIN-SUFFIX,paltalk.com,节点选择",
        "DOMAIN-SUFFIX,parsevideo.com,节点选择",
        "DOMAIN-SUFFIX,pawoo.net,节点选择",
        "DOMAIN-SUFFIX,pbxes.com,节点选择",
        "DOMAIN-SUFFIX,pcdvd.com.tw,节点选择",
        "DOMAIN-SUFFIX,pchome.com.tw,节点选择",
        "DOMAIN-SUFFIX,pcloud.com,节点选择",
        "DOMAIN-SUFFIX,peing.net,节点选择",
        "DOMAIN-SUFFIX,picacomic.com,节点选择",
        "DOMAIN-SUFFIX,pinimg.com,节点选择",
        "DOMAIN-SUFFIX,pixiv.net,节点选择",
        "DOMAIN-SUFFIX,player.fm,节点选择",
        "DOMAIN-SUFFIX,plurk.com,节点选择",
        "DOMAIN-SUFFIX,po18.tw,节点选择",
        "DOMAIN-SUFFIX,potato.im,节点选择",
        "DOMAIN-SUFFIX,potatso.com,节点选择",
        "DOMAIN-SUFFIX,prism-break.org,节点选择",
        "DOMAIN-SUFFIX,proxifier.com,节点选择",
        "DOMAIN-SUFFIX,pt.im,节点选择",
        "DOMAIN-SUFFIX,pts.org.tw,节点选择",
        "DOMAIN-SUFFIX,pubu.com.tw,节点选择",
        "DOMAIN-SUFFIX,pubu.tw,节点选择",
        "DOMAIN-SUFFIX,pureapk.com,节点选择",
        "DOMAIN-SUFFIX,quora.com,节点选择",
        "DOMAIN-SUFFIX,quoracdn.net,节点选择",
        "DOMAIN-SUFFIX,qz.com,节点选择",
        "DOMAIN-SUFFIX,radio.garden,节点选择",
        "DOMAIN-SUFFIX,rakuten.co.jp,节点选择",
        "DOMAIN-SUFFIX,rarbgprx.org,节点选择",
        "DOMAIN-SUFFIX,reabble.com,节点选择",
        "DOMAIN-SUFFIX,readingtimes.com.tw,节点选择",
        "DOMAIN-SUFFIX,readmoo.com,节点选择",
        "DOMAIN-SUFFIX,redbubble.com,节点选择",
        "DOMAIN-SUFFIX,redd.it,节点选择",
        "DOMAIN-SUFFIX,reddit.com,节点选择",
        "DOMAIN-SUFFIX,redditmedia.com,节点选择",
        "DOMAIN-SUFFIX,resilio.com,节点选择",
        "DOMAIN-SUFFIX,reuters.com,节点选择",
        "DOMAIN-SUFFIX,reutersmedia.net,节点选择",
        "DOMAIN-SUFFIX,rfi.fr,节点选择",
        "DOMAIN-SUFFIX,rixcloud.com,节点选择",
        "DOMAIN-SUFFIX,roadshow.hk,节点选择",
        "DOMAIN-SUFFIX,rsshub.app,节点选择",
        "DOMAIN-SUFFIX,scmp.com,节点选择",
        "DOMAIN-SUFFIX,scribd.com,节点选择",
        "DOMAIN-SUFFIX,seatguru.com,节点选择",
        "DOMAIN-SUFFIX,shadowsocks.org,节点选择",
        "DOMAIN-SUFFIX,shindanmaker.com,节点选择",
        "DOMAIN-SUFFIX,shopee.tw,节点选择",
        "DOMAIN-SUFFIX,sina.com.hk,节点选择",
        "DOMAIN-SUFFIX,slideshare.net,节点选择",
        "DOMAIN-SUFFIX,softfamous.com,节点选择",
        "DOMAIN-SUFFIX,spiegel.de,节点选择",
        "DOMAIN-SUFFIX,ssrcloud.org,节点选择",
        "DOMAIN-SUFFIX,startpage.com,节点选择",
        "DOMAIN-SUFFIX,steamcommunity.com,节点选择",
        "DOMAIN-SUFFIX,steemit.com,节点选择",
        "DOMAIN-SUFFIX,steemitwallet.com,节点选择",
        "DOMAIN-SUFFIX,straitstimes.com,节点选择",
        "DOMAIN-SUFFIX,streamable.com,节点选择",
        "DOMAIN-SUFFIX,streema.com,节点选择",
        "DOMAIN-SUFFIX,t66y.com,节点选择",
        "DOMAIN-SUFFIX,tapatalk.com,节点选择",
        "DOMAIN-SUFFIX,teco-hk.org,节点选择",
        "DOMAIN-SUFFIX,teco-mo.org,节点选择",
        "DOMAIN-SUFFIX,teddysun.com,节点选择",
        "DOMAIN-SUFFIX,textnow.me,节点选择",
        "DOMAIN-SUFFIX,theguardian.com,节点选择",
        "DOMAIN-SUFFIX,theinitium.com,节点选择",
        "DOMAIN-SUFFIX,themoviedb.org,节点选择",
        "DOMAIN-SUFFIX,thetvdb.com,节点选择",
        "DOMAIN-SUFFIX,time.com,节点选择",
        "DOMAIN-SUFFIX,tineye.com,节点选择",
        "DOMAIN-SUFFIX,tiny.cc,节点选择",
        "DOMAIN-SUFFIX,tinyurl.com,节点选择",
        "DOMAIN-SUFFIX,torproject.org,节点选择",
        "DOMAIN-SUFFIX,tumblr.com,节点选择",
        "DOMAIN-SUFFIX,turbobit.net,节点选择",
        "DOMAIN-SUFFIX,tutanota.com,节点选择",
        "DOMAIN-SUFFIX,tvboxnow.com,节点选择",
        "DOMAIN-SUFFIX,udn.com,节点选择",
        "DOMAIN-SUFFIX,unseen.is,节点选择",
        "DOMAIN-SUFFIX,upmedia.mg,节点选择",
        "DOMAIN-SUFFIX,uptodown.com,节点选择",
        "DOMAIN-SUFFIX,urbandictionary.com,节点选择",
        "DOMAIN-SUFFIX,ustream.tv,节点选择",
        "DOMAIN-SUFFIX,uwants.com,节点选择",
        "DOMAIN-SUFFIX,v2fly.org,节点选择",
        "DOMAIN-SUFFIX,v2ray.com,节点选择",
        "DOMAIN-SUFFIX,viber.com,节点选择",
        "DOMAIN-SUFFIX,videopress.com,节点选择",
        "DOMAIN-SUFFIX,vimeo.com,节点选择",
        "DOMAIN-SUFFIX,voachinese.com,节点选择",
        "DOMAIN-SUFFIX,voanews.com,节点选择",
        "DOMAIN-SUFFIX,voxer.com,节点选择",
        "DOMAIN-SUFFIX,vzw.com,节点选择",
        "DOMAIN-SUFFIX,w3schools.com,节点选择",
        "DOMAIN-SUFFIX,washingtonpost.com,节点选择",
        "DOMAIN-SUFFIX,wattpad.com,节点选择",
        "DOMAIN-SUFFIX,whoer.net,节点选择",
        "DOMAIN-SUFFIX,wikileaks.org,节点选择",
        "DOMAIN-SUFFIX,wikimapia.org,节点选择",
        "DOMAIN-SUFFIX,wikimedia.org,节点选择",
        "DOMAIN-SUFFIX,wikinews.org,节点选择",
        "DOMAIN-SUFFIX,wikipedia.org,节点选择",
        "DOMAIN-SUFFIX,wikiquote.org,节点选择",
        "DOMAIN-SUFFIX,wikiwand.com,节点选择",
        "DOMAIN-SUFFIX,winudf.com,节点选择",
        "DOMAIN-SUFFIX,wire.com,节点选择",
        "DOMAIN-SUFFIX,wn.com,节点选择",
        "DOMAIN-SUFFIX,wordpress.com,节点选择",
        "DOMAIN-SUFFIX,workflow.is,节点选择",
        "DOMAIN-SUFFIX,worldcat.org,节点选择",
        "DOMAIN-SUFFIX,wsj.com,节点选择",
        "DOMAIN-SUFFIX,wsj.net,节点选择",
        "DOMAIN-SUFFIX,xhamster.com,节点选择",
        "DOMAIN-SUFFIX,xn--90wwvt03e.com,节点选择",
        "DOMAIN-SUFFIX,xn--i2ru8q2qg.com,节点选择",
        "DOMAIN-SUFFIX,xnxx.com,节点选择",
        "DOMAIN-SUFFIX,xvideos.com,节点选择",
        "DOMAIN-SUFFIX,yahoo.com,节点选择",
        "DOMAIN-SUFFIX,yandex.ru,节点选择",
        "DOMAIN-SUFFIX,ycombinator.com,节点选择",
        "DOMAIN-SUFFIX,yesasia.com,节点选择",
        "DOMAIN-SUFFIX,yes-news.com,节点选择",
        "DOMAIN-SUFFIX,yomiuri.co.jp,节点选择",
        "DOMAIN-SUFFIX,you-get.org,节点选择",
        "DOMAIN-SUFFIX,zaobao.com,节点选择",
        "DOMAIN-SUFFIX,zb.com,节点选择",
        "DOMAIN-SUFFIX,zello.com,节点选择",
        "DOMAIN-SUFFIX,zeronet.io,节点选择",
        "DOMAIN-SUFFIX,zoom.us,节点选择",
        "DOMAIN,cc.tvbs.com.tw,节点选择",
        "DOMAIN,ocsp.int-x3.letsencrypt.org,节点选择",
        "DOMAIN,search.avira.com,节点选择",
        "DOMAIN,us.weibo.com,节点选择",
        "DOMAIN-KEYWORD,.pinterest.,节点选择",
        "DOMAIN-SUFFIX,edu,节点选择",
        "DOMAIN-SUFFIX,gov,节点选择",
        "DOMAIN-SUFFIX,mil,节点选择",
        "DOMAIN-SUFFIX,google,节点选择",
        "DOMAIN-SUFFIX,abc.xyz,节点选择",
        "DOMAIN-SUFFIX,advertisercommunity.com,节点选择",
        "DOMAIN-SUFFIX,ampproject.org,节点选择",
        "DOMAIN-SUFFIX,android.com,节点选择",
        "DOMAIN-SUFFIX,androidify.com,节点选择",
        "DOMAIN-SUFFIX,autodraw.com,节点选择",
        "DOMAIN-SUFFIX,capitalg.com,节点选择",
        "DOMAIN-SUFFIX,certificate-transparency.org,节点选择",
        "DOMAIN-SUFFIX,chrome.com,节点选择",
        "DOMAIN-SUFFIX,chromeexperiments.com,节点选择",
        "DOMAIN-SUFFIX,chromestatus.com,节点选择",
        "DOMAIN-SUFFIX,chromium.org,节点选择",
        "DOMAIN-SUFFIX,creativelab5.com,节点选择",
        "DOMAIN-SUFFIX,debug.com,节点选择",
        "DOMAIN-SUFFIX,deepmind.com,节点选择",
        "DOMAIN-SUFFIX,dialogflow.com,节点选择",
        "DOMAIN-SUFFIX,firebaseio.com,节点选择",
        "DOMAIN-SUFFIX,getmdl.io,节点选择",
        "DOMAIN-SUFFIX,ggpht.com,节点选择",
        "DOMAIN-SUFFIX,googleapis.cn,节点选择",
        "DOMAIN-SUFFIX,gmail.com,节点选择",
        "DOMAIN-SUFFIX,gmodules.com,节点选择",
        "DOMAIN-SUFFIX,godoc.org,节点选择",
        "DOMAIN-SUFFIX,golang.org,节点选择",
        "DOMAIN-SUFFIX,gstatic.com,节点选择",
        "DOMAIN-SUFFIX,gv.com,节点选择",
        "DOMAIN-SUFFIX,gwtproject.org,节点选择",
        "DOMAIN-SUFFIX,itasoftware.com,节点选择",
        "DOMAIN-SUFFIX,madewithcode.com,节点选择",
        "DOMAIN-SUFFIX,material.io,节点选择",
        "DOMAIN-SUFFIX,page.link,节点选择",
        "DOMAIN-SUFFIX,polymer-project.org,节点选择",
        "DOMAIN-SUFFIX,recaptcha.net,节点选择",
        "DOMAIN-SUFFIX,shattered.io,节点选择",
        "DOMAIN-SUFFIX,synergyse.com,节点选择",
        "DOMAIN-SUFFIX,telephony.goog,节点选择",
        "DOMAIN-SUFFIX,tensorflow.org,节点选择",
        "DOMAIN-SUFFIX,tfhub.dev,节点选择",
        "DOMAIN-SUFFIX,tiltbrush.com,节点选择",
        "DOMAIN-SUFFIX,waveprotocol.org,节点选择",
        "DOMAIN-SUFFIX,waymo.com,节点选择",
        "DOMAIN-SUFFIX,webmproject.org,节点选择",
        "DOMAIN-SUFFIX,webrtc.org,节点选择",
        "DOMAIN-SUFFIX,whatbrowser.org,节点选择",
        "DOMAIN-SUFFIX,widevine.com,节点选择",
        "DOMAIN-SUFFIX,x.company,节点选择",
        "DOMAIN-SUFFIX,youtu.be,节点选择",
        "DOMAIN-SUFFIX,yt.be,节点选择",
        "DOMAIN-SUFFIX,ytimg.com,节点选择",
        "DOMAIN-SUFFIX,t.me,节点选择",
        "DOMAIN-SUFFIX,tdesktop.com,节点选择",
        "DOMAIN-SUFFIX,telegram.me,节点选择",
        "DOMAIN-SUFFIX,telesco.pe,节点选择",
        "DOMAIN-KEYWORD,.facebook.,节点选择",
        "DOMAIN-SUFFIX,facebookmail.com,节点选择",
        "DOMAIN-SUFFIX,noxinfluencer.com,节点选择",
        "DOMAIN-SUFFIX,smartmailcloud.com,节点选择",
        "DOMAIN-SUFFIX,weebly.com,节点选择",
        "DOMAIN-SUFFIX,twitter.jp,节点选择",
        "DOMAIN-SUFFIX,appsto.re,节点选择",
        "DOMAIN,books.itunes.apple.com,节点选择",
        "DOMAIN,apps.apple.com,节点选择",
        "DOMAIN,itunes.apple.com,节点选择",
        "DOMAIN,api-glb-sea.smoot.apple.com,节点选择",
        "DOMAIN-SUFFIX,smoot.apple.com,节点选择",
        "DOMAIN,lookup-api.apple.com,节点选择",
        "DOMAIN,beta.music.apple.com,节点选择",
        "DOMAIN-SUFFIX,bing.com,节点选择",
        "DOMAIN-SUFFIX,cccat.io,节点选择",
        "DOMAIN-SUFFIX,dubox.com,节点选择",
        "DOMAIN-SUFFIX,duboxcdn.com,节点选择",
        "DOMAIN-SUFFIX,ifixit.com,节点选择",
        "DOMAIN-SUFFIX,mangakakalot.com,节点选择",
        "DOMAIN-SUFFIX,shopeemobile.com,节点选择",
        "DOMAIN-SUFFIX,cloudcone.com.cn,节点选择",
        "DOMAIN-SUFFIX,inkbunny.net,节点选择",
        "DOMAIN-SUFFIX,metapix.net,节点选择",
        "DOMAIN-SUFFIX,s3.amazonaws.com,节点选择",
        "DOMAIN-SUFFIX,zaobao.com.sg,节点选择",
        "DOMAIN,international-gfe.download.nvidia.com,节点选择",
        "DOMAIN,ocsp.apple.com,节点选择",
        "DOMAIN,store-images.s-microsoft.com,节点选择",
        "DOMAIN-SUFFIX,qhres.com,DIRECT",
        "DOMAIN-SUFFIX,qhimg.com,DIRECT",
        "DOMAIN-SUFFIX,alibaba.com,DIRECT",
        "DOMAIN-SUFFIX,alibabausercontent.com,DIRECT",
        "DOMAIN-SUFFIX,alicdn.com,DIRECT",
        "DOMAIN-SUFFIX,alikunlun.com,DIRECT",
        "DOMAIN-SUFFIX,alipay.com,DIRECT",
        "DOMAIN-SUFFIX,amap.com,DIRECT",
        "DOMAIN-SUFFIX,autonavi.com,DIRECT",
        "DOMAIN-SUFFIX,dingtalk.com,DIRECT",
        "DOMAIN-SUFFIX,mxhichina.com,DIRECT",
        "DOMAIN-SUFFIX,soku.com,DIRECT",
        "DOMAIN-SUFFIX,taobao.com,DIRECT",
        "DOMAIN-SUFFIX,tmall.com,DIRECT",
        "DOMAIN-SUFFIX,tmall.hk,DIRECT",
        "DOMAIN-SUFFIX,ykimg.com,DIRECT",
        "DOMAIN-SUFFIX,youku.com,DIRECT",
        "DOMAIN-SUFFIX,xiami.com,DIRECT",
        "DOMAIN-SUFFIX,xiami.net,DIRECT",
        "DOMAIN-SUFFIX,aaplimg.com,DIRECT",
        "DOMAIN-SUFFIX,apple.co,DIRECT",
        "DOMAIN-SUFFIX,apple.com,DIRECT",
        "DOMAIN-SUFFIX,apple-cloudkit.com,DIRECT",
        "DOMAIN-SUFFIX,appstore.com,DIRECT",
        "DOMAIN-SUFFIX,cdn-apple.com,DIRECT",
        "DOMAIN-SUFFIX,icloud.com,DIRECT",
        "DOMAIN-SUFFIX,icloud-content.com,DIRECT",
        "DOMAIN-SUFFIX,me.com,DIRECT",
        "DOMAIN-SUFFIX,mzstatic.com,DIRECT",
        "DOMAIN-KEYWORD,apple.com.akadns.net,DIRECT",
        "DOMAIN-KEYWORD,icloud.com.akadns.net,DIRECT",
        "DOMAIN-SUFFIX,baidu.com,DIRECT",
        "DOMAIN-SUFFIX,baidubcr.com,DIRECT",
        "DOMAIN-SUFFIX,baidupan.com,DIRECT",
        "DOMAIN-SUFFIX,baidupcs.com,DIRECT",
        "DOMAIN-SUFFIX,bdimg.com,DIRECT",
        "DOMAIN-SUFFIX,bdstatic.com,DIRECT",
        "DOMAIN-SUFFIX,yunjiasu-cdn.net,DIRECT",
        "DOMAIN-SUFFIX,acgvideo.com,DIRECT",
        "DOMAIN-SUFFIX,biliapi.com,DIRECT",
        "DOMAIN-SUFFIX,biliapi.net,DIRECT",
        "DOMAIN-SUFFIX,bilibili.com,DIRECT",
        "DOMAIN-SUFFIX,bilibili.tv,DIRECT",
        "DOMAIN-SUFFIX,hdslb.com,DIRECT",
        "DOMAIN-SUFFIX,feiliao.com,DIRECT",
        "DOMAIN-SUFFIX,pstatp.com,DIRECT",
        "DOMAIN-SUFFIX,snssdk.com,DIRECT",
        "DOMAIN-SUFFIX,iesdouyin.com,DIRECT",
        "DOMAIN-SUFFIX,toutiao.com,DIRECT",
        "DOMAIN-SUFFIX,cctv.com,DIRECT",
        "DOMAIN-SUFFIX,cctvpic.com,DIRECT",
        "DOMAIN-SUFFIX,livechina.com,DIRECT",
        "DOMAIN-SUFFIX,didialift.com,DIRECT",
        "DOMAIN-SUFFIX,didiglobal.com,DIRECT",
        "DOMAIN-SUFFIX,udache.com,DIRECT",
        "DOMAIN-SUFFIX,21cn.com,DIRECT",
        "DOMAIN-SUFFIX,hitv.com,DIRECT",
        "DOMAIN-SUFFIX,mgtv.com,DIRECT",
        "DOMAIN-SUFFIX,iqiyi.com,DIRECT",
        "DOMAIN-SUFFIX,iqiyipic.com,DIRECT",
        "DOMAIN-SUFFIX,71.am,DIRECT",
        "DOMAIN-SUFFIX,jd.com,DIRECT",
        "DOMAIN-SUFFIX,jd.hk,DIRECT",
        "DOMAIN-SUFFIX,jdpay.com,DIRECT",
        "DOMAIN-SUFFIX,360buyimg.com,DIRECT",
        "DOMAIN-SUFFIX,iciba.com,DIRECT",
        "DOMAIN-SUFFIX,ksosoft.com,DIRECT",
        "DOMAIN-SUFFIX,meitu.com,DIRECT",
        "DOMAIN-SUFFIX,meitudata.com,DIRECT",
        "DOMAIN-SUFFIX,meitustat.com,DIRECT",
        "DOMAIN-SUFFIX,meipai.com,DIRECT",
        "DOMAIN-SUFFIX,dianping.com,DIRECT",
        "DOMAIN-SUFFIX,dpfile.com,DIRECT",
        "DOMAIN-SUFFIX,meituan.com,DIRECT",
        "DOMAIN-SUFFIX,meituan.net,DIRECT",
        "DOMAIN-SUFFIX,duokan.com,DIRECT",
        "DOMAIN-SUFFIX,mi.com,DIRECT",
        "DOMAIN-SUFFIX,mi-img.com,DIRECT",
        "DOMAIN-SUFFIX,miui.com,DIRECT",
        "DOMAIN-SUFFIX,miwifi.com,DIRECT",
        "DOMAIN-SUFFIX,xiaomi.com,DIRECT",
        "DOMAIN-SUFFIX,xiaomi.net,DIRECT",
        "DOMAIN-SUFFIX,hotmail.com,DIRECT",
        "DOMAIN-SUFFIX,microsoft.com,DIRECT",
        "DOMAIN-SUFFIX,msecnd.net,DIRECT",
        "DOMAIN-SUFFIX,office365.com,DIRECT",
        "DOMAIN-SUFFIX,outlook.com,DIRECT",
        "DOMAIN-SUFFIX,s-microsoft.com,DIRECT",
        "DOMAIN-SUFFIX,visualstudio.com,DIRECT",
        "DOMAIN-SUFFIX,windows.com,DIRECT",
        "DOMAIN-SUFFIX,windowsupdate.com,DIRECT",
        "DOMAIN-SUFFIX,163.com,DIRECT",
        "DOMAIN-SUFFIX,126.com,DIRECT",
        "DOMAIN-SUFFIX,126.net,DIRECT",
        "DOMAIN-SUFFIX,127.net,DIRECT",
        "DOMAIN-SUFFIX,163yun.com,DIRECT",
        "DOMAIN-SUFFIX,lofter.com,DIRECT",
        "DOMAIN-SUFFIX,netease.com,DIRECT",
        "DOMAIN-SUFFIX,ydstatic.com,DIRECT",
        "DOMAIN-SUFFIX,paypal.com,DIRECT",
        "DOMAIN-SUFFIX,paypal.me,DIRECT",
        "DOMAIN-SUFFIX,paypalobjects.com,DIRECT",
        "DOMAIN-SUFFIX,sina.com,DIRECT",
        "DOMAIN-SUFFIX,weibo.com,DIRECT",
        "DOMAIN-SUFFIX,weibocdn.com,DIRECT",
        "DOMAIN-SUFFIX,sohu.com,DIRECT",
        "DOMAIN-SUFFIX,sohucs.com,DIRECT",
        "DOMAIN-SUFFIX,sohu-inc.com,DIRECT",
        "DOMAIN-SUFFIX,v-56.com,DIRECT",
        "DOMAIN-SUFFIX,sogo.com,DIRECT",
        "DOMAIN-SUFFIX,sogou.com,DIRECT",
        "DOMAIN-SUFFIX,sogoucdn.com,DIRECT",
        "DOMAIN-SUFFIX,steamcontent.com,DIRECT",
        "DOMAIN-SUFFIX,steampowered.com,DIRECT",
        "DOMAIN-SUFFIX,steamstatic.com,DIRECT",
        "DOMAIN-SUFFIX,gtimg.com,DIRECT",
        "DOMAIN-SUFFIX,idqqimg.com,DIRECT",
        "DOMAIN-SUFFIX,igamecj.com,DIRECT",
        "DOMAIN-SUFFIX,myapp.com,DIRECT",
        "DOMAIN-SUFFIX,myqcloud.com,DIRECT",
        "DOMAIN-SUFFIX,qq.com,DIRECT",
        "DOMAIN-SUFFIX,qqmail.com,DIRECT",
        "DOMAIN-SUFFIX,servicewechat.com,DIRECT",
        "DOMAIN-SUFFIX,tencent.com,DIRECT",
        "DOMAIN-SUFFIX,tencent-cloud.net,DIRECT",
        "DOMAIN-SUFFIX,tenpay.com,DIRECT",
        "DOMAIN-SUFFIX,wechat.com,DIRECT",
        "DOMAIN,file-igamecj.akamaized.net,DIRECT",
        "DOMAIN-SUFFIX,ccgslb.com,DIRECT",
        "DOMAIN-SUFFIX,ccgslb.net,DIRECT",
        "DOMAIN-SUFFIX,chinanetcenter.com,DIRECT",
        "DOMAIN-SUFFIX,meixincdn.com,DIRECT",
        "DOMAIN-SUFFIX,ourdvs.com,DIRECT",
        "DOMAIN-SUFFIX,staticdn.net,DIRECT",
        "DOMAIN-SUFFIX,wangsu.com,DIRECT",
        "DOMAIN-SUFFIX,ipip.net,DIRECT",
        "DOMAIN-SUFFIX,ip.la,DIRECT",
        "DOMAIN-SUFFIX,ip.sb,DIRECT",
        "DOMAIN-SUFFIX,ip-cdn.com,DIRECT",
        "DOMAIN-SUFFIX,ipv6-test.com,DIRECT",
        "DOMAIN-SUFFIX,myip.la,DIRECT",
        "DOMAIN-SUFFIX,test-ipv6.com,DIRECT",
        "DOMAIN-SUFFIX,whatismyip.com,DIRECT",
        "DOMAIN,ip.istatmenus.app,DIRECT",
        "DOMAIN,sms.imagetasks.com,DIRECT",
        "DOMAIN-SUFFIX,netspeedtestmaster.com,DIRECT",
        "DOMAIN,speedtest.macpaw.com,DIRECT",
        "DOMAIN-SUFFIX,acg.rip,DIRECT",
        "DOMAIN-SUFFIX,animebytes.tv,DIRECT",
        "DOMAIN-SUFFIX,awesome-hd.me,DIRECT",
        "DOMAIN-SUFFIX,broadcasthe.net,DIRECT",
        "DOMAIN-SUFFIX,chdbits.co,DIRECT",
        "DOMAIN-SUFFIX,classix-unlimited.co.uk,DIRECT",
        "DOMAIN-SUFFIX,comicat.org,DIRECT",
        "DOMAIN-SUFFIX,empornium.me,DIRECT",
        "DOMAIN-SUFFIX,gazellegames.net,DIRECT",
        "DOMAIN-SUFFIX,hdbits.org,DIRECT",
        "DOMAIN-SUFFIX,hdchina.org,DIRECT",
        "DOMAIN-SUFFIX,hddolby.com,DIRECT",
        "DOMAIN-SUFFIX,hdhome.org,DIRECT",
        "DOMAIN-SUFFIX,hdsky.me,DIRECT",
        "DOMAIN-SUFFIX,icetorrent.org,DIRECT",
        "DOMAIN-SUFFIX,jpopsuki.eu,DIRECT",
        "DOMAIN-SUFFIX,keepfrds.com,DIRECT",
        "DOMAIN-SUFFIX,madsrevolution.net,DIRECT",
        "DOMAIN-SUFFIX,morethan.tv,DIRECT",
        "DOMAIN-SUFFIX,m-team.cc,DIRECT",
        "DOMAIN-SUFFIX,myanonamouse.net,DIRECT",
        "DOMAIN-SUFFIX,nanyangpt.com,DIRECT",
        "DOMAIN-SUFFIX,ncore.cc,DIRECT",
        "DOMAIN-SUFFIX,open.cd,DIRECT",
        "DOMAIN-SUFFIX,ourbits.club,DIRECT",
        "DOMAIN-SUFFIX,passthepopcorn.me,DIRECT",
        "DOMAIN-SUFFIX,privatehd.to,DIRECT",
        "DOMAIN-SUFFIX,pterclub.com,DIRECT",
        "DOMAIN-SUFFIX,redacted.ch,DIRECT",
        "DOMAIN-SUFFIX,springsunday.net,DIRECT",
        "DOMAIN-SUFFIX,tjupt.org,DIRECT",
        "DOMAIN-SUFFIX,totheglory.im,DIRECT",
        "DOMAIN-SUFFIX,cn,DIRECT",
        "DOMAIN-SUFFIX,115.com,DIRECT",
        "DOMAIN-SUFFIX,360in.com,DIRECT",
        "DOMAIN-SUFFIX,51ym.me,DIRECT",
        "DOMAIN-SUFFIX,8686c.com,DIRECT",
        "DOMAIN-SUFFIX,99.com,DIRECT",
        "DOMAIN-SUFFIX,abchina.com,DIRECT",
        "DOMAIN-SUFFIX,accuweather.com,DIRECT",
        "DOMAIN-SUFFIX,aicoinstorge.com,DIRECT",
        "DOMAIN-SUFFIX,air-matters.com,DIRECT",
        "DOMAIN-SUFFIX,air-matters.io,DIRECT",
        "DOMAIN-SUFFIX,aixifan.com,DIRECT",
        "DOMAIN-SUFFIX,amd.com,DIRECT",
        "DOMAIN-SUFFIX,b612.net,DIRECT",
        "DOMAIN-SUFFIX,bdatu.com,DIRECT",
        "DOMAIN-SUFFIX,beitaichufang.com,DIRECT",
        "DOMAIN-SUFFIX,booking.com,DIRECT",
        "DOMAIN-SUFFIX,bstatic.com,DIRECT",
        "DOMAIN-SUFFIX,cailianpress.com,DIRECT",
        "DOMAIN-SUFFIX,camera360.com,DIRECT",
        "DOMAIN-SUFFIX,chaoxing.com,DIRECT",
        "DOMAIN-SUFFIX,chaoxing.com,DIRECT",
        "DOMAIN-SUFFIX,chinaso.com,DIRECT",
        "DOMAIN-SUFFIX,chuimg.com,DIRECT",
        "DOMAIN-SUFFIX,chunyu.mobi,DIRECT",
        "DOMAIN-SUFFIX,cmbchina.com,DIRECT",
        "DOMAIN-SUFFIX,cmbimg.com,DIRECT",
        "DOMAIN-SUFFIX,ctrip.com,DIRECT",
        "DOMAIN-SUFFIX,dfcfw.com,DIRECT",
        "DOMAIN-SUFFIX,dji.net,DIRECT",
        "DOMAIN-SUFFIX,docschina.org,DIRECT",
        "DOMAIN-SUFFIX,douban.com,DIRECT",
        "DOMAIN-SUFFIX,doubanio.com,DIRECT",
        "DOMAIN-SUFFIX,douyu.com,DIRECT",
        "DOMAIN-SUFFIX,dxycdn.com,DIRECT",
        "DOMAIN-SUFFIX,dytt8.net,DIRECT",
        "DOMAIN-SUFFIX,eastmoney.com,DIRECT",
        "DOMAIN-SUFFIX,eudic.net,DIRECT",
        "DOMAIN-SUFFIX,feng.com,DIRECT",
        "DOMAIN-SUFFIX,fengkongcloud.com,DIRECT",
        "DOMAIN-SUFFIX,frdic.com,DIRECT",
        "DOMAIN-SUFFIX,futu5.com,DIRECT",
        "DOMAIN-SUFFIX,futunn.com,DIRECT",
        "DOMAIN-SUFFIX,gandi.net,DIRECT",
        "DOMAIN-SUFFIX,gcores.com,DIRECT",
        "DOMAIN-SUFFIX,geilicdn.com,DIRECT",
        "DOMAIN-SUFFIX,getpricetag.com,DIRECT",
        "DOMAIN-SUFFIX,gifshow.com,DIRECT",
        "DOMAIN-SUFFIX,godic.net,DIRECT",
        "DOMAIN-SUFFIX,hicloud.com,DIRECT",
        "DOMAIN-SUFFIX,hongxiu.com,DIRECT",
        "DOMAIN-SUFFIX,hostbuf.com,DIRECT",
        "DOMAIN-SUFFIX,huxiucdn.com,DIRECT",
        "DOMAIN-SUFFIX,huya.com,DIRECT",
        "DOMAIN-SUFFIX,ibm.com,DIRECT",
        "DOMAIN-SUFFIX,infinitynewtab.com,DIRECT",
        "DOMAIN-SUFFIX,ithome.com,DIRECT",
        "DOMAIN-SUFFIX,java.com,DIRECT",
        "DOMAIN-SUFFIX,jianguoyun.com,DIRECT",
        "DOMAIN-SUFFIX,jianshu.com,DIRECT",
        "DOMAIN-SUFFIX,jianshu.io,DIRECT",
        "DOMAIN-SUFFIX,jidian.im,DIRECT",
        "DOMAIN-SUFFIX,kaiyanapp.com,DIRECT",
        "DOMAIN-SUFFIX,kaspersky-labs.com,DIRECT",
        "DOMAIN-SUFFIX,keepcdn.com,DIRECT",
        "DOMAIN-SUFFIX,kkmh.com,DIRECT",
        "DOMAIN-SUFFIX,lanzous.com,DIRECT",
        "DOMAIN-SUFFIX,licdn.com,DIRECT",
        "DOMAIN-SUFFIX,luojilab.com,DIRECT",
        "DOMAIN-SUFFIX,maoyan.com,DIRECT",
        "DOMAIN-SUFFIX,maoyun.tv,DIRECT",
        "DOMAIN-SUFFIX,mls-cdn.com,DIRECT",
        "DOMAIN-SUFFIX,mobike.com,DIRECT",
        "DOMAIN-SUFFIX,moke.com,DIRECT",
        "DOMAIN-SUFFIX,mubu.com,DIRECT",
        "DOMAIN-SUFFIX,myzaker.com,DIRECT",
        "DOMAIN-SUFFIX,nim-lang-cn.org,DIRECT",
        "DOMAIN-SUFFIX,nvidia.com,DIRECT",
        "DOMAIN-SUFFIX,oracle.com,DIRECT",
        "DOMAIN-SUFFIX,originlab.com,DIRECT",
        "DOMAIN-SUFFIX,qdaily.com,DIRECT",
        "DOMAIN-SUFFIX,qidian.com,DIRECT",
        "DOMAIN-SUFFIX,qyer.com,DIRECT",
        "DOMAIN-SUFFIX,qyerstatic.com,DIRECT",
        "DOMAIN-SUFFIX,raychase.net,DIRECT",
        "DOMAIN-SUFFIX,ronghub.com,DIRECT",
        "DOMAIN-SUFFIX,ruguoapp.com,DIRECT",
        "DOMAIN-SUFFIX,sankuai.com,DIRECT",
        "DOMAIN-SUFFIX,scomper.me,DIRECT",
        "DOMAIN-SUFFIX,seafile.com,DIRECT",
        "DOMAIN-SUFFIX,sm.ms,DIRECT",
        "DOMAIN-SUFFIX,smzdm.com,DIRECT",
        "DOMAIN-SUFFIX,snapdrop.net,DIRECT",
        "DOMAIN-SUFFIX,snwx.com,DIRECT",
        "DOMAIN-SUFFIX,s-reader.com,DIRECT",
        "DOMAIN-SUFFIX,sspai.com,DIRECT",
        "DOMAIN-SUFFIX,subhd.tv,DIRECT",
        "DOMAIN-SUFFIX,takungpao.com,DIRECT",
        "DOMAIN-SUFFIX,teamviewer.com,DIRECT",
        "DOMAIN-SUFFIX,tianyancha.com,DIRECT",
        "DOMAIN-SUFFIX,tophub.today,DIRECT",
        "DOMAIN-SUFFIX,udacity.com,DIRECT",
        "DOMAIN-SUFFIX,uning.com,DIRECT",
        "DOMAIN-SUFFIX,weather.com,DIRECT",
        "DOMAIN-SUFFIX,weico.cc,DIRECT",
        "DOMAIN-SUFFIX,weidian.com,DIRECT",
        "DOMAIN-SUFFIX,xiachufang.com,DIRECT",
        "DOMAIN-SUFFIX,xiaoka.tv,DIRECT",
        "DOMAIN-SUFFIX,ximalaya.com,DIRECT",
        "DOMAIN-SUFFIX,xinhuanet.com,DIRECT",
        "DOMAIN-SUFFIX,xmcdn.com,DIRECT",
        "DOMAIN-SUFFIX,yangkeduo.com,DIRECT",
        "DOMAIN-SUFFIX,yizhibo.com,DIRECT",
        "DOMAIN-SUFFIX,zhangzishi.cc,DIRECT",
        "DOMAIN-SUFFIX,zhihu.com,DIRECT",
        "DOMAIN-SUFFIX,zhihuishu.com,DIRECT",
        "DOMAIN-SUFFIX,zhimg.com,DIRECT",
        "DOMAIN-SUFFIX,zhuihd.com,DIRECT",
        "DOMAIN,download.jetbrains.com,DIRECT",
        "DOMAIN,images-cn.ssl-images-amazon.com,DIRECT",
        "DOMAIN-SUFFIX,local,DIRECT",
        "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
        "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
        "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
        "IP-CIDR6,::1/128,DIRECT,no-resolve",
        "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
        "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
        "IP-CIDR6,fd00::/8,DIRECT,no-resolve",
        "GEOIP,CN,DIRECT",
        "MATCH,节点选择"
    ]
}


def _decode_base64_text(data):
    """宽松 base64 解码：自动补齐 padding，兼容 urlsafe 与标准字母表，失败返回 None"""
    if not data:
        return None
    if isinstance(data, str):
        data = data.encode('utf-8')
    data = data.strip() + b'=' * (-len(data.strip()) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(data).decode('utf-8')
        except Exception:
            continue
    return None


def _fallback_name(parts, default='node'):
    """链接缺少 #fragment 时，用 host:port 兜底命名"""
    if parts.fragment:
        return urllib.parse.unquote(parts.fragment)
    if parts.hostname:
        return f"{parts.hostname}:{parts.port}" if parts.port else parts.hostname
    return default


# 解析 Hysteria2 链接
def parse_hysteria2_link(link):
    # hysteria2:// 与 hy2:// 前缀长度不同，用 urlsplit 统一处理
    parts = urllib.parse.urlsplit(link)
    if not parts.hostname or not parts.port:
        return None
    # userinfo 整体即密码，同时兼容 user:pass 写法
    password = urllib.parse.unquote(parts.password if parts.password is not None else (parts.username or ''))
    query_params = urllib.parse.parse_qs(parts.query)
    insecure = query_params.get('insecure', ['0'])[0] in ('1', 'true')

    return {
        "name": _fallback_name(parts),
        "server": parts.hostname,
        "port": parts.port,
        "type": "hysteria2",
        "password": password,
        "auth": password,
        "sni": query_params.get('sni', [''])[0],
        # insecure=1 表示跳过证书校验，语义与 skip-cert-verify 一致
        "skip-cert-verify": insecure,
        "client-fingerprint": "chrome"
    }


# 解析 Shadowsocks 链接
def parse_ss_link(link):
    parts = urllib.parse.urlsplit(link)

    if parts.hostname and parts.port:
        # ss://base64(method:password)@host:port  或  ss://method:password@host:port
        if parts.password is not None:
            cipher = urllib.parse.unquote(parts.username or '')
            password = urllib.parse.unquote(parts.password)
        else:
            decoded = _decode_base64_text(parts.username)
            decoded = urllib.parse.unquote(decoded) if decoded else decoded
            if not decoded or ':' not in decoded:
                return None
            cipher, _, password = decoded.partition(':')
        server, port = parts.hostname, parts.port
    else:
        # 老式整体编码 ss://base64(method:password@host:port)
        # 标准 base64 可能包含 '/'，urlsplit 会把它切进 path，这里拼回来
        decoded = _decode_base64_text(parts.netloc + parts.path)
        if not decoded or '@' not in decoded:
            return None
        userinfo, _, hostinfo = decoded.rpartition('@')
        cipher, _, password = userinfo.partition(':')
        server, _, port_str = hostinfo.rpartition(':')
        if not port_str.isdigit():
            return None
        port = int(port_str)

    if not cipher or not server:
        return None

    return {
        "name": _fallback_name(parts),
        "type": "ss",
        "server": server,
        "port": int(port),
        "cipher": cipher,
        "password": password,
        "udp": True
    }


# 解析 Trojan 链接
def parse_trojan_link(link):
    parts = urllib.parse.urlsplit(link)
    if not parts.hostname or not parts.port:
        return None
    password = urllib.parse.unquote(parts.password if parts.password is not None else (parts.username or ''))
    query = urllib.parse.parse_qs(parts.query)

    return {
        "name": _fallback_name(parts),
        "type": "trojan",
        "server": parts.hostname,
        "port": parts.port,
        "password": password,
        "sni": query.get("sni", [""])[0],
        "skip-cert-verify": query.get("skip-cert-verify", ["false"])[0] == "true"
    }


# 解析 VLESS 链接
def parse_vless_link(link):
    parts = urllib.parse.urlsplit(link)
    if not parts.hostname or not parts.port or not parts.username:
        return None
    query = urllib.parse.parse_qs(parts.query)
    security = query.get("security", ["none"])[0]
    network = query.get("type", ["tcp"])[0]
    sni = query.get("sni", [""])[0]

    node = {
        "name": _fallback_name(parts),
        "type": "vless",
        "server": parts.hostname,
        "port": parts.port,
        "uuid": urllib.parse.unquote(parts.username),
        "security": security,
        "tls": security in ("tls", "reality"),
        "sni": sni,
        "skip-cert-verify": query.get("skip-cert-verify", ["false"])[0] == "true",
        "network": network,
        "udp": True,
    }

    if query.get("flow"):
        node["flow"] = query["flow"][0]
    if query.get("fp"):
        node["client-fingerprint"] = query["fp"][0]
    if security == "reality":
        node["reality-opts"] = {
            "public-key": query.get("pbk", [""])[0],
            "short-id": query.get("sid", [""])[0],
        }
    if network == "ws":
        node["ws-opts"] = {
            "path": query.get("path", ["/"])[0],
            "headers": {"Host": query.get("host", [sni])[0]},
        }
    elif network == "grpc":
        node["grpc-opts"] = {"grpc-service-name": query.get("serviceName", [""])[0]}

    return node


# 解析 VMESS 链接
def parse_vmess_link(link):
    decoded_link = _decode_base64_text(link[8:])
    if not decoded_link:
        return None
    try:
        vmess_info = json.loads(decoded_link)
    except ValueError:
        return None
    if not vmess_info.get("add") or not vmess_info.get("port"):
        return None

    return {
        "name": urllib.parse.unquote(vmess_info.get("ps") or "vmess"),
        "type": "vmess",
        "server": vmess_info["add"],
        "port": int(vmess_info["port"]),
        "uuid": vmess_info["id"],
        "alterId": int(vmess_info.get("aid", 0) or 0),
        "cipher": "auto",
        "network": vmess_info.get("net", "tcp"),
        "tls": vmess_info.get("tls", "") == "tls",
        "sni": vmess_info.get("sni", ""),
        "ws-opts": {
            "path": vmess_info.get("path", ""),
            "headers": {
                "Host": vmess_info.get("host", "")
            }
        } if vmess_info.get("net", "tcp") == "ws" else {}
    }


# 解析ss订阅源
def parse_ss_sub(link):
    """请求 |ss 订阅（返回 JSON 数组），任何异常都返回空列表"""
    try:
        response = requests.get(link, headers=headers, verify=False,
                                allow_redirects=True, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"请求错误: {e}")
        return []

    if not isinstance(data, list):
        return []

    new_links = []
    for item in data:
        try:
            new_links.append({"name": str(item['remarks']), "type": "ss", "server": item['server'],
                              "port": int(item['server_port']), "cipher": item['method'],
                              "password": item['password'], "udp": True})
        except (KeyError, TypeError, ValueError):
            continue
    return new_links


def parse_md_link(link):
    try:
        # 发送请求并获取内容
        response = requests.get(link, timeout=FETCH_TIMEOUT)
        response.raise_for_status()  # 检查请求是否成功
        content = response.text
        content = urllib.parse.unquote(content)
        # 定义正则表达式模式，匹配所需的协议链接
        pattern = r'(?:vless|vmess|trojan|hysteria2|hy2|ss):\/\/[^#\s]*(?:#[^\s]*)?'

        # 使用re.findall()提取所有匹配的链接
        matches = re.findall(pattern, content)
        return matches

    except requests.RequestException as e:
        print(f"请求错误: {e}")
        return []


# js渲染页面
JS_RENDER_TIMEOUT = 30  # 渲染超时（秒）；pyppeteer 的 render(timeout=) 在页面一直加载时不会生效，必须由外部强制结束


def _js_render_in_process(url, result_queue):
    """在子进程里跑 pyppeteer。chromium 卡死时可以直接 kill 子进程，不会拖住主流水线。"""
    session = None
    try:
        browser_args = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                        '--disable-software-rasterizer', '--disable-setuid-sandbox']
        session = HTMLSession(browser_args=browser_args)
        r = session.get(url, headers=headers, timeout=10, verify=False)
        r.html.render(timeout=10)
        result_queue.put(r.html.text)
    except Exception as e:
        result_queue.put(f'__JS_RENDER_ERROR__{type(e).__name__}: {e}')
    finally:
        # 释放 pyppeteer 浏览器，否则每次渲染都会残留一个 chromium 进程
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def js_render(url, timeout=JS_RENDER_TIMEOUT):
    """渲染 JS 页面并返回 html 文本。

    原来直接在主线程序列化调用 render()：订阅页里只要有一个源卡在渲染上，整个
    GitHub Actions 任务就会一直挂到超时。这里改为子进程 + 硬超时，超时后杀掉进程。
    """
    # fork 不需要 pickle 子进程函数，也不重复导入 requests_html；Windows 只能用 spawn
    method = 'fork' if hasattr(os, 'fork') else 'spawn'
    ctx = multiprocessing.get_context(method)
    result_queue = ctx.Queue()
    proc = ctx.Process(target=_js_render_in_process, args=(url, result_queue), daemon=True)
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.kill()
        proc.join(5)
        _kill_orphan_chromium()
        _drain_queue(result_queue)
        raise TimeoutError(f"JS 渲染超时（{timeout}s）: {url}")

    try:
        text = result_queue.get_nowait()
    except queue.Empty:
        raise RuntimeError(f"JS 渲染子进程未返回结果（退出码 {proc.exitcode}）: {url}")
    finally:
        _drain_queue(result_queue)
        proc.join(1)
    if isinstance(text, str) and text.startswith('__JS_RENDER_ERROR__'):
        raise RuntimeError(text[len('__JS_RENDER_ERROR__'):])
    return text


def _drain_queue(result_queue):
    """关闭队列前先取走内容，否则 put 方可能卡在 feeder 线程上"""
    try:
        while True:
            result_queue.get_nowait()
    except queue.Empty:
        pass
    result_queue.close()


def _kill_orphan_chromium():
    """被杀掉的渲染子进程会留下它的 chromium 后代，按本机 pyppeteer 安装路径清理"""
    try:
        proc = subprocess.run(['pgrep', '-f', 'pyppeteer/local-chromium'],
                              capture_output=True, text=True, timeout=5)
        for pid in proc.stdout.split():
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (OSError, ValueError):
                pass
    except Exception:
        # 没有 pgrep（Windows）时忽略：子进程 daemon=True，进程退出时会被回收
        pass


# je_render返回的text没有缩进，通过正则表达式匹配proxies下的所有代理节点
def match_nodes(text):
    proxy_pattern = r"\{[^}]*name\s*:\s*['\"][^'\"]+['\"][^}]*server\s*:\s*[^,]+[^}]*\}"
    nodes = re.findall(proxy_pattern, text, re.DOTALL)

    # 将每个节点字符串转换为字典
    proxies_list = []
    for node in nodes:
        # 使用yaml.safe_load来加载每个节点
        node_dict = yaml.safe_load(node)
        proxies_list.append(node_dict)

    yaml_data = {"proxies": proxies_list}
    return yaml_data


# link非代理协议时(https)，请求url解析
def process_url(url):
    """返回 (内容列表, 是否为yaml配置)。任何失败路径都返回 ([], False)，绝不返回 None"""
    isyaml = False
    try:
        # 发送GET请求
        response = requests.get(url, headers=headers, verify=False,
                                allow_redirects=True, timeout=FETCH_TIMEOUT)
        if response.status_code != 200:
            print(f"Failed to retrieve data from {url}, status code: {response.status_code}")
            return [], isyaml

        content = response.content.decode('utf-8', errors='ignore')
        if 'proxies:' in content:
            # GitHub raw 之类的外层 <pre> 包装，统一用正则剥掉
            content = re.sub(r'<pre[^>]*>', '', content).replace('</pre>', '')
            try:
                yaml_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                print(f"YAML 解析失败 {url}: {e}")
                yaml_data = None
            if isinstance(yaml_data, dict) and yaml_data.get('proxies'):
                return yaml_data['proxies'], True
            if yaml_data is not None:
                return [], isyaml
            # YAML 解析失败时继续尝试 base64 / JS 渲染，而不是直接放弃这个源

        # 尝试Base64解码（内容必须像订阅，避免把 HTML 误判成 base64 垃圾）
        decoded_content = _decode_base64_text(content)
        if decoded_content and ('://' in decoded_content or 'proxies:' in decoded_content):
            return urllib.parse.unquote(decoded_content).splitlines(), isyaml

        # 页面需要 JS 渲染
        text = js_render(url)
        if 'external-controller' in text:
            try:
                yaml_data = yaml.safe_load(text)
            except Exception:
                yaml_data = match_nodes(text)
            if isinstance(yaml_data, dict) and yaml_data.get('proxies'):
                return yaml_data['proxies'], True
            return [], isyaml

        pattern = r'([A-Za-z0-9_+/\-]+={0,2})'
        matches = re.findall(pattern, text)
        stdout = matches[-1] if matches else ''
        decoded_content = _decode_base64_text(stdout)
        if decoded_content:
            return decoded_content.splitlines(), isyaml
        return [], isyaml
    except Exception as e:
        print(f"An error occurred while requesting {url}: {e}")
        return [], isyaml


# 解析不同的代理链接
def parse_proxy_link(link):
    parsers = (
        ("hysteria2://", parse_hysteria2_link),
        ("hy2://", parse_hysteria2_link),
        ("trojan://", parse_trojan_link),
        ("ss://", parse_ss_link),
        ("vless://", parse_vless_link),
        ("vmess://", parse_vmess_link),
    )
    for prefix, parser in parsers:
        if link.startswith(prefix):
            try:
                return parser(link)
            except Exception as e:
                # 只打印协议前缀，避免把凭据写进日志
                print(f"解析 {prefix} 链接失败: {type(e).__name__}: {e}")
                return None
    return None


# 根据 server/port/协议/凭据联合去重
def deduplicate_proxies(proxies_list):
    unique_proxies = []
    seen = set()
    for proxy in proxies_list:
        server, port = proxy.get('server'), proxy.get('port')
        if not server or not port:
            # 缺 server/port 的节点无法连接，直接丢弃
            continue
        key = (str(server), str(port), proxy.get('type'),
               str(proxy.get('password') or ''), str(proxy.get('uuid') or ''),
               str(proxy.get('cipher') or ''))
        if key not in seen:
            seen.add(key)
            unique_proxies.append(proxy)
    return unique_proxies


# 出现节点name相同时，加上4位随机字符串
def add_random_suffix(name, existing_names):
    # 生成4位随机字符串
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    new_name = f"{name}-{suffix}"
    # 确保生成的新名字不在已存在的名字列表中
    while new_name in existing_names:
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        new_name = f"{name}-{suffix}"
    return new_name


# 从指定目录下的txt读取代理链接
def read_txt_files(folder_path):
    all_lines = []  # 用于存储所有文件的行

    # 使用 glob 获取指定文件夹下的所有 txt 文件
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))

    for file_path in txt_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            # 读取文件内容并按行存入数组
            lines = file.readlines()
            all_lines.extend(line.strip() for line in lines)  # 去除每行的换行符并添加到数组中
    if all_lines:
        print(f'加载【{folder_path}】目录下所有txt中节点')
    return all_lines


# 从指定目录下的yaml/yml读取proxies
def read_yaml_files(folder_path):
    load_nodes = []
    # 使用 glob 获取指定文件夹下的所有 yaml/yml 文件
    yaml_files = glob.glob(os.path.join(folder_path, '*.yaml'))
    yaml_files.extend(glob.glob(os.path.join(folder_path, '*.yml')))

    for file_path in yaml_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # 读取并解析yaml文件
                config = yaml.safe_load(file)
                # 如果存在proxies字段，添加到nodes列表
                if config and 'proxies' in config:
                    load_nodes.extend(config['proxies'])
        except Exception as e:
            print(f"Error reading {file_path}: {str(e)}")
    if load_nodes:
        print(f'加载【{folder_path}】目录下yaml/yml中所有节点')
    return load_nodes


# 进行type过滤
def filter_by_types_alt(allowed_types, nodes):
    # 进行过滤
    return [x for x in nodes if x.get('type') in allowed_types]


# 合并links列表
def merge_lists(*lists):
    return [item for item in chain.from_iterable(lists) if item != '']


def handle_links(new_links, resolve_name_conflicts):
    for new_link in new_links:
        # 逐条容错：一条坏链接不应中断后面所有节点
        try:
            if new_link.startswith(("hysteria2://", "hy2://", "trojan://", "ss://", "vless://", "vmess://")):
                node = parse_proxy_link(new_link)
                if node:
                    resolve_name_conflicts(node)
            else:
                print(f"跳过无效或不支持的链接: {new_link[:30]}")
        except Exception as e:
            print(f"处理链接失败: {type(e).__name__}: {e}")


# 生成 Clash 配置文件
def generate_clash_config(links, load_nodes):
    now = datetime.now()
    print(f"当前时间: {now}\n---")

    final_nodes = []
    existing_names = set()  # 存储所有节点名字以检查重复
    # 深拷贝，避免污染模块级模板（浅拷贝会让各组 proxies 列表被后续调用复用）
    config = copy.deepcopy(clash_config_template)

    # 名称已存在的节点加随机后缀
    def resolve_name_conflicts(node):
        server = node.get("server")
        if not server:
            # print(f'不存在sever，非节点')
            return
        if not_contains(str(node.get("name") or "")):
            node = dict(node)  # 复制一份，避免修改调用方传入的节点对象
            name = str(node.get("name") or f"{server}:{node.get('port')}")
            if name in existing_names:
                name = add_random_suffix(name, existing_names)
            existing_names.add(name)
            node["name"] = name
            final_nodes.append(node)

    for node in load_nodes:
        if isinstance(node, dict):
            # 缺 name 的节点补一个可读名字，而不是整批中断
            if not node.get("name"):
                node = {**node, "name": f"{node.get('server')}:{node.get('port')}"}
            resolve_name_conflicts(node)

    for link in links:
        if link.startswith(("hysteria2://", "hy2://", "trojan://", "ss://", "vless://", "vmess://")):
            node = parse_proxy_link(link)
            if not node:
                continue
            resolve_name_conflicts(node)
        else:
            if '|links' in link or '.md' in link:
                link = link.replace('|links', '')
                new_links = parse_md_link(link)
                handle_links(new_links, resolve_name_conflicts)
            if '|ss' in link:
                link = link.replace('|ss', '')
                new_links = parse_ss_sub(link)
                for node in new_links:
                    resolve_name_conflicts(node)
            if '{' in link:
                link = resolve_template_url(link)
            print(f'当前正在处理link: {link}')
            # 处理非特定协议的链接
            try:
                new_links, isyaml = process_url(link)
            except Exception as e:
                print(f"error: {e}")
                continue
            if isyaml:
                for node in new_links:
                    resolve_name_conflicts(node)
            else:
                handle_links(new_links, resolve_name_conflicts)
    final_nodes = deduplicate_proxies(final_nodes)

    # 组内节点按加入顺序去重（不用 set，保序且只遍历一次）
    group_names = [str(node["name"]) for node in final_nodes
                   if not_contains(str(node["name"]))]
    group_names = list(dict.fromkeys(group_names))
    for group in config["proxy-groups"]:
        if group["name"] in ("自动选择", "故障转移", "手动选择"):
            group["proxies"] = list(group_names)
    config["proxies"] = final_nodes

    if config["proxies"]:
        global CONFIG_FILE
        CONFIG_FILE = CONFIG_FILE[:-5] if CONFIG_FILE.endswith('.json') else CONFIG_FILE
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        with open(f'{CONFIG_FILE}.json', "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False)
        print(f"已经生成Clash配置文件{CONFIG_FILE}|{CONFIG_FILE}.json")
    else:
        print('没有节点数据更新')


# 判断不包含
def not_contains(s):
    return not any(k in s for k in BAN)


# 自定义 Clash API 异常
class ClashAPIException(Exception):
    """自定义 Clash API 异常"""
    pass


# 代理测试结果类
class ProxyTestResult:
    """代理测试结果类"""

    def __init__(self, name: str, delay: Optional[float] = None):
        self.name = name
        self.delay = delay if delay is not None else float('inf')
        self.status = "ok" if delay is not None else "fail"
        self.tested_time = datetime.now()

    @property
    def is_valid(self) -> bool:
        return self.status == "ok"

    def __eq__(self, other):
        return isinstance(other, ProxyTestResult) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


def ensure_executable(file_path):
    """ 确保文件具有可执行权限（仅适用于 Linux 和 macOS） """
    if platform.system().lower() in ['linux', 'darwin']:
        os.chmod(file_path, 0o755)  # 设置文件为可执行


# 处理 Clash 配置错误，解析错误信息并更新配置文件
def handle_clash_error(error_message, config_file_path):
    start_time = time.time()
    config_file_path = f'{config_file_path}.json' if os.path.exists(f'{config_file_path}.json') else config_file_path

    proxy_index_match = re.search(r'proxy (\d+):', error_message)
    if not proxy_index_match:
        return False

    problem_index = int(proxy_index_match.group(1))

    try:
        # 读取配置文件
        with open(config_file_path, 'r', encoding='utf-8') as file:
            config = json.load(file)

        # 获取要删除的节点的name
        problem_proxy_name = config['proxies'][problem_index]['name']
        # 删除问题节点
        del config['proxies'][problem_index]

        # 从所有proxy-groups中删除该节点引用（逐组独立修改，不要共用同一个列表对象）
        for group in config.get("proxy-groups", []):
            if problem_proxy_name in group.get("proxies", []):
                group["proxies"] = [p for p in group["proxies"] if p != problem_proxy_name]

        # 同时修正 yaml 副本，避免两份配置分叉（WebUI/下次生成读的是 yaml）
        if config_file_path.endswith('.json'):
            yaml_path = config_file_path[:-5]
            with open(config_file_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, ensure_ascii=False)
            with open(yaml_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, allow_unicode=True, sort_keys=False)
        else:
            with open(config_file_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, allow_unicode=True, sort_keys=False)

        print(
            f'配置异常：{error_message}修复配置异常，移除proxy[{problem_index}] {problem_proxy_name} 完毕，耗时{time.time() - start_time}s\n')
        return True

    except Exception as e:
        print(f"处理配置文件时出错: {str(e)}")
        return False


# 下载最新mihomo
def download_and_extract_latest_release():
    url = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"获取 mihomo 版本信息失败: {e}")
        return

    assets = data.get("assets", [])
    os_type = platform.system().lower()
    targets = {
        "darwin": "mihomo-darwin-amd64-compatible",
        "linux": "mihomo-linux-amd64-compatible",
        "windows": "mihomo-windows-amd64-compatible"
    }

    # 确定下载链接和新名称
    download_url = None
    new_name = f"clash-{os_type}" if os_type != "windows" else "clash.exe"

    # 检查是否已存在二进制文件
    if os.path.exists(new_name):
        return

    for asset in assets:
        name = asset.get("name", "")
        # 根据操作系统确定下载文件的名称和后缀
        if os_type == "darwin" and targets["darwin"] in name and name.endswith('.gz'):
            download_url = asset["browser_download_url"]
            break
        elif os_type == "linux" and targets["linux"] in name and name.endswith('.gz'):
            download_url = asset["browser_download_url"]
            break
        elif os_type == "windows" and targets["windows"] in name and name.endswith('.zip'):
            download_url = asset["browser_download_url"]
            break

    if download_url:
        download_url = f"{download_url}"
        print(f"Downloading file from {download_url}")
        filename = download_url.split('/')[-1]
        try:
            response = requests.get(download_url, timeout=FETCH_TIMEOUT, stream=True)
            response.raise_for_status()
            # 流式写入，避免整包读进内存
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        except requests.RequestException as e:
            print(f"下载 mihomo 失败: {e}")
            return

        # 解压文件并重命名
        extracted_files = []
        if filename.endswith('.zip'):
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall()
                extracted_files = zip_ref.namelist()
        elif filename.endswith('.gz'):
            with gzip.open(filename, 'rb') as f_in:
                output_filename = filename[:-3]
                with open(output_filename, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    extracted_files.append(output_filename)

        # 重命名并删除下载的文件
        for file_name in extracted_files:
            if os.path.exists(file_name):
                os.rename(file_name, new_name)
                break

        os.remove(filename)  # 删除下载的压缩文件
    else:
        print("No suitable release found for the current operating system.")


def read_output(pipe, output_lines, max_lines=200):
    """持续读取子进程输出，只保留最后 max_lines 行，避免长跑时内存无限增长"""
    while True:
        line = pipe.readline()
        if not line:
            break
        output_lines.append(line)
        if len(output_lines) > max_lines:
            del output_lines[:-max_lines]


def kill_clash():
    """
    在 macOS、Linux 和 Windows 上强制杀掉 Clash 进程。
    支持配置文件：clash_config.yaml 和 clash_config.yaml.json
    """
    # 根据操作系统定义 Clash 进程名
    system = platform.system()
    clash_process_names = {
        "Windows": "clash.exe",
        "Linux": "clash-linux",
        "Darwin": "clash-darwin"  # macOS
    }
    config_files = ["clash_config.yaml", "clash_config.yaml.json"]

    # 检查是否支持当前操作系统
    if system not in clash_process_names:
        print("不支持的操作系统")
        return

    # 获取当前系统的 Clash 进程名
    process_name = clash_process_names[system]

    # 遍历所有进程，查找并终止 Clash 进程
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 如果进程名不匹配，跳过
            if proc.info['name'] != process_name:
                continue

            # 获取命令行参数并检查配置文件
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) >= 3 and cmdline[1] == '-f' and cmdline[2] in config_files:
                # 强制终止进程
                proc.kill()
                # print(f"Clash 进程 (PID: {proc.pid}) 已终止 ({system})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # 忽略进程不存在、权限不足或僵尸进程的异常
            pass

    # print(f"未找到 Clash 进程 ({system})")


def start_clash(max_attempts=20, startup_timeout=3):
    """启动 mihomo，返回进程对象；失败达到 max_attempts 次后返回 None（而不是无限重启）"""
    download_and_extract_latest_release()
    system_platform = platform.system().lower()

    if system_platform == 'windows':
        clash_binary = '.\\clash.exe'
    elif system_platform in ["linux", "darwin"]:
        clash_binary = f'./clash-{system_platform}'
    else:
        raise OSError("Unsupported operating system.")

    if not os.path.exists(clash_binary):
        print(f"未找到内核 {clash_binary}，下载失败或当前系统不受支持")
        return None
    ensure_executable(clash_binary)

    global CONFIG_FILE
    CONFIG_FILE = f'{CONFIG_FILE}.json' if os.path.exists(f'{CONFIG_FILE}.json') else CONFIG_FILE

    for attempt in range(1, max_attempts + 1):
        # stderr 并入 stdout，用同一个读取线程消费，避免管道写满后子进程阻塞
        clash_process = subprocess.Popen(
            [clash_binary, '-f', CONFIG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8'
        )

        output_lines = []
        reader = threading.Thread(target=read_output, args=(clash_process.stdout, output_lines), daemon=True)
        reader.start()

        start_time = time.time()
        while time.time() - start_time < startup_timeout:
            reader.join(timeout=0.5)
            last_line = output_lines[-1] if output_lines else ''
            if last_line:
                # 检查输出是否包含错误信息
                if 'GeoIP.dat' in last_line:
                    print(last_line.strip())
                    time.sleep(5)
                    if is_clash_api_running():
                        print('Clash API启动成功，开始批量检测')
                        return clash_process

                if "Parse config error" in last_line:
                    if handle_clash_error(last_line, CONFIG_FILE):
                        break  # 修复成功，重启一次
                    print(f"配置修复失败，放弃启动: {last_line.strip()}")
                    clash_process.kill()
                    return None
            if is_clash_api_running():
                print('Clash API启动成功，开始批量检测')
                return clash_process

        clash_process.kill()
        clash_process.wait()
        print(f"Clash 第 {attempt}/{max_attempts} 次启动失败")

    print("Clash 启动失败次数过多，已放弃")
    return None


def is_clash_api_running():
    try:
        url = f"http://{CLASH_API_HOST}:{CLASH_API_PORTS[0]}/configs"
        response = requests.get(url, timeout=2, headers={
            "Authorization": f"Bearer {CLASH_API_SECRET}" if CLASH_API_SECRET else ""
        })
        # 检查响应状态码，200表示正常
        return response.status_code == 200
    except requests.exceptions.RequestException:
        # 捕获所有请求异常，包括连接错误等
        return False


# 切换到指定代理节点
def switch_proxy(proxy_name='DIRECT'):
    """
    切换 Clash 中策略组的代理节点。
    :param proxy_name: 要切换到的代理节点名称
    :return: 返回切换结果或错误信息
    """
    url = f"http://{CLASH_API_HOST}:{CLASH_API_PORTS[0]}/proxies/节点选择"
    data = {
        "name": proxy_name
    }

    try:
        response = requests.put(url, json=data, timeout=5)
        # 检查响应状态
        if response.status_code == 204:  # Clash API 切换成功返回 204 No Content
            print(f"切换到 '节点选择-{proxy_name}' successfully.")
            return {"status": "success", "message": f"Switched to proxy '{proxy_name}'."}
        return response.json()
    except Exception as e:
        print(f"Error occurred: {e}")
        return {"status": "error", "message": str(e)}


# 调用ClashAPI
class ClashAPI:
    def __init__(self, host: str, ports: List[int], secret: str = ""):
        self.host = host
        self.ports = ports
        self.base_url = None  # 将在连接检查时设置
        self.headers = {
            "Authorization": f"Bearer {secret}" if secret else "",
            "Content-Type": "application/json",
            'Accept-Charset': 'utf-8',
            'Accept': 'text/html,application/x-yaml,*/*',
            'User-Agent': 'Clash Verge/1.7.7'
        }
        # /delay 接口会阻塞到测试超时为止，读超时必须留出余量，否则客户端先超时会把慢节点误判为失效
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5, read=TIMEOUT + 5, write=5, pool=5))
        self.semaphore = Semaphore(MAX_CONCURRENT_TESTS)
        self._test_results_cache: Dict[str, ProxyTestResult] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def check_connection(self) -> bool:
        """检查与 Clash API 的连接状态，自动尝试不同端口"""
        for port in self.ports:
            try:
                test_url = f"http://{self.host}:{port}"
                response = await self.client.get(f"{test_url}/version")
                if response.status_code == 200:
                    version = response.json().get('version', 'unknown')
                    print(f"成功连接到 Clash API (端口 {port})，版本: {version}")
                    self.base_url = test_url
                    return True
            except httpx.RequestError:
                print(f"端口 {port} 连接失败，尝试下一个端口...")
                continue

        print("所有端口均连接失败")
        print(f"请确保 Clash 正在运行，并且 External Controller 已启用于以下端口之一: {', '.join(map(str, self.ports))}")
        return False

    async def get_proxies(self) -> Dict:
        """获取所有代理节点信息"""
        if not self.base_url:
            raise ClashAPIException("未建立与 Clash API 的连接")

        try:
            response = await self.client.get(
                f"{self.base_url}/proxies",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print("认证失败，请检查 API Secret 是否正确")
            raise ClashAPIException(f"HTTP 错误: {e}")
        except httpx.RequestError as e:
            raise ClashAPIException(f"请求错误: {e}")

    async def test_proxy_delay(self, proxy_name: str) -> ProxyTestResult:
        """测试指定代理节点的延迟，使用缓存避免重复测试"""
        if not self.base_url:
            raise ClashAPIException("未建立与 Clash API 的连接")

        # 检查缓存
        if proxy_name in self._test_results_cache:
            cached_result = self._test_results_cache[proxy_name]
            # 如果测试结果不超过60秒，直接返回缓存的结果
            if (datetime.now() - cached_result.tested_time).total_seconds() < 60:
                return cached_result

        async with self.semaphore:
            try:
                response = await self.client.get(
                    f"{self.base_url}/proxies/{urllib.parse.quote(proxy_name, safe='')}/delay",
                    headers=self.headers,
                    params={"url": TEST_URL, "timeout": int(TIMEOUT * 1000)}
                )
                response.raise_for_status()
                delay = response.json().get("delay")
                result = ProxyTestResult(proxy_name, delay)
            except (httpx.HTTPError, ValueError):
                result = ProxyTestResult(proxy_name)

            # 更新缓存并返回（不要在 finally 里 return，避免吞掉取消/异常信号）
            self._test_results_cache[proxy_name] = result
            return result


# 更新clash配置
class ClashConfig:
    """Clash 配置管理类"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.proxy_groups = self._get_proxy_groups()

    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到配置文件: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        if not isinstance(data, dict):
            raise ValueError(f"配置文件内容不是有效的 YAML 映射: {self.config_path}")
        return data

    @property
    def yaml_path(self) -> str:
        """配置对应的 yaml 路径（config_path 可能是 .json）"""
        if self.config_path.endswith('.yaml.json'):
            return self.config_path[:-5]
        if self.config_path.endswith('.json'):
            return self.config_path[:-5] + '.yaml'
        return self.config_path

    def _get_proxy_groups(self) -> List[Dict]:
        """获取所有代理组信息"""
        return self.config.get("proxy-groups", [])

    def get_group_names(self) -> List[str]:
        """获取所有代理组名称"""
        return [group["name"] for group in self.proxy_groups]

    def get_group_proxies(self, group_name: str) -> List[str]:
        """获取指定组的所有代理"""
        for group in self.proxy_groups:
            if group["name"] == group_name:
                return group.get("proxies", [])
        return []

    def remove_invalid_proxies(self, results: List[ProxyTestResult]):
        """从配置中完全移除失效的节点"""
        # 获取所有失效节点名称
        invalid_proxies = {r.name for r in results if not r.is_valid}

        if not invalid_proxies:
            return

        # 从 proxies 部分移除失效节点
        valid_proxies = []
        if "proxies" in self.config:
            valid_proxies = [p for p in self.config["proxies"]
                             if p.get("name") not in invalid_proxies]
            self.config["proxies"] = valid_proxies

        # 从所有代理组中移除失效节点
        for group in self.proxy_groups:
            if "proxies" in group:
                group["proxies"] = [p for p in group["proxies"] if p not in invalid_proxies]
        print(f"已从配置中移除 {len(invalid_proxies)} 个失效节点")

    def keep_proxies_by_limit(self, proxy_names):
        if "proxies" in self.config:
            self.config["proxies"] = [p for p in self.config["proxies"] if p["name"] in proxy_names]

    def apply_results(self, results: List[ProxyTestResult], groups_to_test: List[str],
                      limit: Optional[int] = None) -> List[str]:
        """移除失效节点，并按延迟重排各组。

        返回有效节点名列表（已按延迟升序、已按 limit 截断）。
        组内未被测试的成员（自定义组 / DIRECT / REJECT）保留在末尾，
        并保证 config["proxies"] 不会删掉仍被任何组引用的节点。
        """
        valid_results = sorted((r for r in results if r.is_valid), key=lambda r: r.delay)
        if not valid_results:
            # 全部失效：不动配置，交给调用方决定
            return []

        self.remove_invalid_proxies(results)

        if limit:
            valid_results = valid_results[:limit]
        valid_names = [r.name for r in valid_results]
        valid_set = set(valid_names)
        tested_names = {r.name for r in results}

        for group_name in groups_to_test:
            group = next((g for g in self.proxy_groups if g["name"] == group_name), None)
            if group is None:
                continue
            members = group.get("proxies", [])
            member_set = set(members)  # 成员可能有上万个，避免 list 线性查找
            ordered = [n for n in valid_names if n in member_set]
            # 只保留"没参与本轮测试"的成员（自定义组里的节点）；被测试但不合格/超限的节点要移除
            rest = [n for n in members if n not in valid_set and n not in tested_names]
            group["proxies"] = ordered + rest

        # 保留任何组仍在引用的节点，避免 group 引用悬空
        seen_refs = set()
        for group in self.proxy_groups:
            for name in group.get("proxies", []):
                seen_refs.add(name)
        self.keep_proxies_by_limit(seen_refs)

        return valid_names

    def update_group_proxies(self, group_name: str, results: List[ProxyTestResult]):
        """更新指定组的代理列表，仅保留有效节点并按延迟排序"""
        # 移除失效节点
        self.remove_invalid_proxies(results)

        # 获取有效节点并按延迟排序
        valid_results = [r for r in results if r.is_valid]
        valid_results = list(set(valid_results))
        valid_results.sort(key=lambda x: x.delay)

        # 更新代理组
        proxy_names = [r.name for r in valid_results]
        for group in self.proxy_groups:
            if group["name"] == group_name:
                group["proxies"] = proxy_names
                break
        return proxy_names

    def save(self):
        """保存配置到文件（yaml 与 json 同步写入）"""
        yaml_cfg = self.yaml_path
        try:
            with open(yaml_cfg, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, sort_keys=False)
            with open(f'{yaml_cfg}.json', "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False)
        except OSError as e:
            # 抛给调用方处理（WebUI 需要捕获而不是让整个进程退出）
            raise OSError(f"保存配置文件失败: {e}") from e


# 打印测试结果摘要
def print_test_summary(group_name: str, results: List[ProxyTestResult]):
    """打印测试结果摘要"""
    valid_results = [r for r in results if r.is_valid]
    invalid_results = [r for r in results if not r.is_valid]
    total = len(results)
    valid = len(valid_results)
    invalid = len(invalid_results)

    print(f"\n策略组 '{group_name}' 测试结果:")
    print(f"总节点数: {total}")
    print(f"可用节点数: {valid}")
    print(f"失效节点数: {invalid}")

    delays = []

    if valid > 0:
        avg_delay = sum(r.delay for r in valid_results) / valid
        print(f"平均延迟: {avg_delay:.2f}ms")
        print("\n节点延迟统计:")
        sorted_results = sorted(valid_results, key=lambda x: x.delay)
        for i, result in enumerate(sorted_results[:LIMIT], 1):
            delays.append({"name": result.name, "Delay_ms": round(result.delay, 2)})
            print(f"{i}. {result.name}: {result.delay:.2f}ms")
    return delays


# 测试一组代理节点
async def test_group_proxies(clash_api: ClashAPI, proxies: List[str]) -> List[ProxyTestResult]:
    """测试一组代理节点"""
    print(f"开始测试 {len(proxies)} 个节点 (最大并发: {MAX_CONCURRENT_TESTS})")

    # 创建所有测试任务
    tasks = [clash_api.test_proxy_delay(proxy_name) for proxy_name in proxies]

    # 使用进度显示执行所有任务
    results = []
    for future in asyncio.as_completed(tasks):
        result = await future
        results.append(result)
        # 显示进度
        done = len(results)
        total = len(tasks)
        print(f"\r进度: {done}/{total} ({done / total * 100:.1f}%)", end="", flush=True)

    return results


async def proxy_clean():
    # 更新全局配置
    delays = []
    global MAX_CONCURRENT_TESTS, TIMEOUT, CLASH_API_SECRET, LIMIT, CONFIG_FILE
    CONFIG_FILE = f'{CONFIG_FILE}.json' if os.path.exists(f'{CONFIG_FILE}.json') else CONFIG_FILE
    print(f"===================节点批量检测基本信息======================")
    print(f"配置文件: {CONFIG_FILE}")
    print(f"API 端口: {CLASH_API_PORTS[0]}")
    print(f"并发数量: {MAX_CONCURRENT_TESTS}")
    print(f"超时时间: {TIMEOUT}秒")
    print(f"保留节点：最多保留{LIMIT}个延迟最小的有效节点")

    # 加载配置
    print(f'加载配置文件{CONFIG_FILE}')
    config = ClashConfig(CONFIG_FILE)

    # 确定要测试的策略组（跳过总控组"节点选择"）
    groups_to_test = [name for name in config.get_group_names() if name != '节点选择']

    if not groups_to_test:
        print("错误: 没有找到要测试的有效策略组")
        print(f"可用的策略组: {', '.join(config.get_group_names())}")
        return

    print(f"\n将测试以下策略组: {', '.join(groups_to_test)}")

    # 开始测试
    start_time = datetime.now()

    # 创建支持多端口的API实例
    async with ClashAPI(CLASH_API_HOST, CLASH_API_PORTS, CLASH_API_SECRET) as clash_api:
        if not await clash_api.check_connection():
            return

        try:
            all_test_results = []  # 收集所有测试结果

            # 测试策略组，只需要测试其中一个即可（生成时各组节点相同）；取节点数最多的组
            group_name = max(groups_to_test, key=lambda g: len(config.get_group_proxies(g)))
            print(f"\n======================== 开始测试策略组: {group_name} ====================")
            proxies = config.get_group_proxies(group_name)

            if not proxies:
                print(f"策略组 '{group_name}' 中没有代理节点")
                return
            # 测试该组的所有节点
            results = await test_group_proxies(clash_api, proxies)
            all_test_results.extend(results)
            # 打印测试结果摘要
            delays = print_test_summary(group_name, results)

            print('\n===================移除失效节点并按延迟排序======================\n')
            # 先按延迟排序，再按 LIMIT 截断（反过来会保留测试完成顺序的随机节点）
            valid_names = config.apply_results(all_test_results, groups_to_test, LIMIT)
            if not valid_names:
                # 全部失效多半是网络瞬断，保留原配置而不是把节点清空
                print("警告: 本轮没有任何有效节点，保留原配置不做修改")
                return delays
            for name in groups_to_test:
                print(f"'{name}'已按延迟大小重新排序")

            # 保存更新后的配置
            config.save()

            if SPEED_TEST:
                # 测速
                print('\n===================检测节点速度======================\n')
                sorted_proxy_names = start_download_test(valid_names)
                # 按速度重排每个组，未参与测速的成员保留在末尾
                for name in groups_to_test:
                    group = next((g for g in config.proxy_groups if g["name"] == name), None)
                    if group is None:
                        continue
                    ordered = [n for n in sorted_proxy_names if n in group["proxies"]]
                    rest = [n for n in group["proxies"] if n not in ordered]
                    group["proxies"] = ordered + rest
                # 保存更新后的配置
                config.save()

            # 显示总耗时
            total_time = (datetime.now() - start_time).total_seconds()
            print(f"\n总耗时: {total_time:.2f} 秒")
            return delays
        except ClashAPIException as e:
            print(f"Clash API 错误: {e}")
        except Exception as e:
            print(f"发生错误: {e}")
            raise


# 获取当前时间的各个组成部分
def parse_datetime_variables():
    now = datetime.now()
    return {
        'Y': str(now.year),
        'm': str(now.month).zfill(2),
        'd': str(now.day).zfill(2),
        'H': str(now.hour).zfill(2),
        'M': str(now.minute).zfill(2),
        'S': str(now.second).zfill(2)
    }


# 移除URL中的代理前缀
def strip_proxy_prefix(url):
    proxy_pattern = r'^https?://[^/]+/https://'
    match = re.match(proxy_pattern, url)
    if match:
        real_url = re.sub(proxy_pattern, 'https://', url)
        proxy_prefix = url[:match.end() - 8]
        return real_url, proxy_prefix
    return url, None


# 判断是否为GitHub raw URL
def is_github_raw_url(url):
    return 'raw.githubusercontent.com' in url


# 从URL中提取文件模式，返回占位符前后的部分
def extract_file_pattern(url):
    # 查找形如 {x}<suffix> 的模式
    match = re.search(r'\{x\}(\.[a-zA-Z0-9]+)(?:/|$)', url)
    if match:
        return match.group(1)  # 返回文件后缀，如 '.yaml', '.txt', '.json'
    return None


# 从GitHub API获取匹配指定后缀的文件名
def get_github_filename(github_url, file_suffix):
    # 同时支持 /owner/repo/branch/path 与 /owner/repo/refs/heads/branch/path 两种写法
    match = re.match(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)', github_url)
    if not match:
        raise ValueError("无法从URL中提取owner和repo信息")
    owner, repo, rest = match.groups()

    if rest.startswith('refs/heads/'):
        rest = rest[len('refs/heads/'):]
    branch, _, path_part = rest.partition('/')

    # 移除 {x}<suffix> 部分来获取目录路径
    path_part = re.sub(r'\{x\}' + re.escape(file_suffix) + '(?:/|$)', '', path_part)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path_part}"

    response = requests.get(api_url, timeout=FETCH_TIMEOUT)
    if response.status_code != 200:
        raise Exception(f"GitHub API请求失败: {response.status_code}")

    files = response.json()
    if isinstance(files, dict):
        files = [files]
    matching_files = [f['name'] for f in files
                      if isinstance(f, dict) and str(f.get('name', '')).endswith(file_suffix)]

    if not matching_files:
        raise Exception(f"未找到匹配的{file_suffix}文件")

    return matching_files[0]


# 解析URL模板，支持任意组合的日期时间变量和分隔符
def parse_template(template_url, datetime_vars):
    def replace_template(match):
        """替换单个模板块的内容"""
        template_content = match.group(1)
        if template_content == 'x':
            return '{x}'  # 保持 {x} 不变，供后续处理

        result = ''
        # 用于临时存储当前字符
        current_char = ''

        # 遍历模板内容中的每个字符
        for char in template_content:
            if char in datetime_vars:
                # 如果是日期时间变量，替换为对应值
                if current_char:
                    # 添加之前累积的非变量字符
                    result += current_char
                    current_char = ''
                result += datetime_vars[char]
            else:
                # 如果是其他字符（分隔符），直接保留
                current_char += char

        # 添加最后可能剩余的非变量字符
        if current_char:
            result += current_char

        return result

    # 使用正则表达式查找并替换所有模板块
    return re.sub(r'\{([^}]+)\}', replace_template, template_url)


# 完整解析模板URL
def resolve_template_url(template_url):
    # 先处理代理前缀
    url, proxy_prefix = strip_proxy_prefix(template_url)

    # 获取日期时间变量
    datetime_vars = parse_datetime_variables()

    # 替换日期时间变量
    resolved_url = parse_template(url, datetime_vars)

    # 如果是GitHub URL且包含{x}，则处理文件名
    if is_github_raw_url(resolved_url) and '{x}' in resolved_url:
        # 提取文件后缀
        file_suffix = extract_file_pattern(resolved_url)
        if file_suffix:
            filename = get_github_filename(resolved_url, file_suffix)
            # 替换 {x}<suffix> 为实际文件名
            resolved_url = re.sub(r'\{x\}' + re.escape(file_suffix), filename, resolved_url)

    # 如果有代理前缀，重新添加上
    if proxy_prefix:
        resolved_url = f"{proxy_prefix}{resolved_url}"

    return resolved_url


def start_download_test(proxy_names, speed_limit=0.1):
    """
    开始下载测试

    """
    # 清空上一轮结果，避免旧节点名残留到本次排序里
    results_speed.clear()
    # 第一步：测试所有节点的下载速度
    test_all_proxies(proxy_names[:SPEED_TEST_LIMIT])

    # 过滤出速度大于等于 speed_limit 的节点
    filtered_list = [item for item in results_speed if float(item[1]) >= float(f'{speed_limit}')]

    # 按下载速度从大到小排序
    sorted_proxy_names = []
    sorted_list = sorted(filtered_list, key=lambda x: float(x[1]), reverse=True)
    print(f'节点速度统计:')
    for i, result in enumerate(sorted_list[:LIMIT], 1):
        sorted_proxy_names.append(result[0])
        print(f"{i}. {result[0]}: {result[1]}Mb/s")

    return sorted_proxy_names


# 测试所有代理节点的下载速度，并排序结果
def test_all_proxies(proxy_names):
    try:
        # 单线程节点速度下载测试
        i = 0
        for proxy_name in proxy_names:
            i += 1
            print(f"\r正在测速节点【{i}】: {proxy_name}", flush=True, end='')
            test_proxy_speed(proxy_name)

        print("\r" + " " * 50 + "\r", end='')  # 清空行并返回行首
    except Exception as e:
        print(f"测试节点速度时出错: {e}")


# 测试指定代理节点的下载速度（下载5秒后停止）
def test_proxy_speed(proxy_name):
    # 切换到该代理节点
    switch_proxy(proxy_name)
    # 设置代理
    proxies = {
        "http": 'http://127.0.0.1:7890',
        "https": 'http://127.0.0.1:7890',
    }

    # 开始下载并测量时间
    start_time = time.time()
    # 计算总下载量
    total_length = 0
    # 测试下载时间（秒）
    test_duration = 5  # 逐块下载，直到达到5秒钟为止

    # 不断发起请求直到达到时间限制
    while time.time() - start_time < test_duration:
        remaining = test_duration - (time.time() - start_time)
        if remaining <= 0:
            break
        try:
            with requests.get("http://speedtest.tele2.net/100MB.zip", stream=True, proxies=proxies,
                               headers={'Cache-Control': 'no-cache'},
                               timeout=(3, max(1, remaining))) as response:
                for data in response.iter_content(chunk_size=524288):
                    total_length += len(data)
                    if time.time() - start_time >= test_duration:
                        break
        except Exception as e:
            print(f"测试节点 {proxy_name} 下载失败: {e}")
            break

    # 计算速度：Bps -> MB/s
    elapsed_time = time.time() - start_time
    speed = total_length / elapsed_time if elapsed_time > 0 else 0

    results_speed.append((proxy_name, f"{speed / 1024 / 1024:.2f}"))  # 记录速度测试结果
    return speed / 1024 / 1024  # 返回 MB/s


def upload_and_generate_urls(file_path=CONFIG_FILE):
    # api_url = "https://catbox.moe/user/api.php"
    # api_url = "https://f2.252035.xyz/user/api.php"
    api_url = "https://ade4e1d7-catbox.seczhcom.workers.dev/user/api.php"
    result = {"clash_url": None, "singbox_url": None}

    try:
        if not os.path.isfile(file_path):
            print(f"错误：文件 {file_path} 不存在。")
            return result
        if os.path.getsize(file_path) > 209715200:
            print("错误：文件大小超过 200MB 限制。")
            return result

        # Upload Clash config
        with open(file_path, 'rb') as file:
            response = requests.post(api_url, data={"reqtype": "fileupload"}, files={"fileToUpload": file}, timeout=15,
                                     verify=False)
            if response.status_code == 200:
                clash_url = response.text.strip()
                result["clash_url"] = clash_url
                print(f"Clash 配置文件上传成功！直链：{clash_url}")

                sb_full_url = f'https://url.v1.mk/sub?target=singbox&url={clash_url}&insert=false&config=https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full_NoAuto.ini&emoji=true&list=false&xudp=false&udp=false&tfo=false&expand=true&scv=false&fdn=false'
                encoded_url = base64.urlsafe_b64encode(sb_full_url.encode()).decode()
                response = requests.post("https://v1.mk/short", json={"longUrl": encoded_url}, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("Code") == 1:
                        singbox_url = data["ShortUrl"]
                        result["singbox_url"] = singbox_url
                        print(f"singbox 配置文件上传成功！直链：{singbox_url}")

    except Exception as e:
        print(f"发生错误：{e}")

    # 记录成功生成的链接到subs.json
    subs_file = "subs.json"
    if result["clash_url"] or result["singbox_url"]:
        try:
            # 初始化默认结构
            subs_data = {"clash": [], "singbox": []}

            # 尝试读取现有文件
            if os.path.exists(subs_file):
                try:
                    with open(subs_file, 'r', encoding='utf-8') as f:
                        subs_data = json.load(f)
                except:
                    pass  # 如果文件损坏，使用默认结构

            # 添加新链接到记录中(避免重复)
            if result["clash_url"] and result["clash_url"] not in subs_data.get("clash", []):
                if "clash" not in subs_data:
                    subs_data["clash"] = []
                subs_data["clash"].append(result["clash_url"])

            if result["singbox_url"] and result["singbox_url"] not in subs_data.get("singbox", []):
                if "singbox" not in subs_data:
                    subs_data["singbox"] = []
                subs_data["singbox"].append(result["singbox_url"])

            # 保存更新后的数据
            with open(subs_file, 'w', encoding='utf-8') as f:
                json.dump(subs_data, f, ensure_ascii=False, indent=2)

            print(f"已将订阅链接记录到 {subs_file}")
        except Exception as e:
            print(f"记录订阅链接失败: {str(e)}")

    return result


def work(links, check=False, allowed_types=[], only_check=False):
    try:
        if not only_check:
            load_nodes = read_yaml_files(folder_path=INPUT)
            if allowed_types:
                load_nodes = filter_by_types_alt(allowed_types, nodes=load_nodes)
            links = merge_lists(read_txt_files(folder_path=INPUT), links)
            if links or load_nodes:
                generate_clash_config(links, load_nodes)

        if check or only_check:
            clash_process = None
            try:
                # 启动clash
                print(f"===================启动clash并初始化配置======================")
                clash_process = start_clash()
                # 切换节点到'节点选择-DIRECT'
                switch_proxy('DIRECT')
                asyncio.run(proxy_clean())
                print(f'批量检测完毕')
            except Exception as e:
                print("Error calling Clash API:", e)
            finally:
                print(f'关闭Clash API')
                if clash_process is not None:
                    clash_process.kill()

    except KeyboardInterrupt:
        print("\n用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    links = [
        "https://c7dabe95.proxy-978.pages.dev/767b6340-96dc-4aa0-8013-a8af7513d920?clash",
        "https://cdn.jsdelivr.net/gh/xiaoji235/airport-free/clash/naidounode.txt",
        "https://cdn.jsdelivr.net/gh/yangxiaoge/tvbox_cust@master/clash/Clash2.yml",
        "https://gy.xiaozi.us.kg/sub?token=lzj666",
        "https://igdux.top/5Hna",
        "https://mxlsub.me/newfull",
        "https://proxypool.link/ss/sub|ss",
        "https://proxypool.link/trojan/sub",
        "https://proxypool.link/vmess/sub",
        "https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc0.yaml",
        "https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc1.yaml",
        "https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc2.yaml",
        "https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc3.yaml",
        "https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc4.yaml",
        "https://raw.githubusercontent.com/Roywaller/clash_subscription/refs/heads/main/clash_subscription.txt",
        "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml",
        "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/all_configs.txt",
        "https://raw.githubusercontent.com/a2470982985/getNode/main/clash.yaml",
        "https://raw.githubusercontent.com/aiboboxx/clashfree/refs/heads/main/clash.yml",
        "https://raw.githubusercontent.com/aiboboxx/v2rayfree/refs/heads/main/README.md",
        "https://raw.githubusercontent.com/anaer/Sub/refs/heads/main/clash.yaml",
        "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml",
        "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
        "https://raw.githubusercontent.com/firefoxmmx2/v2rayshare_subcription/refs/heads/main/subscription/clash_sub.yaml",
        "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml",
        "https://raw.githubusercontent.com/go4sharing/sub/main/sub.yaml",
        "https://raw.githubusercontent.com/leetomlee123/freenode/refs/heads/main/README.md",
        "https://raw.githubusercontent.com/ljlfct01/ljlfct01.github.io/refs/heads/main/节点",
        "https://raw.githubusercontent.com/mahdibland/SSAggregator/master/sub/sub_merge_yaml.yml",
        "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml",
        "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/LogInfo.txt",
        "https://raw.githubusercontent.com/mai19950/clashgithub_com/refs/heads/main/site",
        "https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/main/trial.yaml",
        "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml",
        "https://raw.githubusercontent.com/mgit0001/test_clash/refs/heads/main/heima.txt",
        "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml",
        "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
        "https://raw.githubusercontent.com/Pawdroid/Free-servers/refs/heads/main/sub",
        "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash",
        "https://raw.githubusercontent.com/shahidbhutta/Clash/refs/heads/main/Router",
        "https://raw.githubusercontent.com/skka3134/Free-servers/refs/heads/main/README.md",
        "https://raw.githubusercontent.com/snakem982/proxypool/main/source/clash-meta.yaml",
        "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml",
        "https://raw.githubusercontent.com/xiaoji235/airport-free/refs/heads/main/clash/naidounode.txt",
        "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml",
        "https://raw.githubusercontent.com/aiboboxx/clashfree/refs/heads/main/clash.yml",
        "https://raw.githubusercontent.com/ljlfct01/ljlfct01.github.io/refs/heads/main/节点",
        "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/LogInfo.txt",
        "https://github.com/mahdibland/V2RayAggregator/raw/refs/heads/master/Eternity.yml",
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/refs/heads/master/LogInfo.txt",
        "https://SOS.CMLiussss.net/auto",
        "https://sub.fqzsnai.ggff.net/auto",
        "https://sub.mikeone.ggff.net/sub?token=6e300fe82f12874e439b76693aa179fb",
        "https://sub.reajason.eu.org/clash.yaml",
        "https://v1.mk/HuaplNe",
        "https://www.freeclashnode.com/uploads/{Y}/{m}/0-{Ymd}.yaml",
        "https://www.freeclashnode.com/uploads/{Y}/{m}/1-{Ymd}.yaml",
        "https://zrf.zrf.me/zrf"
    ]
    work(links, check=True, only_check=False, allowed_types=["ss", "hysteria2", "hy2", "vless", "vmess", "trojan"])
