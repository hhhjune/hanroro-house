#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_today.py
----------------
"오늘, 한로로는" 섹션에 쓰일 today.json을 만드는 스크립트예요.

- 유튜브: 공식 YouTube Data API v3 (공식 지원, 안정적. API 키 필요)
- 인스타그램: instaloader로 공개 게시물 정보를 가져와요 (비공식·로그인 불필요.
  Instagram이 구조를 바꾸거나 요청을 막으면 실패할 수 있어요)
- 틱톡: yt-dlp로 사용자 페이지의 최신 영상 목록을 가져와요 (비공식)

결과는 today.json 하나로 저장되고, 이 파일을 GitHub Pages 등 정적 호스팅과
함께 배포하면 index.html이 fetch('./today.json')으로 그대로 읽어서 보여줍니다.

⚠️ 주의
- 인스타그램/틱톡은 공식 오픈 API가 아니라서 두 서비스의 이용약관과 100%
  합치하지 않을 수 있고, 과도하게 자주 돌리면 그 계정의 요청이 일시적으로
  차단될 수 있어요. GitHub Actions에서 30분~1시간 간격 정도로 실행하는 걸
  추천해요.
- 인스타그램은 비공개 계정이거나 로그인 없이 접근이 막히면 결과가 비어있을
  수 있어요. 그럴 땐 today.json의 해당 배열이 빈 배열로 남고, 사이트에서는
  "최신 소식을 불러오지 못했어요" 안내와 함께 프로필 링크만 보여줍니다.
"""

import os
import json
import datetime

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "today.json")

YOUTUBE_CHANNEL_ID = "UCrDa_5OU-rhvXqWlPx5hgKQ"   # 한로로 HANRORO 공식 채널
INSTAGRAM_USERNAME = "hanr0r0"
TIKTOK_USERNAME = "hanroro_official"

MAX_ITEMS_PER_SOURCE = 10


def fetch_youtube_latest():
    """YouTube Data API v3로 채널의 최신 업로드 영상을 가져와요."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[youtube] YOUTUBE_API_KEY 환경변수가 없어서 건너뜁니다.")
        return []

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


def fetch_instagram_latest():
    """instaloader로 공개 계정의 최신 게시물을 가져와요 (로그인 없이, 비공식)."""
    try:
        import instaloader  # pip install instaloader
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
    """yt-dlp로 틱톡 사용자 페이지의 최신 영상 목록을 가져와요 (비공식)."""
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
    data = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "instagram": fetch_instagram_latest(),
        "youtube": fetch_youtube_latest(),
        "tiktok": fetch_tiktok_latest(),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"today.json 생성 완료 → {OUTPUT_PATH}")
    print(f"  instagram: {len(data['instagram'])}건 / youtube: {len(data['youtube'])}건 / tiktok: {len(data['tiktok'])}건")


if __name__ == "__main__":
    main()
