"""
番茄小说 & 红果短剧 数据提取脚本
用于从两大平台提取最新作品信息

注意：这些平台对直接爬取有访问限制，建议使用官方API或在平台允许的范围内使用
"""

import json
import time
import requests
from datetime import datetime


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.baidu.com/",
}


def fetch_fanqie_ranking():
    """尝试获取番茄小说排行榜数据"""
    base_url = "https://fanqienovel.com"
    rank_urls = {
        "热门排行榜": f"{base_url}/keyword/7167221",
        "高分热门": f"{base_url}/keyword/2020655962",
        "玄幻排行榜": f"{base_url}/keyword/8015385",
        "甜文榜单": f"{base_url}/keyword/7539239767251257383",
    }

    results = {}
    for name, url in rank_urls.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            results[name] = {"url": url, "status": "success", "content_length": len(resp.text)}
            time.sleep(1)
        except requests.HTTPError as e:
            results[name] = {"url": url, "status": "error", "error": str(e)}
        except Exception as e:
            results[name] = {"url": url, "status": "error", "error": str(e)}

    return results


def fetch_hongguo_dramas():
    """尝试获取红果短剧数据"""
    base_url = "https://novelquickapp.com"
    known_series_ids = [
        "7455939291827407897",  # 再次告白
        "7474811850085895230",  # 魔神人生
    ]

    results = {}
    for series_id in known_series_ids:
        url = f"{base_url}/detail?series_id={series_id}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            results[series_id] = {"url": url, "status": "success", "content_length": len(resp.text)}
            time.sleep(1)
        except requests.HTTPError as e:
            results[series_id] = {"url": url, "status": "error", "error": str(e)}
        except Exception as e:
            results[series_id] = {"url": url, "status": "error", "error": str(e)}

    return results


def save_results(data, filename):
    """保存结果到JSON文件"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {filename}")


if __name__ == "__main__":
    print(f"开始提取数据... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n[1/2] 提取番茄小说数据...")
    fanqie_data = fetch_fanqie_ranking()
    save_results(fanqie_data, "fanqie_live_data.json")

    print("\n[2/2] 提取红果短剧数据...")
    hongguo_data = fetch_hongguo_dramas()
    save_results(hongguo_data, "hongguo_live_data.json")

    print("\n完成!")
