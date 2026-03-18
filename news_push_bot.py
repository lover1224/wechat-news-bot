#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信新闻推送机器人 - 独立版本
支持：GitHub Actions、本地运行
功能：获取新闻并发送图文消息到企业微信群
"""

import requests
import json
import os
import sys
from datetime import datetime

# ============================================
# 配置区域
# ============================================

# 从环境变量读取配置
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
NEWS_API_URL = os.getenv("NEWS_API_URL", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# 请求超时时间（秒）
TIMEOUT = 30

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
# 新闻获取函数
# ============================================

def get_mock_news():
    """
    获取模拟新闻数据

    Returns:
        list: 新闻列表
    """
    log_warning("使用模拟新闻数据")
    return [
        {
            "title": "字节跳动组织架构调整：今日头条划归抖音",
            "description": "字节跳动进行内部组织架构大调整，今日头条、西瓜视频等业务划归抖音业务线，合力打造超级应用生态",
            "url": "https://www.toutiao.com/article/1",
            "picurl": "https://s3.pstatp.com/toutiao/static/img/logo/logo_201b2bc.png"
        },
        {
            "title": "全球AI技术突破：首例再生胰岛移植成功",
            "description": "我国医疗技术实现重大突破，成功完成全球首例再生胰岛移植手术，为糖尿病患者带来新希望",
            "url": "https://www.toutiao.com/article/2",
            "picurl": "https://sf1-ttcdn-tos.pstatp.com/img/tos-cn-i-qvj2lq49k0/80a000b8c5e8494b9e6e7d9b0c3d4e5f~tplv-tt-for-image:640:356.webp?lk3s=e0680277"
        },
        {
            "title": "华为阿里同日发布AI新品",
            "description": "科技巨头华为和阿里巴巴同日发布AI新品，标志着国产AI技术进入新阶段",
            "url": "https://www.toutiao.com/article/3",
            "picurl": "https://sf1-ttcdn-tos.pstatp.com/img/tos-cn-i-qvj2lq49k0/90b000c8d5e8494c9f6e8e9c1d4e5f6g~tplv-tt-for-image:640:356.webp?lk3s=e0680277"
        }
    ]

def get_news_from_api():
    """
    从API获取真实新闻数据

    Returns:
        list: 新闻列表
    """
    if not NEWS_API_URL or not NEWS_API_KEY:
        log_warning("未配置新闻API，使用模拟数据")
        return get_mock_news()

    try:
        log_info(f"正在调用新闻API: {NEWS_API_URL}")

        # 调用新闻API（支持天行数据、聚合数据等）
        response = requests.get(
            NEWS_API_URL,
            params={
                "key": NEWS_API_KEY,
                "num": 3,
                "page": 1,
                "word": "互联网"
            },
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            log_error(f"新闻API调用失败: {response.status_code}")
            return get_mock_news()

        data = response.json()

        # 解析返回数据（根据实际API格式调整）
        news_list = []

        # 打印API响应用于调试
        log_info(f"API响应: {str(data)[:500]}")

        # 天行数据格式: {code: 200, msg: "success", result: {newslist: [...]}}
        if data.get("code") == 200 and "result" in data:
            result = data["result"]
            # 支持多种字段名：newslist、list
            news_items = result.get("newslist", result.get("list", []))

            if news_items:
                for item in news_items[:3]:
                    news_list.append({
                        "title": item.get("title", ""),
                        "description": item.get("description", item.get("descri", item.get("title", ""))),
                        "url": item.get("url", ""),
                        "picurl": item.get("picUrl", item.get("picurl", ""))
                    })

        if news_list:
            log_info(f"成功获取{len(news_list)}条新闻")
            return news_list
        else:
            log_warning("API返回数据为空，使用模拟数据")
            return get_mock_news()

    except Exception as e:
        log_error(f"获取新闻失败: {str(e)}")
        return get_mock_news()

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
        log_error("获取新闻失败")
        return []

    log_info(f"获取到{len(news_list)}条新闻")
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
        log_error("新闻列表为空")
        return {"success": False, "message": "新闻列表为空"}

    if not WEBHOOK_URL:
        log_error("未配置WEBHOOK_URL环境变量")
        return {"success": False, "message": "未配置WEBHOOK_URL"}

    log_info(f"准备发送{len(news_list)}条图文消息")

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
        log_info(f"正在发送到企业微信")
        log_info(f"Webhook URL: {WEBHOOK_URL[:50]}...")

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
                log_info("✅ 图文消息发送成功")
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
    log_info("企业微信新闻推送机器人 - 开始运行")
    log_info("=" * 60)

    try:
        # 1. 获取新闻
        log_info("\n步骤1: 获取新闻数据")
        news_list = get_news()

        if not news_list:
            log_error("❌ 获取新闻失败，无法继续")
            return 1

        # 2. 发送图文消息
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
        log_error("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
