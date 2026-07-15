#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_today.py
----------------
"오늘, 한로로는" 섹션에 쓰일 today.json을 만드는 스크립트예요.
"""

import os
import json
import datetime
import socket
import urllib.request
import xml.etree.ElementTree as ET

# 기본 네트워크 타임아웃을 10초로 설정
socket.setdefaulttimeout(10.0)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "today.json")

YOUTUBE_CHANNEL_ID = "UCrDa_5OU-rhvXqWlPx5hgKQ"   # 한로로 HANRORO 공식 채널
INSTAGRAM_USERNAME = "hanr0r0"
TIKTOK_USERNAME = "hanroro_official"

MAX_ITEMS_PER_SOURCE = 10


def fetch_youtube_latest():
    """YouTube Data API v3로 채널의 최신 업로드 영상을 가져옵니다."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    print(f"[youtube] YOUTUBE_API_KEY 존재 여부: {'OK' if api_key else 'NOT FOUND'}")
    
    if not api_key:
        print("[youtube] YOUTUBE_API_KEY 환경변수가 없어서 건너뜁니다.")
        return []

    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=api_key)

        # 1) 채널의 업로드 재생목록 ID를 가져오기
        channel_res = youtube.channels().list(
            part="contentDetails",
            id=YOUTUBE_CHANNEL_ID
        ).execute()

        items = channel_res.get("items", [])
        if not items:
            print("[youtube] 채널 정보를 찾지 못했습니다.")
            return []

        uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # 2) 업로드 재생목록에서 최신 영상 가져오기
        playlist_res = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=MAX_ITEMS_PER_SOURCE
        ).execute()

        results = []
        for item in playlist_res.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            published = snippet["publishedAt"][:10].replace("-", ".")
            results.append({
                "date": published,
                "title": snippet["title"],
                "link": f"https://www.youtube.com/watch?v={video_id}"
            })

        return results
    except Exception as e:
        print(f"[youtube] 수집 중 예외 발생: {e}")
        return []


def _fetch_instagram_fallback():
    """우회 서버가 모두 작동하지 않을 때 마지막 수단으로 instaloader를 시도합니다."""
    print("[instagram] 최종 백업 방식(instaloader) 실행 중...")
    try:
        import instaloader
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
        )
        profile = instaloader.Profile.from_username(loader.context, INSTAGRAM_USERNAME)
        results = []
        for post in profile.get_posts():
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
            caption = (post.caption or "").strip().splitlines()[0] if post.caption else "(캡션 없음)"
            if len(caption) > 40:
                caption = caption[:40] + "…"
            date_str = post.date_utc.strftime("%Y.%m.%d")
            results.append({
                "date": date_str,
                "title": f"@{INSTAGRAM_USERNAME} — {caption}",
                "link": f"https://www.instagram.com/p/{post.shortcode}/"
            })
        return results
    except Exception as e:
        print(f"[instagram] instaloader 백업 방식도 실패했습니다: {e}")
        return []


def fetch_instagram_latest():
    """안정적인 여러 개의 Public RSSHub 미러 서버를 순차적으로 테스트하며 인스타 피드를 가져옵니다."""
    
    # 전 세계에 흩어진 신뢰도 높은 공개 RSSHub 우회 서버 목록입니다.
    # 인스타그램 서버 차단을 뚫기 위해 이 주소들을 순서대로 찔러봅니다.
    rss_gateways = [
        f"https://rsshub.app/instagram/user/{INSTAGRAM_USERNAME}",
        f"https://rsshub.rssbuddy.com/instagram/user/{INSTAGRAM_USERNAME}",
        f"https://rsshub.moeyy.cn/instagram/user/{INSTAGRAM_USERNAME}",
        f"https://rss.outv.im/instagram/user/{INSTAGRAM_USERNAME}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    for url in rss_gateways:
        try:
            print(f"[instagram] 우회 서버 시도 중: {url}")
            req = urllib.request.Request(url, headers=headers)
            
            # 각 서버당 타임아웃 8초 설정
            with urllib.request.urlopen(req, timeout=8) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            results = []
            
            # RSS 피드의 개별 게시물 가공
            for item in root.findall(".//item"):
                if len(results) >= MAX_ITEMS_PER_SOURCE:
                    break
                    
                title_el = item.find("title")
                title_text = title_el.text if title_el is not None else ""
                
                link_el = item.find("link")
                link = link_el.text if link_el is not None else f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"
                
                pub_date_el = item.find("pubDate")
                pub_date_raw = pub_date_el.text if pub_date_el is not None else ""
                
                # 날짜 변환 (YYYY.MM.DD)
                date_str = ""
                if pub_date_raw:
                    try:
                        # Wed, 15 Jul 2026 ... 포맷 처리
                        parsed_date = datetime.datetime.strptime(pub_date_raw[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                        date_str = parsed_date.strftime("%Y.%m.%d")
                    except Exception:
                        date_str = datetime.datetime.now().strftime("%Y.%m.%d")
                
                # 태그 내용 정제 및 한 줄 자르기
                caption = title_text.strip().splitlines()[0] if title_text else "(사진/동영상)"
                if len(caption) > 40:
                    caption = caption[:40] + "…"
                    
                results.append({
                    "date": date_str,
                    "title": f"@{INSTAGRAM_USERNAME} — {caption}",
                    "link": link
                })
                
            if results:
                print(f"[instagram] 수집 성공! ({len(results)}건 가져옴, 출처: {url})")
                return results
                
        except Exception as e:
            print(f"[instagram] 해당 우회 서버 실패: {e}. 다음 서버로 넘어갑니다.")
            continue
            
    # 모든 우회 서버가 실패했을 경우 최종 수단 작동
    return _fetch_instagram_fallback()


def fetch_tiktok_latest():
    """yt-dlp로 틱톡 사용자 페이지의 최신 영상 목록을 가져옵니다 (비공식)."""
    try:
        import yt_dlp
    except ImportError:
        print("[tiktok] yt-dlp가 설치되어 있지 않아 건너뜁니다.")
        return []

    url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": MAX_ITEMS_PER_SOURCE,
        "socket_timeout": 15,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries", []) if info else []
        results = []
        for entry in entries[:MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title") or "(제목 없음)"
            video_id = entry.get("id")
            upload_date = entry.get("upload_date")
            date_str = (
                f"{upload_date[:4]}.{upload_date[4:6]}.{upload_date[6:8]}"
                if upload_date else ""
            )
            results.append({
                "date": date_str,
                "title": f"@{TIKTOK_USERNAME} — {title}",
                "link": f"https://www.tiktok.com/@{TIKTOK_USERNAME}/video/{video_id}"
            })
        return results
    except Exception as e:
        print(f"[tiktok] 수집 실패: {e}")
        return []


def main():
    print("--- '오늘, 한로로는' 데이터 수집 시작 ---")
    
    youtube_data = fetch_youtube_latest()
    instagram_data = fetch_instagram_latest()
    tiktok_data = fetch_tiktok_latest()
    
    data = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "instagram": instagram_data,
        "youtube": youtube_data,
        "tiktok": tiktok_data,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"today.json 생성 완료 → {OUTPUT_PATH}")
    print(f"  instagram: {len(data['instagram'])}건 / youtube: {len(data['youtube'])}건 / tiktok: {len(data['tiktok'])}건")


if __name__ == "__main__":
    main()
