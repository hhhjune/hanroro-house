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
import urllib.parse
import re
import html

# 기본 네트워크 타임아웃을 15초로 설정 (무한 대기 방지)
socket.setdefaulttimeout(15.0)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "today.json")

YOUTUBE_CHANNEL_ID = "UCrDa_5OU-rhvXqWlPx5hgKQ"   # 한로로 HANRORO 공식 채널
INSTAGRAM_USERNAME = "hanr0r0"
TIKTOK_USERNAME = "hanroro_official"
NAVER_BLOG_ID = "hanr0r0"

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


def _clean_caption(caption_raw):
    """캡션 앞뒤 공백/줄바꿈을 정리하고 40자로 잘라줍니다."""
    caption = html.unescape((caption_raw or "").strip())
    caption = caption.splitlines()[0] if caption else "(사진/동영상)"
    if len(caption) > 40:
        caption = caption[:40] + "…"
    return caption


def fetch_html_with_proxy(url):
    """깃허브 서버 차단을 뚫기 위해 공용 우회 프록시 서버들을 거쳐 HTML을 가져옵니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        print(f"[instagram] 직접 접속 시도 중: {url}")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[instagram] 직접 접속 실패: {e}. 프록시 우회를 시작합니다.")

    proxy_url1 = f"https://api.allorigins.win/raw?url={urllib.parse.quote(url)}"
    try:
        print("[instagram] 프록시 1선(AllOrigins) 우회 시도 중...")
        req = urllib.request.Request(proxy_url1, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[instagram] 프록시 1선 실패: {e}")

    proxy_url2 = f"https://corsproxy.io/?{urllib.parse.quote(url)}"
    try:
        print("[instagram] 프록시 2선(Corsproxy) 우회 시도 중...")
        req = urllib.request.Request(proxy_url2, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[instagram] 프록시 2선 실패: {e}")

    return ""


def _fetch_instagram_fallback():
    """웹 수집기가 모두 실패했을 때 실행되는 최종 백업 수단입니다."""
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
            caption = _clean_caption((post.caption or "").splitlines()[0] if post.caption else "")
            # 날짜는 부정확하게 나오는 문제가 있어서 "최근 게시물" 문구로 통일하고,
            # 링크도 요청하신 대로 비워둡니다 (프로필 바로가기로만 접근).
            results.append({
                "date": "최근 게시물",
                "title": caption,
                "link": ""
            })
        return results
    except Exception as e:
        print(f"[instagram] instaloader 백업 방식도 실패했습니다: {e}")
        return []


def fetch_instagram_latest():
    """인스타그램 최신 게시물의 캡션(내용)만 가져옵니다.

    Picuki -> Imginn -> Instaloader 순서로 시도해요. 날짜는 계속 부정확하게
    나오는 문제가 있어서 실제 날짜 대신 "최근 게시물"이라는 문구로 통일하고,
    개별 링크도 두지 않아요(진짜 최신 글은 프로필 바로가기로 확인).
    """
    print("[instagram] 데이터 수집 시작...")

    # --- 1단계: Picuki 파싱 ---
    picuki_url = f"https://www.picuki.com/profile/{INSTAGRAM_USERNAME}"
    html_content = fetch_html_with_proxy(picuki_url)

    if html_content and "box-photo" in html_content:
        print("[instagram] Picuki HTML 획득 성공. 파싱을 진행합니다.")
        posts = html_content.split('class="box-photo"')
        if len(posts) < 2:
            posts = html_content.split('class="photo"')

        results = []
        for post in posts[1:]:
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
            caption_match = re.search(r'alt="([^"]*)"', post)
            caption = _clean_caption(caption_match.group(1) if caption_match else "")
            results.append({"date": "최근 게시물", "title": caption, "link": ""})

        if results:
            print(f"[instagram] Picuki에서 {len(results)}건의 게시글을 성공적으로 가져왔습니다!")
            return results
    else:
        print("[instagram] Picuki 파싱 실패 혹은 차단됨. 2단계 백업으로 전환합니다.")

    # --- 2단계: Imginn 파싱 ---
    imginn_url = f"https://imginn.com/{INSTAGRAM_USERNAME}/"
    html_content = fetch_html_with_proxy(imginn_url)

    if html_content and 'class="item"' in html_content:
        print("[instagram] Imginn HTML 획득 성공. 파싱을 진행합니다.")
        posts = html_content.split('class="item"')
        results = []
        for post in posts[1:]:
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
            caption_match = re.search(r'alt="([^"]*)"', post)
            caption = _clean_caption(caption_match.group(1) if caption_match else "")
            results.append({"date": "최근 게시물", "title": caption, "link": ""})

        if results:
            print(f"[instagram] Imginn에서 {len(results)}건의 게시글을 성공적으로 가져왔습니다!")
            return results
    else:
        print("[instagram] Imginn 파싱 실패 혹은 차단됨. 최종 백업으로 전환합니다.")

    # --- 3단계: 최후의 수단 Instaloader 작동 ---
    return _fetch_instagram_fallback()


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

        # extract_flat 모드는 목록을 빠르게 가져오는 대신 썸네일 정보가 빠져있어요.
        # 그래서 화면에 실제로 쓰이는 "가장 최근 영상" 1개에 대해서만, 그 영상
        # 페이지에 다시 한번 접속해서(flat 아님) 썸네일 주소를 가져와요.
        if results:
            try:
                detail_opts = {"quiet": True, "socket_timeout": 15}
                with yt_dlp.YoutubeDL(detail_opts) as ydl:
                    detail = ydl.extract_info(results[0]["link"], download=False)
                thumbnail = detail.get("thumbnail")
                if thumbnail:
                    results[0]["thumbnail"] = thumbnail
            except Exception as e:
                print(f"[tiktok] 최신 영상 썸네일 조회 실패: {e}")

        return results
    except Exception as e:
        print(f"[tiktok] 수집 실패: {e}")
        return []


def fetch_naver_blog_latest():
    """네이버 블로그의 RSS 피드로 최신 글 목록을 가져옵니다."""
    import re as _re
    import xml.etree.ElementTree as ET

    url = f"https://rss.blog.naver.com/{NAVER_BLOG_ID}.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read()
    except Exception as e:
        print(f"[네이버 블로그] RSS 요청 실패: {e}")
        return []

    try:
        # 네이버 RSS는 종종 EUC-KR로 내려오는 경우가 있어서 두 인코딩을 순서대로 시도해요.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("euc-kr", errors="ignore")

        root = ET.fromstring(text)
        items = root.findall(".//item")
        results = []
        for item in items[:MAX_ITEMS_PER_SOURCE]:
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else "(제목 없음)"
            link = (link_el.text or "").strip() if link_el is not None else f"https://blog.naver.com/{NAVER_BLOG_ID}"
            date_str = ""
            if date_el is not None and date_el.text:
                # 예: "Mon, 20 Jul 2026 10:00:00 +0900" -> "2026.07.20"
                m = _re.search(r"(\d{1,2}) (\w{3}) (\d{4})", date_el.text)
                if m:
                    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                    day, mon, year = m.group(1), m.group(2), m.group(3)
                    if mon in months:
                        date_str = f"{year}.{months.index(mon)+1:02d}.{int(day):02d}"
            results.append({"date": date_str, "title": title, "link": link})
        return results
    except Exception as e:
        print(f"[네이버 블로그] RSS 파싱 실패: {e}")
        return []


def main():
    print("--- '오늘, 한로로는' 데이터 수집 시작 ---")

    youtube_data = fetch_youtube_latest()
    instagram_data = fetch_instagram_latest()
    tiktok_data = fetch_tiktok_latest()
    naverblog_data = fetch_naver_blog_latest()

    data = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "instagram": instagram_data,
        "youtube": youtube_data,
        "tiktok": tiktok_data,
        "naverblog": naverblog_data,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"today.json 생성 완료 → {OUTPUT_PATH}")
    print(f"  instagram: {len(data['instagram'])}건 / youtube: {len(data['youtube'])}건 / tiktok: {len(data['tiktok'])}건 / naverblog: {len(data['naverblog'])}건")


if __name__ == "__main__":
    main()
