---
name: promo-banner-localize
description: >-
  챌린지·IR 홍보 배너(K-Navi/KICXUP 등)를 한글/영문 짝으로 만들고 진짜 16:9로 맞출 때 사용.
  Cursor GenerateImage 의 aspect_ratio 는 픽셀 계약이 아니다(16:9 요청해도 1536×1024=3:2 가 나옴).
  반드시 PIL 로 실측한 뒤 하단 크레딧을 살리는 크롭으로 1920×1080 을 만든다.
  트리거: "배너 영문", "배너 한글", "16:9", "16대9", "홍보 이미지", "K-Navi", "K-네비",
  "케이내비", "사람을 서양인으로", "왼쪽 상단 숫자 빼", "01 빼줘", "같은 구도 번역".
---

# promo-banner-localize — 홍보 배너 한/영 짝 + 진짜 16:9

> 수확: 2026-08-20 K-Navi 세션. 문서 하네스(bizdoc-hub)와 별개. PNG 는 사용자가 원할 때만 git 커밋.

## 언제 쓰나

- 기존 배너/전단을 **다른 언어**로 같은 구도로 다시 만들 때
- **인물·배지·카피**를 바꾸되 레이아웃은 유지할 때
- **16:9** (발표 슬라이드·유튜브 썸네일) 를 요청받았을 때

문서 DOCX 다듬기는 `document-quality-orchestrator`. 이 스킬은 **이미지 배너** 전용.

## 핵심 원칙 (실측)

`GenerateImage(aspect_ratio="16:9")` 는 **픽셀을 보장하지 않는다.**
2026-08-20 실측: 요청은 16:9 인데 산출은 항상 `1536×1024` (3:2, 비율 1.5000).
이미지 설명 모델이 "16:9 배너"라고 말해도 **거짓말일 수 있다.**  cred는 픽셀만.

통과 기준: `width/height ≈ 1.7778` 또는 정확히 `1920×1080`.

## 입력

- 원본 이미지 경로 (있으면 `reference_image_paths` 에 넣는다)
- 언어: 한글 / 영문 / 둘 다
- 유지·변경: 인물, 숫자 배지, 브랜드명, 푸터 크레딧
- 카피 정본(사용자가 준 문장). 없으면 원본 OCR 후 번역하되 **브랜드·고유명사는 날조 금지**

## 절차

1. **프롬프트 불변**
   - `NO "01"`, `NO number badge`, 왼쪽 상단 숫자 라벨 금지 — 모델이 코너 번호를 다시 그림.
   - 인물 제약은 구체적으로 (예: blonde Caucasian woman, straw hat, backpack, looking at phone).
   - 바꿀 텍스트는 **한 글자까지** 프롬프트에 적는다. 푸터 `KICXUP` 를 `KICKUP` 으로 쓰지 말 것.
2. **짝 생성**
   - 한쪽을 먼저 만들고, 그 파일을 레퍼런스로 다른 언어를 생성한다. 구도·인물·폰 목업을 고정하고 **언어만** 바꾼다.
3. **실측** (생성 직후, 설명문 믿기 금지)

```python
from PIL import Image
im = Image.open(path)
w, h = im.size
print(w, h, round(w / h, 4), "16:9" if abs(w / h - 16 / 9) < 0.01 else "NOT 16:9")
```

4. **3:2 → 16:9 변환** (1536×1024 가 나온 경우)
   - 가로를 1920 으로 스케일 → `1920×1280`
   - 높이 200px 를 자른다. **위(하늘)에서 많이, 아래(푸터)에서 적게.**
   - 실측 기본값: 위 172px + 아래 28px → `1920×1080`
   - 타이틀이 잘리면 위 크롭을 줄이고, 푸터가 잘리면 아래 크롭을 더 줄인다.
   - 가로로 18% 늘리기(stretch) 금지. 흐린 양옆 패딩만으로 "16:9" 라고 보고하지 말 것.
5. **카피 검수**
   - 상단·좌측 카피·푸터를 crop 해서 읽는다.
   - 말풍선·지도 라벨이 요청 언어와 같은지 확인.
6. **산출 위치**
   - `/opt/cursor/artifacts/<name>_16x9.png` 에 복사해 사용자에게 보여 준다.
   - **git 에 PNG 커밋 금지** (사용자가 저장소/슬라이드 삽입을 명시할 때만).

## 성공 기준

- [ ] `1920×1080` (또는 비율 1.7778±0.01)
- [ ] 왼쪽 상단에 `01` 등 숫자 배지 없음
- [ ] 한/영 요청이면 **같은 구도·같은 인물** 두 장
- [ ] 푸터·브랜드 철자가 정본과 일치 (`KICXUP` 유지)
- [ ] 코드/테스트와 무관하면 RESUME 에 artifact 경로만 기록

## 카피 정본 (K-Navi / 2026-08-20)

영문: `K-Navi` / Satellite-based Pedestrian Navigation for Wayfinding Assistance / GNSS/SBAS + AI-based Precise Route Guidance / Resolves direction errors / Alley and entrance guidance / GPS error correction / Instant rerouting upon deviation / Multilingual support for foreigners / "Pass the convenience store and turn into the alley on the right." / "The entrance is right here." / `2026 KICXUP Challenge | K-Navi | CEO Dasom Park`

한글: `K-네비` / 길찾기 어려운 보행자를 위한 위성항법 도보 내비게이션 / GNSS/SBAS + AI 기반 정밀 길안내 / 방향 착오 해결 / 골목·출입구 안내 / GPS 오차 보정 / 경로 이탈 즉시 재안내 / 외국인 다국어 지원 / "편의점을 지나 오른쪽 골목으로 진입하세요" / "출입구 여기입니다" / `2026 KICXUP Challenge | 케이내비 | 대표 박다솜`

## 하지 말 것

- aspect_ratio 만 넣고 16:9 완료 보고
- 설명 모델이 "widescreen" 이라고 해서 실측 생략
- 원본 배너 파일을 저장소 `results/` 에 덮어쓰기
- bizdoc-hub 로 라우팅 (문서 파이프라인이 아님)
