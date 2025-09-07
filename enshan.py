#!/usr/bin/python3
# -*- coding: utf-8 -*-
# -------------------------------
# @Author : github@wd210010 https://github.com/wd210010/only_for_happly
# @Time : 2023/10/4 16:23
# -------------------------------
# cron "0 0 2 * * *" script-path=xxx.py,tag=匹配cron用
# const $ = new Env('恩山签到')
"""
恩山论坛自动签到脚本
功能：自动访问恩山论坛并获取用户积分信息，通过青龙面板notify.py推送结果
配置要求：
1. 恩山Cookie: 在配置文件config.sh中设置export enshanck='你的cookie'
依赖安装: pip3 install requests
"""

import requests
import re
import os
import json
import time
import logging
import sys
import subprocess
from typing import Optional, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnshanSign:
    def __init__(self):
        # 从环境变量获取配置
        self.enshanck = os.getenv("enshanck")
        
        # 请求配置
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Cookie": self.enshanck if self.enshanck else "",
            "Referer": "https://www.right.com.cn/FORUM/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # 请求会话
        self.session = requests.Session()
        self.session。headers.update(self.headers)
        
        # 最大重试次数
        self.max_retries = 3
        self.retry_delay = 5  # 重试延迟(秒)

    def check_config(self) -> bool:
        """检查必要配置是否存在"""
        if not self.enshanck:
            logger.error("未找到恩山Cookie配置，请设置环境变量: enshanck")
            return False
        return True

    def get_enshan_info(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取恩山论坛的积分信息
        Returns:
            Tuple[coin, point]: 恩山币和积分
        """
        url = 'https://www.right.com.cn/FORUM/home.php?mod=spacecp&ac=credit&showcredit=1'
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()  # 检查HTTP状态码
                
                # 使用更健壮的正则表达式匹配
                coin_pattern = r'恩山币[^:]*:\s*</em>([^<&]+)'
                point_pattern = r'积分[^:]*:\s*</em>([^<&]+)'
                
                coin_match = re.search(coin_pattern, response.text, re.IGNORECASE)
                point_match = re.search(point_pattern, response.text, re.IGNORECASE)
                
                if coin_match and point_match:
                    coin = coin_match.group(1).strip()
                    point = point_match.group(1).strip()
                    return coin, point
                else:
                    logger.warning(f"第{attempt+1}次尝试: 未找到积分信息，可能是页面结构变化或Cookie失效")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"第{attempt+1}次请求失败: {str(e)}")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return None, None

    def send_notify(self, title: str, content: str):
        """
        使用青龙面板的notify.py发送通知
        Args:
            title: 通知标题
            content: 通知内容
        """
        try:
            # 查找notify.py文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            notify_py_path = os.path.join(script_dir, "notify.py")
            
            if not os.path.exists(notify_py_path):
                # 尝试在上级目录查找
                parent_dir = os.path.dirname(script_dir)
                notify_py_path = os.path.join(parent_dir, "notify.py")
                
            if not os.path.exists(notify_py_path):
                logger.warning("未找到notify.py文件，无法发送通知")
                return
            
            # 使用Python直接导入notify.py模块并调用发送函数
            # 首先将notify.py所在目录添加到Python路径
            notify_dir = os.path.dirname(notify_py_path)
            if notify_dir not in sys.path:
                sys.path.insert(0, notify_dir)
            
            # 尝试导入notify模块
            try:
                import notify
                # 调用notify的发送函数
                notify.send(title, content)
                logger.info("使用notify.py发送通知成功")
            except ImportError as e:
                logger.error(f"导入notify模块失败: {str(e)}")
                # 如果导入失败，尝试使用命令行方式调用
                self._fallback_notify(notify_py_path, title, content)
                
        except Exception as e:
            logger.error(f"发送通知时发生错误: {str(e)}")

    def _fallback_notify(self, notify_py_path: str, title: str, content: str):
        """
        备用的通知发送方式（通过命令行调用）
        Args:
            notify_py_path: notify.py文件路径
            title: 通知标题
            content: 通知内容
        """
        try:
            # 创建临时数据文件
            data = {
                "title": title,
                "content": content
            }
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            temp_file = os.path.join(script_dir, "temp_notify_data.json")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            # 使用Python执行notify.py并传递参数
            cmd = f"python3 {notify_py_path} '{title}' '{content}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=script_dir)
            
            # 清理临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            if result.returncode == 0:
                logger.info("通过命令行调用notify.py发送通知成功")
            else:
                logger.error(f"通过命令行调用notify.py发送通知失败: {result.stderr}")
                
        except Exception as e:
            logger.error(f"备用通知方式也失败了: {str(e)}")

    def run(self):
        """主运行逻辑"""
        logger.info("开始恩山签到任务")
        
        # 检查配置
        if not self.check_config():
            return
        
        # 获取积分信息
        coin, point = self.get_enshan_info()
        
        if coin is not None and point is not None:
            title = "恩山签到成功"
            content = f"恩山币：{coin}\n积分：{point}"
            logger.info(f"获取信息成功: {content}")
        else:
            title = "恩山签到失败"
            content = "获取恩山积分信息失败，请检查Cookie是否有效"
            logger.error(content)
        
        # 发送通知
        self.send_notify(title, content)

if __name__ == "__main__":
    sign = EnshanSign()
    sign.run()
