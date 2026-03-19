#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信新闻推送机器人 - 聚合数据版
功能：从聚合数据获取科技新闻，推送到企业微信群
每次推送5条新闻，自动去重，避免重复推送
"""

import requests
import os
import sys
import json
from datetime import datetime, date
from pathlib import Path

# ============================================
# 配置区域
# ============================================

# 从环境变量读取配置
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# 请求超时时间（秒）
TIMEOUT = 30

# 日期宽容度（天数）
DATE_TOLERANCE_DAYS = int(os.getenv("DATE_TOLERANCE_DAYS", "2"))

# 聚合数据接口URL
JUHE_API_URL = "https://v.juhe.cn/toutiao/index"

# 新闻类型：keji(科技)、guonei(国内)、guoji(国际)、yule(娱乐)
NEWS_TYPE = "keji"

# 每次推送的新闻数量
NEWS_COUNT = 5

# 历史记录保留天数
HISTORY_DAYS = 3

# 历史记录文件
HISTORY_FILE = Path(__file__).parent / "news_history.json"

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
    """
    if not date_str:
        return None
    
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None

def is_recent_news(news_date, tolerance_days=2):
    """
    判断新闻是否是最近N天的
    """
    if not news_date:
        return False
    
    today = date.today()
    news_day = news_date.date()
    delta = (today - news_day).days
    return 0 <= delta <= tolerance_days

def load_history():
    """
    加载历史记录
    """
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                # 清理过期的历史记录（只保留最近HISTORY_DAYS天的）
                cutoff_date = datetime.now().timestamp() - (HISTORY_DAYS * 24 * 3600)
                valid_history = [item for item in history if item.get('timestamp', 0) > cutoff_date]
                return valid_history
        except Exception as e:
            log_warning(f"加载历史记录失败: {e}")
    return []

def save_history(history):
    """
    保存历史记录
    """
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
    except Exception as e:
        log_warning(f"保存历史记录失败: {e}")

def is_in_history(news_item, history):
    """
    检查新闻是否在历史记录中
    """
    title = news_item.get('title', '').strip().lower()
    url = news_item.get('url', '').strip()
    
    for item in history:
        if (item.get('title', '').strip().lower() == title or 
            item.get('url', '') == url):
            return True, item.get('pushed_at', '')
    
    return False, None

def remove_duplicates(news_list):
    """
    去除重复新闻（使用标题和URL双重去重）
    """
    seen_titles = set()
    seen_urls = set()
    unique_list = []
    
    for item in news_list:
        title = item.get('title', '').strip().lower()
        url = item.get('url', '').strip()
        
        # 检查标题和URL是否重复
        if title in seen_titles or url in seen_urls:
            log_warning(f"发现重复新闻（标题: {title[:30]}...），已跳过")
            continue
        
        seen_titles.add(title)
        seen_urls.add(url)
        unique_list.append(item)
    
    return unique_list

# ============================================
# 新闻获取函数
# ============================================

def get_news_from_api():
    """
    从聚合数据API获取新闻
    """
    if not NEWS_API_KEY:
        log_error("未配置NEWS_API_KEY")
        return []

    try:
        log_info(f"正在调用聚合数据API...")
        log_info(f"新闻类型: {NEWS_TYPE}")
        log_info(f"日期宽容度: {DATE_TOLERANCE_DAYS}天")
        log_info(f"每次推送: {NEWS_COUNT}条新闻")
        log_info(f"历史记录保留: {HISTORY_DAYS}天")

        # 加载历史记录
        history = load_history()
        log_info(f"已加载 {len(history)} 条历史记录")

        # 调用聚合数据接口
        params = {
            "key": NEWS_API_KEY,
            "type": NEWS_TYPE
        }

        response = requests.get(JUHE_API_URL, params=params, timeout=TIMEOUT)

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
            
            # 判断是否是最近N天的新闻
            if not news_date or not is_recent_news(news_date, DATE_TOLERANCE_DAYS):
                continue
            
            # 构建新闻对象
            news_item = {
                "uniquekey": item.get("uniquekey", ""),
                "title": item.get("title", ""),
                "description": item.get("digest", item.get("title", "")),
                "url": item.get("url", ""),
                "picurl": item.get("thumbnail_pic_s02", item.get("thumbnail_pic_s", "")),
                "_date": news_date
            }
            
            recent_news_list.append(news_item)
            log_info(f"✓ 找到新闻: {item.get('title', '')[:40]}... ({date_str})")

        if not recent_news_list:
            log_warning(f"没有找到最近{DATE_TOLERANCE_DAYS+1}天的新闻")
            return []

        # 去重（同一次推送内的重复）
        log_info(f"开始去重，当前有 {len(recent_news_list)} 条新闻")
        unique_news_list = remove_duplicates(recent_news_list)
        log_info(f"去重后剩余 {len(unique_news_list)} 条新闻")

        # 过滤历史记录（避免重复推送）
        filtered_list = []
        for item in unique_news_list:
            in_history, pushed_at = is_in_history(item, history)
            if in_history:
                log_warning(f"新闻已推送过（{pushed_at}），跳过: {item.get('title', '')[:40]}...")
            else:
                filtered_list.append(item)
        
        log_info(f"过滤历史记录后剩余 {len(filtered_list)} 条新闻")

        # 如果过滤后数量不足
        if len(filtered_list) < NEWS_COUNT:
            log_warning(f"过滤后只有 {len(filtered_list)} 条新闻，不足 {NEWS_COUNT} 条")
        
        # 按时间排序，取最新的 NEWS_COUNT 条
        filtered_list.sort(key=lambda x: x.get("_date", datetime.min), reverse=True)
        final_news_list = [item for item in filtered_list[:NEWS_COUNT]]
        
        # 保存到历史记录
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in final_news_list:
            history.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "pushed_at": current_time,
                "timestamp": datetime.now().timestamp()
            })
        
        save_history(history)
        log_info(f"已更新历史记录，当前共 {len(history)} 条")
        
        log_info(f"✓ 最终筛选出 {len(final_news_list)} 条最新新闻")
        
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
    log_info("企业微信新闻推送机器人 - 聚合数据版（增强去重）")
    log_info("=" * 60)

    try:
        # 1. 获取新闻
        log_info("\n步骤1: 获取新闻数据")
        news_list = get_news()

        # 2. 如果没有新闻，直接退出
        if not news_list:
            log_error("\n" + "=" * 60)
            log_error("❌ 未获取到新闻，任务终止")
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
