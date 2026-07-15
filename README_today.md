# "오늘, 한로로는" 자동 업데이트 구성

말씀하신 구조 그대로예요.

```
유튜브        → 공식 YouTube Data API로 최신 영상 자동 표시
인스타그램     → Python 자동화(instaloader)가 최신 게시물 정보를 today.json에 저장
틱톡          → Python 자동화(yt-dlp)가 최신 영상 정보를 today.json에 저장
HTML         → today.json만 fetch해서 화면에 출력
```

## 파일 구성

- `update_today.py` — today.json을 만드는 스크립트
- `requirements.txt` — 필요한 파이썬 패키지
- `today.json` — 초기 시드 파일(최초 배포 시 빈 상태). 스크립트를 실행하면 덮어써져요.
- `.github/workflows/update-today.yml` — 매시간 자동으로 스크립트를 돌려서
  today.json을 커밋해주는 GitHub Actions 워크플로우
- `index_3_3.html` — `fetch('./today.json')`으로 데이터를 읽어 렌더링하도록 수정한 사이트 본문

## 처음 설정하는 법 (GitHub Pages 기준)

1. 이 파일들을 전부 같은 저장소 루트에 넣어주세요. (`index_3_3.html`은 `index.html`로 이름을
   바꾸면 GitHub Pages에서 바로 홈페이지로 열립니다.)
2. **YouTube Data API 키 발급**
   - Google Cloud Console → 프로젝트 생성 → "YouTube Data API v3" 사용 설정 → API 키 발급
3. **저장소 Secret 등록**
   - 저장소의 Settings → Secrets and variables → Actions → New repository secret
   - 이름: `YOUTUBE_API_KEY`, 값: 위에서 발급한 키
4. **Actions 쓰기 권한 확인**
   - Settings → Actions → General → Workflow permissions → "Read and write permissions" 선택
   (워크플로우가 today.json을 커밋하려면 이 권한이 필요해요)
5. **GitHub Pages 켜기**
   - Settings → Pages → Branch를 `main`(또는 사용 중인 브랜치)으로 설정
6. Actions 탭에서 `Update today.json` 워크플로우를 한 번 수동 실행(`workflow_dispatch`)해서
   today.json이 정상적으로 만들어지는지 확인해보세요.

## 로컬에서 직접 실행해보고 싶다면

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY="발급받은_키"
python update_today.py
```

실행하면 같은 폴더에 today.json이 새로 생성/갱신됩니다.

## 미리 알아두면 좋은 점

- **유튜브**는 공식 API라서 안정적이에요. 다만 무료 할당량(하루 10,000 유닛)이 있어서,
  이 스크립트 정도의 호출량이면 매시간 돌려도 충분히 여유가 있어요.
- **인스타그램(instaloader)**과 **틱톡(yt-dlp)**은 두 회사가 공식으로 열어준 API가 아니라,
  공개 페이지 정보를 읽어오는 방식이에요. 그래서:
  - 두 회사의 이용약관과 완전히 합치하지는 않을 수 있고,
  - 사이트 구조가 바뀌면 스크립트가 깨질 수 있고,
  - 너무 자주 요청하면 일시적으로 접근이 막힐 수 있어요(그래서 워크플로우를 1시간 간격 정도로
    맞춰뒀어요).
  - 계정이 비공개이거나 접근이 막히면 해당 배열이 빈 값으로 저장되고, 사이트에서는 자동으로
    "최신 소식을 불러오지 못했어요" + 프로필 바로가기 링크를 보여줘요.
- 더 안정적으로 가고 싶다면, 나중에 인스타그램은 Meta의 공식 Graph API(비즈니스 계정 전환 +
  액세스 토큰 필요), 틱톡은 TikTok Display API(앱 심사 필요)로 바꿔 끼울 수 있도록
  today.json 포맷은 그대로 유지해뒀어요.
