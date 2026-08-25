---
title: "K-Navi MVP highlight edit"
tags: ["k-navi", "kicxup", "mvp", "video", "ffmpeg", "highlight"]
created: 2026-08-20T06:45:00.000Z
updated: 2026-08-20T06:45:00.000Z
sources: ["session-2026-08-20-k-navi-mvp"]
links: ["k-navi-cloud-drive-ingest.md", "session-2026-08-20-k-navi-mvp.md"]
category: convention
confidence: high
schemaVersion: 1
---

# K-Navi MVP highlight edit

KICXUP(발표평가 2026-08-19~08-21)용 케이네비 Streamlit **도보 내비게이션** 실녹화에서, 쓸 장면만 남긴다. 문서 하네스(`bizdoc-hub`) 대상이 아니다. 절차는 스킬 `k-navi-mvp-highlight`. 원본 입수는 [[K-Navi cloud Drive ingest]]. 세션 맥락은 [[Session 2026-08-20 K-Navi MVP]].

## 원본 (이 녹화)

Drive id `1_BUufLAantULLQkHEQshEAHMgxAcjxqz` · `케이네비 녹화영상 .mp4` · 2:21 · 620×1006 · h264+aac · 오디오 없음.

## Keep (원본 타임코드)

| 구간 | 화면 | 하이라이트 |
|------|------|------------|
| 00:15–00:18 (`14.80–17.60`) | 여의도역 5호선 검색·선택, 걷기 | 0:00–0:03 |
| 00:31–00:37 (`30.50–37.20`) | 다음 회전 135m / 좌회전 후 111m, 경로 유지 | 0:03–0:10 |
| 00:46–00:53 (`46.00–53.00`) | 총 403m · 도보 약 5분, 출발/회전/목적지 | 0:10–0:16 |

산출 ~16.5초. 세로 crop `620:920:0:48`(창 제목+Streamlit Manage app 제거). PPT용 16:9는 `1920×1080` 남색 `#081C3A` 패딩.

## Cut

00:00–00:07 빈화면/동의 · 00:18–00:28 GPS 경고만 · 00:38–00:40 다른 창(Google Slides / rhwp) · 00:54–01:19 설정·이탈점수·heading·랜드마크 0/3 · 01:20–01:55 재검색 · 01:56–02:21 진단 JSON/초기화.

## 발표에서 하지 말 것

이 녹화에 **사진·랜드마크 안내 없음**(0/3). SBAS/KASS·초정밀·마지막 100m 카피를 이 영상으로 증명하지 말 것. 나레이션: “목적지를 넣으면 보행 경로가 바로 그려집니다. 여의도역까지 403m, 약 5분.” PPT는 Solution 3장 또는 현재단계 8장.

## 함정

GPS 배지(±96~97m, 실내)를 흰 `drawbox`로 가리면 파란 회전 카드 자막을 덮는다 → 덮지 말 것. 필요하면 “실내 테스트” 자막만. 영상은 저장소 커밋 금지(아티팩트).
