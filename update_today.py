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

# 기본 네트워크 타임아웃을 15초로 설정 (GitHub Actions 무한 대기 방지)
socket.setdefaulttimeout(15.0)

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
        from googleapiclient.discovery import build  # pip install google-api-python-client
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
        print(f"[youtube] 수집 중 예외 발생 (Quota 초과 또는 API 오류 가능성): {e}")
        return []


def _fetch_instagram_fallback():
    """우회 API가 일시적으로 작동하지 않을 때만 기존 instaloader로 재시도합니다."""
    print("[instagram] 백업 방식(instaloader)으로 재시도를 진행합니다.")
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
        print(f"[instagram] 백업 수집 방식도 실패했습니다: {e}")
        return []


def fetch_instagram_latest():
    """RSS 브릿지를 우회 활용하여 인스타그램 최신 게시물을 차단 없이 안전하게 가져옵니다."""
    # 로그인 없이 인스타그램을 안전하게 긁어오는 공개용 RSS 게이트웨이를 사용합니다.
    rss_url = f"https://rss.dw9.me/instagram/user/{INSTAGRAM_USERNAME}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print(f"[instagram] 우회 RSS를 통해 피드 수집 시도 중... ({rss_url})")
        req = urllib.request.Request(rss_url, headers=headers)
        
        # 10초 이내에 응답이 없으면 타임아웃 처리
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        
        results = []
        # RSS <item> 태그들을 탐색하여 최신 글 추출
        for item in root.findall(".//item"):
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
                
            title_element = item.find("title")
            title_text = title_element.text if title_element is not None else "(내용 없음)"
            
            link_element = item.find("link")
            link = link_element.text if link_element is not None else f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"
            
            pub_date_element = item.find("pubDate")
            pub_date_raw = pub_date_element.text if pub_date_element is not None else ""
            
            # 날짜 변환 (YYYY.MM.DD 포맷으로 가공)
            date_str = ""
            if pub_date_raw:
                try:
                    parsed_date = datetime.datetime.strptime(pub_date_raw[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    date_str = parsed_date.strftime("%Y.%m.%d")
                except Exception:
                    date_str = datetime.datetime.now().strftime("%Y.%m.%d")
            
            # 캡션 글자수 제한 (첫 줄만 남기고 생략)
            caption = title_text.strip().splitlines()[0] if title_text else ""
            if len(caption) > 40:
                caption = caption[:40] + "…"
                
            results.append({
                "date": date_str,
                "title": f"@{INSTAGRAM_USERNAME} — {caption}",
                "link": link
            })
            
        print(f"[instagram] 수집 성공: {len(results)}건")
        return results
        
    except Exception as e:
        print(f"[instagram] 우회 수집 실패 (RSS 인스턴스 제한 또는 네트워크 오류): {e}")
        # 우회 수집이 막혔을 때 마지막 수단으로 기존 instaloader 실행
        return _fetch_instagram_fallback()


def fetch_tiktok_latest():
    """yt-dlp로 틱톡 사용자 페이지의 최신 영상 목록을 가져옵니다 (비공식)."""
    try:
        import yt_dlp  # pip install yt-dlp
    except ImportError:
        print("[tiktok] yt-dlp가 설치되어 있지 않아 건너뜁니다.")
        return []

    url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,   # 개별 영상을 전부 다운로드하지 않고 목록만
        "playlistend": MAX_ITEMS_PER_SOURCE,
        "socket_timeout": 15,   # yt-dlp 자체 타임아웃 설정
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries", []) if info else []
        results = []
        for entry in entries[:MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title") or "(제목 없음)"
            video_id = entry.get("id")
            upload_date = entry.get("upload_date")  # 'YYYYMMDD' 또는 없음
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
