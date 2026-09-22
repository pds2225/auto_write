"""web_draft.py — 공고문+양식 → 다른 AI 전달용 계획서 초안(MD) 생성 웹 UI.

Streamlit 기반. 파일 업로드 또는 링크(URL) 입력 지원.
기존 auto_write 서비스(announcement_analyzer, form_analyzer, document_ingest)를 그대로 재사용.

실행:
    cd D:\\auto_write\\app
    streamlit run web_draft.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st

# ── import 경로 설정 ──────────────────────────────────────────────
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from auto_write.services.doc_text_extract import extract_text
from auto_write.services.announcement_analyzer import analyze_announcement
from auto_write.services.form_analyzer import analyze_form, FormReport


# ── 상수 ──────────────────────────────────────────────────────────
UPLOAD_DIR = Path(tempfile.gettempdir()) / "web_draft_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ACCEPTED_EXTS = {".hwp", ".hwpx", ".docx", ".pdf", ".txt", ".md"}


# ── 유틸리티 ──────────────────────────────────────────────────────
def _save_uploaded(uploaded_file, prefix: str) -> Path:
    """Streamlit UploadedFile을 임시 파일로 저장하고 경로를 반환."""
    suffix = Path(uploaded_file.name).suffix
    out = UPLOAD_DIR / f"{prefix}{suffix}"
    out.write_bytes(uploaded_file.read())
    return out


def _download_from_url(url: str, prefix: str) -> Path:
    """URL에서 파일을 다운로드. Google Drive/Naver/direct URL 지원."""
    import requests

    url = url.strip()
    if not url:
        raise ValueError("URL이 비어 있습니다.")

    # Google Drive 공유 링크 → 직접 다운로드 URL 변환
    drive_match = re.search(r"drive\.google\.com/(?:file/d/|uc\?id=)([a-zA-Z0-9_-]+)", url)
    if drive_match:
        file_id = drive_match.group(1)
        url = f"https://drive.google.com/uc?export=download&id={file_id}"

    # Naver MyBox / 일반 공유 링크는 직접 다운로드 시도
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True, stream=True)
    resp.raise_for_status()

    # Content-Disposition에서 파일명 추출 시도
    cd = resp.headers.get("Content-Disposition", "")
    fname_match = re.search(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\s]+)', cd)
    if fname_match:
        fname = fname_match.group(1)
    else:
        # URL에서 파일명 추출
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        fname = unquote(Path(parsed.path).name) or "downloaded"

    # 확장자 보정
    suffix = Path(fname).suffix
    if suffix not in ACCEPTED_EXTS:
        # Content-Type으로 추정
        ct = resp.headers.get("Content-Type", "")
        ct_map = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/msword": ".docx",
            "application/pdf": ".pdf",
            "text/plain": ".txt",
        }
        suffix = ct_map.get(ct.split(";")[0].strip(), ".bin")
        fname = Path(fname).stem + suffix

    out = UPLOAD_DIR / f"{prefix}{suffix}"
    with open(out, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return out


def _extract_text_from_file(path: Path) -> str:
    """파일에서 텍스트 추출. extract_text가 모든 형식(HWP/HWPX/DOCX/PDF/TXT/MD)을 처리."""
    text, _ = extract_text(str(path))
    return text or ""


def _get_file(source_type: str, uploaded, url_input: str, prefix: str) -> Optional[Path]:
    """파일 소스 타입에 따라 파일 경로 반환."""
    if source_type == "파일 업로드" and uploaded is not None:
        return _save_uploaded(uploaded, prefix)
    elif source_type == "링크 (URL)" and url_input.strip():
        return _download_from_url(url_input.strip(), prefix)
    return None


# ── MD 초안 생성 ──────────────────────────────────────────────────
def _generate_draft_md(
    announcement_text: str,
    form_text: str,
    announcement_report,
    form_report: FormReport,
    company_info: str = "",
) -> str:
    """공고 분석 + 양식 분석 결과를 다른 AI에게 전달할 MD로 조립."""

    lines: list[str] = []
    lines.append("# 사업계획서 초안 브리프")
    lines.append("")
    lines.append("> 이 문서는 AI가 사업계획서를 작성할 때 필요한 정보를 담고 있습니다.")
    lines.append("> 아래 정보를 바탕으로 사업계획서 본문을 작성해 주세요.")
    lines.append("")

    # ── 1. 공고 분석 ──
    lines.append("## 1. 공고 분석 결과")
    lines.append("")

    ki = announcement_report.key_info or {}
    criteria = announcement_report.criteria or []

    if ki.get("support_target"):
        lines.append(f"**지원대상**: {ki['support_target']}")
    if ki.get("eligibility"):
        lines.append(f"**지원자격**: {ki['eligibility']}")
    if ki.get("funding_amount"):
        lines.append(f"**지원금액**: {ki['funding_amount']}")
    if ki.get("deadline"):
        lines.append(f"**신청마감**: {ki['deadline']}")
    if ki.get("support_content"):
        lines.append(f"**지원내용**: {ki['support_content']}")
    if ki.get("bonus_points"):
        lines.append(f"**가점/우대**: {ki['bonus_points']}")
    if ki.get("required_documents"):
        docs = ki["required_documents"]
        if isinstance(docs, list) and docs:
            lines.append(f"**제출서류**: {', '.join(docs)}")
    if ki.get("notes"):
        lines.append(f"**유의사항**: {ki['notes']}")

    lines.append("")

    if criteria:
        lines.append("### 평가기준·배점")
        lines.append("")
        lines.append("| 평가항목 | 배점 | 비고 |")
        lines.append("|----------|------|------|")
        for c in criteria:
            name = c.get("name", "")
            score = c.get("max_score", 0)
            desc = c.get("description", "")
            lines.append(f"| {name} | {score} | {desc} |")
        total = announcement_report.total_max_score
        if total:
            lines.append(f"| **합계** | **{total}** | |")
        lines.append("")

    # ── 2. 양식 분석 ──
    lines.append("## 2. 양식 구조 분석")
    lines.append("")

    if form_report.template_name:
        lines.append(f"**양식명**: {form_report.template_name}")
    lines.append(f"**작성 항목 수**: {form_report.question_count}개 (필수 {form_report.required_question_count}개)")
    lines.append(f"**표 수**: {form_report.table_count}개 | **이미지 슬롯**: {form_report.image_slot_count}개")

    psst = form_report.psst_present or {}
    if psst:
        psst_status = []
        for k, label in [("problem", "P"), ("solution", "S"), ("scale", "S"), ("team", "T")]:
            if k in psst:
                psst_status.append(f"{label}:{'O' if psst[k] else 'X'}")
        lines.append(f"**PSST 구조**: {' / '.join(psst_status)}")

    lines.append("")

    items = form_report.writable_item_details or []
    if items:
        lines.append("### 작성 항목 목록")
        lines.append("")
        lines.append("| # | 항목명 | 유형 | 필수 |")
        lines.append("|---|--------|------|------|")
        for i, item in enumerate(items, 1):
            label = item.get("label", "")
            kind = item.get("field_kind", "fact")
            kind_label = "서술" if kind == "narrative" else "사실"
            req = "O" if item.get("required") else ""
            lines.append(f"| {i} | {label} | {kind_label} | {req} |")
        lines.append("")

    # ── 3. 기업 정보 ──
    if company_info.strip():
        lines.append("## 3. 기업 정보 (신청자 제공)")
        lines.append("")
        lines.append(company_info.strip())
        lines.append("")

    # ── 4. 공고 원문 (발췌) ──
    lines.append("## 4. 공고 원문 (발췌)")
    lines.append("")
    lines.append("```")
    lines.append(announcement_text[:5000])
    if len(announcement_text) > 5000:
        lines.append(f"\n... (총 {len(announcement_text)}자 중 5000자만 표시)")
    lines.append("```")
    lines.append("")

    # ── 5. 양식 원문 (발췌) ──
    lines.append("## 5. 양식 원문 (발췌)")
    lines.append("")
    lines.append("```")
    lines.append(form_text[:5000])
    if len(form_text) > 5000:
        lines.append(f"\n... (총 {len(form_text)}자 중 5000자만 표시)")
    lines.append("```")
    lines.append("")

    # ── 6. 작성 지시 ──
    lines.append("## 6. AI 작성 지시")
    lines.append("")
    lines.append("위 공고 분석과 양식 구조를 바탕으로 사업계획서를 작성해 주세요:")
    lines.append("")
    lines.append("1. **평가기준 기반 작성**: 위 평가기준·배점 비중에 맞춰 내용을 배분하세요.")
    lines.append("2. **PSST 구조 준수**: Problem(문제인식) → Solution(실현가능성) → Scale-up(성장전략) → Team(팀구성) 순서로 작성하세요.")
    lines.append("3. **근거 명시**: 수치·통계는 출처를 반드시 병기하세요. 출처 불명확한 수치는 `[확인필요]`로 표시하세요.")
    lines.append("4. **허위 금지**: 정부지원사업 허위기재는 형사처벌 대상입니다. 확인된 사실만 기재하세요.")
    lines.append("5. **양식 항목별 작성**: 위 '작성 항목 목록'의 각 항목에 맞는 내용을 작성하세요.")
    lines.append("")

    return "\n".join(lines)


# ── Streamlit UI ──────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="공고+양식 → 사업계획서 초안",
        page_icon="📋",
        layout="wide",
    )

    st.title("📋 공고문 + 양식 → 사업계획서 초안 생성")
    st.caption("공고문과 신청서 양식을 업로드하면, 다른 AI에게 전달할 계획서 초안(MD)을 생성합니다.")

    # ── 입력 영역 ──
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 공고문")
        ann_source = st.radio(
            "공고문 입력 방식",
            ["파일 업로드", "링크 (URL)"],
            key="ann_source",
            horizontal=True,
        )
        ann_file = None
        ann_url = ""
        if ann_source == "파일 업로드":
            ann_file = st.file_uploader(
                "공고문 파일",
                type=["hwp", "hwpx", "docx", "pdf", "txt", "md"],
                key="ann_upload",
            )
        else:
            ann_url = st.text_input(
                "공고문 URL",
                placeholder="https://drive.google.com/file/d/... 또는 직접 URL",
                key="ann_url",
            )

    with col2:
        st.subheader("📝 신청서 양식")
        form_source = st.radio(
            "양식 입력 방식",
            ["파일 업로드", "링크 (URL)"],
            key="form_source",
            horizontal=True,
        )
        form_file = None
        form_url = ""
        if form_source == "파일 업로드":
            form_file = st.file_uploader(
                "신청서 양식 파일",
                type=["hwp", "hwpx", "docx", "pdf", "txt", "md"],
                key="form_upload",
            )
        else:
            form_url = st.text_input(
                "양식 URL",
                placeholder="https://drive.google.com/file/d/... 또는 직접 URL",
                key="form_url",
            )

    # ── 기업 정보 (선택) ──
    with st.expander("🏢 기업 정보 (선택사항)", expanded=False):
        company_info = st.text_area(
            "기업 정보를 입력하면 계획서 초안에 반영됩니다.",
            placeholder="예:\n- 회사명: (주)테크스타트\n- 대표자: 홍길동\n- 업력: 3년차\n- 주요 사업: AI 기반 물류 최적화\n- 매출: 2025년 5억원\n- 특허: 2건 보유",
            height=150,
        )

    # ── 실행 버튼 ──
    st.divider()

    can_run = (ann_file is not None or ann_url.strip()) and (form_file is not None or form_url.strip())

    if st.button("🚀 초안 생성", type="primary", disabled=not can_run, use_container_width=True):
        run_pipeline(ann_source, ann_file, ann_url, form_source, form_file, form_url, company_info)

    if not can_run:
        st.info("공고문과 신청서 양식을 모두 입력해 주세요.")


def run_pipeline(ann_source, ann_file, ann_url, form_source, form_file, form_url, company_info):
    """파이프라인 실행."""

    progress = st.progress(0, text="시작...")

    # ── Step 1: 파일 확보 ──
    progress.progress(10, text="1/4 공고문 파일 확보 중...")
    try:
        ann_path = _get_file(ann_source, ann_file, ann_url, "announcement")
        if not ann_path:
            st.error("공고문 파일을 확보하지 못했습니다.")
            return
    except Exception as e:
        st.error(f"공고문 다운로드 실패: {e}")
        return

    progress.progress(20, text="1/4 양식 파일 확보 중...")
    try:
        form_path = _get_file(form_source, form_file, form_url, "form")
        if not form_path:
            st.error("양식 파일을 확보하지 못했습니다.")
            return
    except Exception as e:
        st.error(f"양식 다운로드 실패: {e}")
        return

    # ── Step 2: 텍스트 추출 ──
    progress.progress(30, text="2/4 공고문 텍스트 추출 중...")
    announcement_text = _extract_text_from_file(ann_path)
    if not announcement_text.strip():
        st.warning("공고문에서 텍스트를 추출하지 못했습니다. 파일 형식을 확인해 주세요.")
        announcement_text = "(텍스트 추출 실패)"

    progress.progress(40, text="2/4 양식 텍스트 추출 중...")
    form_text = _extract_text_from_file(form_path)
    if not form_text.strip():
        st.warning("양식에서 텍스트를 추출하지 못했습니다. 파일 형식을 확인해 주세요.")
        form_text = "(텍스트 추출 실패)"

    # ── Step 3: 분석 ──
    progress.progress(50, text="3/4 공고문 분석 중...")
    ann_report = analyze_announcement(announcement_text, is_text=True)

    progress.progress(60, text="3/4 양식 구조 분석 중...")
    try:
        form_report = analyze_form(form_path)
    except Exception as e:
        st.warning(f"양식 구조 분석 실패: {e}. 텍스트만 사용합니다.")
        form_report = FormReport(template_name=form_path.name)

    # ── Step 4: MD 생성 ──
    progress.progress(80, text="4/4 초안 MD 생성 중...")
    md_content = _generate_draft_md(
        announcement_text=announcement_text,
        form_text=form_text,
        announcement_report=ann_report,
        form_report=form_report,
        company_info=company_info,
    )

    progress.progress(100, text="완료!")

    # ── 결과 표시 ──
    st.divider()
    st.subheader("📊 분석 결과 요약")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**공고 분석**")
        ki = ann_report.key_info or {}
        if ki.get("deadline"):
            st.write(f"마감: {ki['deadline']}")
        if ki.get("funding_amount"):
            st.write(f"지원금: {ki['funding_amount']}")
        st.write(f"평가기준: {len(ann_report.criteria)}개 항목")
        st.write(f"공고 텍스트: {len(announcement_text):,}자")

    with col_b:
        st.markdown("**양식 분석**")
        st.write(f"작성 항목: {form_report.question_count}개")
        st.write(f"표: {form_report.table_count}개")
        psst = form_report.psst_present or {}
        psst_ok = sum(1 for v in psst.values() if v)
        st.write(f"PSST 구조: {psst_ok}/4 영역")
        st.write(f"양식 텍스트: {len(form_text):,}자")

    # ── MD 미리보기 ──
    st.subheader("📝 생성된 초안 (MD)")
    st.code(md_content, language="markdown", line_numbers=True)

    # ── 다운로드 ──
    st.download_button(
        "📥 MD 파일 다운로드",
        data=md_content.encode("utf-8"),
        file_name="bizplan_draft_brief.md",
        mime="text/markdown",
        type="primary",
        use_container_width=True,
    )

    # ── 텍스트 미리보기 (접기) ──
    with st.expander("📄 추출된 공고문 텍스트 (전체)", expanded=False):
        st.text(announcement_text[:10000])

    with st.expander("📄 추출된 양식 텍스트 (전체)", expanded=False):
        st.text(form_text[:10000])

    # ── 정리 ──
    try:
        ann_path.unlink(missing_ok=True)
        form_path.unlink(missing_ok=True)
    except Exception:
        pass

    st.success("초안 브리프 MD가 생성되었습니다. 다른 AI에게 전달하세요!")


if __name__ == "__main__":
    main()
