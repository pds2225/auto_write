---
name: k-navi-mvp-highlight-workflow
description: Cloud agents cannot read Windows paths; Drive MCP caps at 10MB; K-Navi pitch clips may only claim what the recording shows.
triggers:
  - 케이네비 영상
  - K-Navi 녹화
  - MVP 하이라이트
  - KICXUP 데모
  - Drive mp4 10MB
  - gdown private
---

# K-Navi MVP highlight workflow

## The Insight

A screen recording is evidence, not a product brochure. Cut to the three beats that exist (search → turn card → full route). Do not cover UI with boxes that collide with the turn subtitle. Cloud ingest is a different problem from editing: path text is not a file, and Drive MCP will not fetch a 27MB mp4.

## Why This Matters

Without this, agents stall on `c:\Users\…\Downloads`, hit the 10MB MCP cap, leave Streamlit chrome / other-window glitches in the pitch clip, or narrate landmarks/KASS that the video does not show.

## Recognition Pattern

User pastes a Windows mp4 path or Drive `/file/d/<id>/view`, says 편집/하이라이트/KICXUP/케이네비.

## The Approach

1. Ingest via `gdown` after share-as-viewer (restrict again after). Skip MCP download for files >10MB.
2. Build a keep/cut sheet from the actual frames, then ffmpeg concat + crop `620:920:0:48`.
3. Pad 16:9 `#081C3A` for PPT. Never git-commit the mp4.
4. Claims follow pixels. SOP: `.claude/skills/k-navi-mvp-highlight/SKILL.md`. Wiki: [[K-Navi MVP highlight edit]], [[K-Navi cloud Drive ingest]].
