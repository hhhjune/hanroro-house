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

# 기본 네트워크 타임아웃을 15초로 설정 (무한 대기 방지)
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
        print(f"[youtube] 수집 중 예외 발생: {e}")
        return []


def fetch_instagram_latest():
    """인스타그램 최신 게시물 정보를 가져옵니다.

    Picuki/Imginn 같은 미러 사이트를 거쳐 스크래핑을 시도해봤지만, 사이트 구조가
    자주 바뀌고 날짜·링크가 부정확하게 나오는 문제가 반복돼서, 대신 훨씬 단순하고
    안정적인 방식으로 바꿨어요: 정확한 제목이나 개별 링크 없이, "최근 게시물이
    있어요"라는 안내만 보여주고, 실제 최신 게시물은 화면의 "프로필 바로가기"
    링크로 직접 확인하도록 안내해요.
    """
    return [
        {"date": "", "title": "최근 게시물", "link": ""},
        {"date": "", "title": "최근 게시물", "link": ""},
        {"date": "", "title": "최근 게시물", "link": ""},
    ]




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
