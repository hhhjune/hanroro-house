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

# 기본 네트워크 타임아웃을 15초로 제한하여 GitHub Actions가 무한 대기하는 현상을 방지합니다.
socket.setdefaulttimeout(15.0)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "today.json")

YOUTUBE_CHANNEL_ID = "UCrDa_5OU-rhvXqWlPx5hgKQ"   # 한로로 공식 채널 ID
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

        channel_res = youtube.channels().list(
            part="contentDetails",
            id=YOUTUBE_CHANNEL_ID
        ).execute()

        items = channel_res.get("items", [])
        if not items:
            print("[youtube] 채널 정보를 찾지 못했습니다.")
            return []

        uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

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
        print(f"[youtube] 수집 중 예외 발생 (Quota 초과 또는 API 키 오류): {e}")
        return []


def fetch_instagram_latest():
    """instaloader로 공개 계정의 최신 게시물을 가져옵니다."""
    try:
        import instaloader
    except ImportError:
        print("[instagram] instaloader가 설치되어 있지 않아 건너뜁니다.")
        return []

    try:
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
        print(f"[instagram] 수집 실패: {e}")
        return []


def fetch_tiktok_latest():
    """yt-dlp로 틱톡 사용자 페이지의 최신 영상 목록을 가져옵니다."""
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
