#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天翼云盘自动签到脚本
脚本类型: 云盘签到
修改时间: 2025/5/9 9:48
编程语言: Python 3
原作者: https://www.52pojie.cn/thread-1231190-1-1.html
项目地址: https://github.com/vistal8/tianyiyun

功能说明:
1. 支持多账号自动登录天翼云盘
2. 执行每日签到任务
3. 参与每日抽奖活动
4. 支持结果推送通知

依赖环境:
1. 第三方Python库: requests, rsa
安装命令: pip install requests rsa

环境变量说明:
必需变量:
- ty_username: 天翼云盘用户名(手机号)，多个账号用&隔开
- ty_password: 天翼云盘密码，多个账号用&隔开

可选变量:
- 通过青龙面板配置通知方式

注意事项:
1. 如遇到图形验证码，表示账号被风控，需前往网页端登录输入验证码解除
2. 设备锁问题请参考: https://github.com/vistal8/tianyiyun/blob/main/README.md
3. 青龙面板配置示例: cron "30 4 * * *" script-path=xxx.py,tag=天翼云盘签到
"""

import time
import os
import random
import json
import base64
import hashlib
import rsa
import requests
import re
import sys
from urllib.parse import urlparse

# 尝试导入青龙面板的notify模块，用于消息推送
try:
    from notify import send
    NOTIFY_AVAILABLE = True
except ImportError:
    NOTIFY_AVAILABLE = False
    print("ℹ️  未找到notify模块，将使用标准输出")

# 常量定义
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def mask_phone(phone):
    """
    隐藏手机号中间四位，保护用户隐私
    :param phone: 手机号字符串
    :return: 隐藏后的手机号，如138****1234
    """
    return phone[:3] + "****" + phone[-4:] if len(phone) == 11 else phone

def int2char(a):
    """
    将数字转换为对应的字符
    :param a: 0-35的数字
    :return: 对应的字符
    """
    return BI_RM[a]

def b64tohex(a):
    """
    Base64字符串转换为十六进制字符串
    :param a: Base64编码的字符串
    :return: 十六进制字符串
    """
    d = ""
    e = 0
    c = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = B64MAP.index(list(a)[i])
            if 0 == e:
                e = 1
                d += int2char(v >> 2)
                c = 3 & v
            elif 1 == e:
                e = 2
                d += int2char(c << 2 | v >> 4)
                c = 15 & v
            elif 2 == e:
                e = 3
                d += int2char(c)
                d += int2char(v >> 2)
                c = 3 & v
            else:
                e = 0
                d += int2char(c << 2 | v >> 4)
                d += int2char(15 & v)
    if e == 1:
        d += int2char(c << 2)
    return d

def rsa_encode(j_rsakey, string):
    """
    使用RSA公钥加密字符串，用于密码加密
    :param j_rsakey: RSA公钥
    :param string: 需要加密的字符串
    :return: 加密后的字符串
    """
    rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
    result = b64tohex((base64.b64encode(rsa.encrypt(f'{string}'.encode(), pubkey))).decode())
    return result

def login(username, password):
    """
    登录天翼云盘
    :param username: 用户名(手机号)
    :param password: 密码
    :return: 登录成功的session对象，失败返回None
    """
    print("🔄 正在执行登录流程...")
    session = requests.Session()
    try:
        # 获取登录令牌
        url_token = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&pageKey=default&clientType=wap&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
        response = session.get(url_token)
        match = re.search(r"https?://[^\s'\"]+", response.text)
        if not match:
            print("❌ 错误：未找到动态登录页")
            return None
            
        # 获取登录页面
        url = match.group()
        response = session.get(url)
        match = re.search(r"<a id=\"j-tab-login-link\"[^>]*href=\"([^\"]+)\"", response.text)
        if not match:
            print("❌ 错误：登录入口获取失败")
            return None
            
        # 解析登录参数
        href = match.group(1)
        response = session.get(href)
        
        captcha_token = re.findall(r"captchaToken' value='(.+?)'", response.text)[0]
        lt = re.findall(r'lt = "(.+?)"', response.text)[0]
        return_url = re.findall(r"returnUrl= '(.+?)'", response.text)[0]
        param_id = re.findall(r'paramId = "(.+?)"', response.text)[0]
        j_rsakey = re.findall(r'j_rsaKey" value="(\S+)"', response.text, re.M)[0]
        session.headers.update({"lt": lt})

        # RSA加密用户名和密码
        username_encrypted = rsa_encode(j_rsakey, username)
        password_encrypted = rsa_encode(j_rsakey, password)
        
        # 准备登录数据
        data = {
            "appKey": "cloud",
            "accountType": '01',
            "userName": f"{{RSA}}{username_encrypted}",
            "password": f"{{RSA}}{password_encrypted}",
            "validateCode": "",
            "captchaToken": captcha_token,
            "returnUrl": return_url,
            "mailSuffix": "@189.cn",
            "paramId": param_id
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0',
            'Referer': 'https://open.e.189.cn/',
        }
        
        # 提交登录请求
        response = session.post(
            "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
            data=data,
            headers=headers,
            timeout=10
        )
        
        # 检查登录结果
        if response.json().get('result', 1) != 0:
            print(f"❌ 登录错误：{response.json().get('msg')}")
            return None
            
        # 跳转到返回URL完成登录
        session.get(response.json()['toUrl'])
        print("✅ 登录成功")
        return session
        
    except Exception as e:
        print(f"⚠️ 登录异常：{str(e)}")
        return None

def main():
    """
    主函数：处理所有账号的签到和抽奖
    """
    print("\n=============== 天翼云盘签到开始 ===============")
    
    # 从环境变量获取账号信息
    usernames = os.getenv("ty_username", "").split('&')
    passwords = os.getenv("ty_password", "").split('&')
    
    # 检查环境变量
    if not usernames or not passwords or not usernames[0] or not passwords[0]:
        print("❌ 请设置环境变量 ty_username 和 ty_password")
        print("ℹ️  格式: 多个账号用&隔开，如: ty_username=13800138000&13900139000")
        return
    
    # 确保账号密码数量匹配
    if len(usernames) != len(passwords):
        print("❌ 账号和密码数量不匹配")
        print(f"ℹ️  用户名数量: {len(usernames)}, 密码数量: {len(passwords)}")
        return
    
    # 组合账号信息
    accounts = [{"username": u.strip(), "password": p.strip()} for u, p in zip(usernames, passwords)]
    all_results = []
    
    for acc in accounts:
        username = acc["username"]
        password = acc["password"]
        masked_phone = mask_phone(username)
        account_result = {"username": masked_phone, "sign": "", "lottery": ""}
        
        print(f"\n🔔 处理账号：{masked_phone}")
        
        # 登录流程
        session = login(username, password)
        if not session:
            account_result["sign"] = "❌ 登录失败"
            all_results.append(account_result)
            continue
        
        # 签到流程
        try:
            # 每日签到
            rand = str(round(time.time() * 1000))
            sign_url = f'https://api.cloud.189.cn/mkt/userSign.action?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/8.6.3 Android/22 clientId/355325117317828 clientModel/SM-G930K imsi/460071114317824 clientChannelId/qq proVersion/1.0.6',
                "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
                "Host": "m.cloud.189.cn",
            }
            response = session.get(sign_url, headers=headers).json()
            
            if 'isSign' in response:
                if response.get('isSign') == "false":
                    account_result["sign"] = f"✅ +{response.get('netdiskBonus', '0')}M"
                else:
                    account_result["sign"] = f"⏳ 已签到+{response.get('netdiskBonus', '0')}M"
            else:
                account_result["sign"] = f"❌ 签到失败: {response.get('errorMsg', '未知错误')}"
            
            # 单次抽奖
            time.sleep(random.randint(2, 5))
            lottery_url = 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN&activityId=ACT_SIGNIN'
            response = session.get(lottery_url, headers=headers).json()
            
            if "errorCode" in response:
                account_result["lottery"] = f"❌ {response.get('errorCode')}"
            else:
                prize = response.get('prizeName') or response.get('description', '未知奖品')
                account_result["lottery"] = f"🎁 {prize}"
                
        except Exception as e:
            account_result["sign"] = "❌ 操作异常"
            account_result["lottery"] = f"⚠️ {str(e)}"
        
        all_results.append(account_result)
        print(f"  {account_result['sign']} | {account_result['lottery']}")
    
    # 生成汇总消息
    title = "⛅ 天翼云盘签到汇总"
    message = ""
    
    for res in all_results:
        message += f"账号: {res['username']}\n"
        message += f"签到结果: {res['sign']}\n"
        message += f"每日抽奖: {res['lottery']}\n"
        message += "--------------------\n"
    
    # 尝试使用青龙面板的notify发送通知
    if NOTIFY_AVAILABLE:
        try:
            send(title, message)
            print("✅ 已通过青龙面板发送通知")
        except Exception as e:
            print(f"❌ 发送通知失败: {str(e)}")
            print("\n" + "="*50)
            print(title)
            print(message)
            print("="*50)
    else:
        print("\n" + "="*50)
        print(title)
        print(message)
        print("="*50)
        print("ℹ️  未找到notify模块，通知仅输出到日志")

    print("\n✅ 所有账号处理完成！")

if __name__ == "__main__":
    main()
