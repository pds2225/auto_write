---
name: k-navi-mvp-highlight
description: >-
  케이네비 화면 녹화를 발표용 짧은 영상으로 자를 때 써요. “케이네비 영상”, “K-Navi 녹화”, “MVP 하이라이트”, “발표 영상 잘라”, “KICXUP 데모 클립”, “이 녹화 편집해줘” 같은 말을 하면 쓸 장면만 골라 이어 붙이고 16:9 발표 화면도 만들어요.
---
# k-navi-mvp-highlight — KICXUP MVP 화면녹화 하이라이트

## 실행 환경 (Grok Bot에서 실행할 때)
- 영상 편집(ffmpeg)은 박스(/workspace)에서 한다. 원본이 노트북에 있으면 CopyToBox(machineId `b09d5493-c6d4-4760-b6fa-a855d89774e9`)로 가져오고, 드라이브에 있으면 DownloadFile(구글 드라이브)로 받는다(크기 제한 없음). 공유 권한을 바꾸게 했다면 끝나고 되돌리라고 알려준다.
- 결과 영상은 사용자에게 파일로 보내거나, 요청하면 드라이브에 올린다.


## 언제 쓰나

케이네비 실녹화(또는 Drive 링크)를 받아 **발표에 넣을 짧은 클립**을 만들 때.
문서 품질·양식 채움 요청이 아니다. 지식 정본: `.omc/wiki/k-navi-mvp-highlight-edit.md`,
`.omc/wiki/k-navi-cloud-drive-ingest.md`.

## 원리

보이는 것만이 주장이다. 이 녹화는 **목적지 검색 → TMAP 보행 경로 → 회전 카드**만
증명한다. 없는 기능(사진 랜드마크, SBAS/KASS, 초정밀)을 클립이나 나레이션에 넣지 않는다.

## 1) 원본 입수 (클라우드)

Windows `c:\Users\…\Downloads\…mp4` 문자열 ≠ 파일. VM에 없으면 Drive.

1. URL에서 file id (`/file/d/<id>/view`).
2. 구글 드라이브 연결 `download_file_content`는 **10MB 한도** → 이 원본(~27MB)은 실패.
3. 공유가 막혀 있으면 `gdown` 실패. 뷰어 공유 후:
   `gdown --fuzzy 'https://drive.google.com/file/d/<id>/view' -O /tmp/knavi_recording.mp4`
4. anyone-writer로 열었으면 **작업 후 제한됨으로 되돌리라고 사용자에게 말한다.**
5. 빈 mp4를 Drive `create_file`로 올리지 말 것. 산출 영상은 사용자에게 파일로 전달한다(SendToUser/드라이브 업로드).

이 세션 원본 id: `1_BUufLAantULLQkHEQshEAHMgxAcjxqz` (`케이네비 녹화영상 .mp4`, 2:21, 620×1006, 무음).

## 2) Keep / Cut (이 녹화 정본)

Keep (원본 초):

| 초 | 화면 |
|----|------|
| `14.80–17.60` | 여의도역 5호선 검색·선택, 걷기 |
| `30.50–37.20` | 다음 회전 135m / 좌회전 후 111m, 경로 유지 |
| `46.00–53.00` | 총 403m · 도보 약 5분, 출발/회전/목적지 |

Cut: 빈화면·동의, GPS 경고만 있는 구간, 다른 창(Slides/rhwp), 설정·이탈점수·heading,
랜드마크 0/3, 재검색, 진단 JSON/초기화, Streamlit Manage app 크롬.

새 녹화가 오면 **같은 원칙으로 다시 컷시트**를 짠다. 위 초는 이 파일 전용.

## 3) 자르기 (ffmpeg)

창 제목+하단 Manage app 제거: crop `620:920:0:48`. GPS 배지를 `drawbox`로 가리지 말 것
(파란 회전 카드 글자를 덮는다). 원하면 클립 아래 “실내 테스트” 자막만.

```bash
SRC=/tmp/knavi_recording.mp4
ffmpeg -y -i "$SRC" -filter_complex "
[0:v]trim=start=14.80:end=17.60,setpts=PTS-STARTPTS,crop=620:920:0:48[v1];
[0:v]trim=start=30.50:end=37.20,setpts=PTS-STARTPTS,crop=620:920:0:48[v2];
[0:v]trim=start=46.00:end=53.00,setpts=PTS-STARTPTS,crop=620:920:0:48[v3];
[v1][v2][v3]concat=n=3:v=1:a=0[vout]
" -map "[vout]" -an -c:v libx264 -pix_fmt yuv420p /workspace/out/knavi_mvp_highlight.mp4

ffmpeg -y -i /workspace/out/knavi_mvp_highlight.mp4 \
  -vf "scale=620:920,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x081C3A" \
  -an -c:v libx264 -pix_fmt yuv420p /workspace/out/knavi_mvp_highlight_16x9.mp4
```

영상은 git 커밋 금지.

## 4) 성공 기준

- 길이 ~16.5초, 무음(원본 오디오 없으면 `-an`).
- 세 장면이 위 Keep 순서. 창 전환·JSON·랜드마크 0/3·Manage app 없음.
- 16:9는 세로 앱 + 남색 패딩. PPT Solution(3) 또는 현재단계(8).
- 나레이션: “목적지를 넣으면 보행 경로가 바로 그려집니다. 여의도역까지 403m, 약 5분.”
- 저장 전 ffmpeg로 프레임 몇 장을 PNG로 뽑아 Read로 화면 글자를 직접 확인한다.

## 함정

- 경로 텍스트를 파일로 착각.
- MCP 10MB로 큰 영상 다운로드.
- GPS 가리개가 안내 문구를 가림.
- 랜드마크/KASS를 이 클립으로 약속.
- `_DRAFT`/품질점수 게이트를 이 작업에 적용(해당 없음).
