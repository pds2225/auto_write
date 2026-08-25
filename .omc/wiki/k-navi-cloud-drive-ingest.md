---
title: "K-Navi cloud Drive ingest"
tags: ["k-navi", "google-drive", "cloud-agent", "gdown", "mcp"]
created: 2026-08-20T06:45:00.000Z
updated: 2026-08-20T06:45:00.000Z
sources: ["session-2026-08-20-k-navi-mvp"]
links: ["k-navi-mvp-highlight-edit.md", "session-2026-08-20-k-navi-mvp.md"]
category: environment
confidence: high
schemaVersion: 1
---

# K-Navi cloud Drive ingest

Cursor 클라우드 VM은 사용자 Windows `Downloads`를 읽지 못한다. 경로 문자열을 붙여넣는 것은 파일 첨부가 아니다. 편집은 [[K-Navi MVP highlight edit]]. 세션은 [[Session 2026-08-20 K-Navi MVP]].

## 실측 차단

1. 로컬 경로 `c:\Users\…\케이네비 녹화영상 .mp4` → VM에 파일 없음.
2. Drive MCP `download_file_content` → **10MB 한도**. 이 원본은 ~27.3MB라 실패.
3. `gdown`은 파일이 비공개면 실패.

## 통과 경로

1. Drive 링크에서 file id를 뺀다 (`/file/d/<id>/view`).
2. 공유를 **링크 있는 사람 = 뷰어**로 두는 것이 원칙. 이 세션은 writer로 열려 `gdown`이 됐다.
3. `gdown --fuzzy 'https://drive.google.com/file/d/<id>/view' -O /tmp/knavi_recording.mp4`
4. **작업 후 공유를 제한됨으로 되돌린다.** anyone-writer는 너무 열림.
5. Drive MCP `create_file`로 빈 mp4를 올리지 말 것. 산출은 Cursor 아티팩트.

## 인식 신호

"이 경로 영상 잘라줘", Drive `view?usp=sharing`, MCP 10MB 에러, gdown 403/private.
