#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信新闻推送机器人 - 聚合数据版
功能：从聚合数据获取科技新闻，推送到企业微信群
"""

import requests
import os
import sys
from datetime import datetime, date

# ============================================
# 配置区域
# ============================================

# 从环境变量读取配置
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# 请求超时时间（秒）
TIMEOUT = 30

# 日期宽容度（天数）
# 0 = 只推送今天的新闻
# 1 = 推送今天和昨天的新闻
# 2 = 推送最近3天的新闻（默认）
DATE_TOLERANCE_DAYS = int(os.getenv("DATE_TOLERANCE_DAYS", "2"))

# 聚合数据接口URL
JUHE_API_URL = "https://v.juhe.cn/toutiao/index"

# 新闻类型：keji(科技)、guonei(国内)、guoji(国际)、yule(娱乐)
NEWS_TYPE = "keji"

# ============================================
# 日志函数
# ============================================

def log_info(message):
    """记录信息日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)

def log_error(message):
    """记录错误日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ERROR: {message}", file=sys.stderr, flush=True)

def log_warning(message):
    """记录警告日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] WARNING: {message}", file=sys.stderr, flush=True)

# ============================================
# 工具函数
# ============================================

def parse_news_date(date_str):
    """
    解析新闻日期字符串

    Args:
        date_str: 日期字符串，如 "2026-03-19 15:30:00"

    Returns:
        datetime: 解析后的日期对象
    """
    if not date_str:
        return None
    
    # 尝试多种日期格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None

def is_recent_news(news_date, tolerance_days=2):
    """
    判断新闻是否是最近N天的
    
    Args:
        news_date: 新闻日期对象
        tolerance_days: 宽容天数（默认2天，即最近3天）
    
    Returns:
        bool: 如果在宽容范围内返回True
    """
    if not news_date:
        return False
    
    today = date.today()
    news_day = news_date.date()
    
    # 计算日期差
    delta = (today - news_day).days
    
    # 只允许宽容范围内的新闻（0到tolerance_days天前）
    return 0 <= delta <= tolerance_days

# ============================================
# 新闻获取函数
# ============================================

def get_news_from_api():
    """
    从聚合数据API获取新闻

    Returns:
        list: 新闻列表（失败返回空列表）
    """
    if not NEWS_API_KEY:
        log_error("未配置NEWS_API_KEY")
        return []

    try:
        log_info(f"正在调用聚合数据API...")
        log_info(f"新闻类型: {NEWS_TYPE}")
        log_info(f"日期宽容度: {DATE_TOLERANCE_DAYS}天（最近{DATE_TOLERANCE_DAYS+1}天的新闻）")

        # 调用聚合数据接口
        params = {
            "key": NEWS_API_KEY,
            "type": NEWS_TYPE
        }

        response = requests.get(
            JUHE_API_URL,
            params=params,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            log_error(f"API调用失败: HTTP {response.status_code}")
            return []

        data = response.json()

        # 检查聚合数据返回状态
        if data.get("error_code") != 0:
            log_error(f"API返回错误: {data.get('error_code')} - {data.get('reason')}")
            return []

        # 解析数据
        result = data.get("result", {})
        if result.get("stat") != "1":
            log_warning(f"API返回状态: {result.get('stat')}")
            return []

        news_items = result.get("data", [])
        log_info(f"API返回 {len(news_items)} 条新闻")

        # 筛选最近N天的新闻
        today = date.today()
        log_info(f"今天是: {today}")
        
        recent_news_list = []
        
        for item in news_items:
            # 解析新闻日期
            date_str = item.get("date", "")
            news_date = parse_news_date(date_str)
            
            # 构建新闻对象
            news_item = {
                "title": item.get("title", ""),
                "description": item.get("digest", item.get("title", "")),
                "url": item.get("url", ""),
                "picurl": item.get("thumbnail_pic_s02", item.get("thumbnail_pic_s", "")),
                "_date": news_date
            }
            
            # 判断是否是最近N天的新闻
            if news_date and is_recent_news(news_date, DATE_TOLERANCE_DAYS):
                recent_news_list.append(news_item)
                log_info(f"✓ 找到新闻: {item.get('title', '')[:40]}... ({date_str})")

        # 如果没有符合条件的新闻
        if not recent_news_list:
            log_warning(f"没有找到最近{DATE_TOLERANCE_DAYS+1}天的新闻")
            return []

        # 按时间排序，取最新的3条
        recent_news_list.sort(key=lambda x: x.get("_date", datetime.min), reverse=True)
        final_news_list = [item for item in recent_news_list[:3]]
        
        log_info(f"✓ 筛选出 {len(final_news_list)} 条最新新闻")
        
        # 打印最终新闻列表
        for i, item in enumerate(final_news_list, 1):
            date_str = item.get("_date").strftime("%Y-%m-%d %H:%M") if item.get("_date") else "未知"
            log_info(f"  {i}. {item['title'][:50]}... ({date_str})")
        
        return final_news_list

    except Exception as e:
        log_error(f"获取新闻失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def get_news():
    """
    获取新闻（主函数）

    Returns:
        list: 新闻列表
    """
    log_info("=" * 60)
    log_info("开始获取新闻数据")
    log_info("=" * 60)

    news_list = get_news_from_api()

    if not news_list:
        log_error("❌ 未获取到新闻，任务终止")
        return []

    log_info(f"✅ 成功获取 {len(news_list)} 条新闻")
    return news_list

# ============================================
# 消息发送函数
# ============================================

def send_news_message(news_list):
    """
    发送图文消息到企业微信群

    Args:
        news_list (list): 新闻列表

    Returns:
        dict: 发送结果
    """
    if not news_list:
        log_error("新闻列表为空，取消发送")
        return {"success": False, "message": "新闻列表为空"}

    if not WEBHOOK_URL:
        log_error("未配置WEBHOOK_URL环境变量")
        return {"success": False, "message": "未配置WEBHOOK_URL"}

    log_info(f"准备发送 {len(news_list)} 条新闻到企业微信")

    # 构建企业微信图文消息格式
    payload = {
        "msgtype": "news",
        "news": {
            "articles": []
        }
    }

    # 添加新闻文章
    for news in news_list:
        article = {
            "title": news.get("title", ""),
            "description": news.get("description", ""),
            "url": news.get("url", ""),
            "picurl": news.get("picurl", "")
        }
        payload["news"]["articles"].append(article)

    try:
        log_info(f"正在发送到企业微信...")
        
        # 发送HTTP POST请求
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )

        log_info(f"响应状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            if result.get("errcode", 0) == 0:
                log_info("✅ 消息发送成功")
                return {"success": True, "message": "发送成功"}
            else:
                log_error(f"企业微信返回错误: {result}")
                return {"success": False, "message": f"企业微信错误: {result}"}
        else:
            log_error(f"HTTP请求失败: {response.status_code}")
            return {"success": False, "message": f"HTTP请求失败: {response.status_code}"}

    except Exception as e:
        log_error(f"发送消息异常: {str(e)}")
        return {"success": False, "message": f"发送异常: {str(e)}"}

# ============================================
# 主函数
# ============================================

def main():
    """
    主函数：获取新闻并发送
    """
    log_info("=" * 60)
    log_info("企业微信新闻推送机器人 - 聚合数据版")
    log_info("=" * 60)

    try:
        # 1. 获取新闻
        log_info("\n步骤1: 获取新闻数据")
        news_list = get_news()

        # 2. 如果没有新闻，直接退出
        if not news_list:
            log_error("\n" + "=" * 60)
            log_error("❌ 未获取到新闻，取消推送任务")
            log_error("=" * 60)
            return 1

        # 3. 发送图文消息
        log_info("\n步骤2: 发送图文消息")
        result = send_news_message(news_list)

        if result["success"]:
            log_info("\n" + "=" * 60)
            log_info("✅ 新闻推送任务执行成功")
            log_info("=" * 60)
            return 0
        else:
            log_error("\n" + "=" * 60)
            log_error(f"❌ 新闻推送任务执行失败: {result['message']}")
            log_error("=" * 60)
            return 1

    except Exception as e:
        log_error(f"\n❌ 任务执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
