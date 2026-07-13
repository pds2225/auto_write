"""sft_export.py — SFT 데이터 레이어 P2: 축적된 trace+feedback → 학습 데이터.

두 산출물을 만든다(둘 다 순수 함수, 부수효과 없음 — CLI/소비자가 파일로 씀).

1) SFT 학습셋(chat JSONL): P0 generation_traces(질문+Context→AI응답)에 P1 feedback
   (사람 최종 수정본)을 조인해 (system, user, assistant) 예시로 만든다.
   - assistant 는 **사람 승인본 우선**(feedback.after), 없으면 AI 응답.
   - draft_rejected(사람이 빈칸으로 거부)한 답은 정답에서 제외.
   - 폴백/빈 응답/파싱 실패 trace 제외, (project_id,qid) dedup, 선택적 PII 마스킹.

2) learned_snippets(생성 소비자용): 사람 승인본을 항목 라벨로 묶은 few-shot 코퍼스.
   **날조0 안전장치**: 항상 수치·PII 를 마스킹해 저장한다(다른 사업의 실제 수치·
   고유명사가 새 문서로 새지 않게). 문체·구성 참고용으로만 generate 컨텍스트에 주입.

learn_run.py 관례(§9)를 따른다: 점수 날조 없음·정확 파싱만·부수효과와 판정 분리.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import generation_store, learning_store

_DRAFT_PURPOSE = "draft_answers"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RRN_RE = re.compile(r"\d{6}\s*-\s*\d{7}")
_PHONE_RE = re.compile(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}")
_DIGITS_RE = re.compile(r"\d+")
_LABEL_NORM_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def mask_pii(text: str) -> str:
    """이메일·주민번호·전화번호를 자리표시로 마스킹."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[이메일]", text)
    text = _RRN_RE.sub("[주민번호]", text)
    text = _PHONE_RE.sub("[전화]", text)
    return text


def mask_facts(text: str) -> str:
    """PII + 모든 숫자를 N 으로 마스킹(수치 사실 유출 차단 — 문체 참고용)."""
    if not text:
        return text
    return _DIGITS_RE.sub("N", mask_pii(text))


def _normalize_label(label: str) -> str:
    return _LABEL_NORM_RE.sub("", str(label or "")).lower()


def _draft_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        t for t in traces
        if str(t.get("purpose", "")) == _DRAFT_PURPOSE and not t.get("empty", False)
    ]


def _parse_bodies(trace: dict[str, Any], root) -> tuple[str, dict, dict] | None:
    """trace blob 을 되읽어 (system_prompt, {questions,context}, {qid:answer}) 로 파싱.

    user_prompt·raw_response 가 정상 JSON 이 아니면 None(파싱 실패 → 제외).
    """
    bodies = generation_store.resolve_trace_bodies(trace, root)
    try:
        user_obj = json.loads(bodies["user_prompt"])
        resp_obj = json.loads(bodies["raw_response"])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(user_obj, dict) or not isinstance(resp_obj, dict):
        return None
    return bodies["system_prompt"], user_obj, resp_obj


def _feedback_maps(feedbacks: list[dict[str, Any]]) -> tuple[dict, set]:
    """feedback → ((project_id,qid)→최신 사람수정본, 거부된 (project_id,qid) 집합)."""
    approved: dict[tuple[str, str], str] = {}
    rejected: set[tuple[str, str]] = set()
    for f in feedbacks:
        key = (str(f.get("project_id", "")), str(f.get("qid", "")))
        action = str(f.get("action_type", ""))
        after = str((f.get("feedback") or {}).get("after", ""))
        if action == "edited" and after.strip():
            approved[key] = after
            rejected.discard(key)
        elif action == "draft_rejected":
            if key not in approved:
                rejected.add(key)
    return approved, rejected


def build_examples(
    traces: list[dict[str, Any]],
    feedbacks: list[dict[str, Any]],
    root=None,
    mask: bool = False,
) -> list[dict[str, Any]]:
    """(project_id,qid) 단위 SFT 예시 목록. 사람 승인본 우선, dedup, 선택 마스킹."""
    approved, rejected = _feedback_maps(feedbacks)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for trace in _draft_traces(traces):
        parsed = _parse_bodies(trace, root)
        if parsed is None:
            continue
        system_prompt, user_obj, resp_obj = parsed
        context = str(user_obj.get("context", ""))
        questions = user_obj.get("questions", [])
        qmeta: dict[str, dict] = {}
        if isinstance(questions, list):
            for q in questions:
                if isinstance(q, dict):
                    qmeta[str(q.get("question_id", ""))] = q
        project_id = str(trace.get("project_id", ""))
        for qid, ai_answer in resp_obj.items():
            qid = str(qid)
            key = (project_id, qid)
            human = approved.get(key)
            if human is not None:
                assistant, source = human, "human"
            elif key in rejected:
                continue  # 사람이 거부한 답은 정답으로 쓰지 않는다
            else:
                assistant, source = str(ai_answer or ""), "ai"
            if not assistant.strip():
                continue
            # dedup: 사람 승인본이 AI 본을 항상 이긴다.
            existing = by_key.get(key)
            if existing is not None and existing["source"] == "human" and source == "ai":
                continue
            q = qmeta.get(qid, {})
            label = str(q.get("label", "")).strip()
            kind = str(q.get("target", {}).get("kind", "")) if isinstance(q.get("target"), dict) else ""
            user_content = (
                f"[작성 항목] {label or qid}\n[참고 컨텍스트]\n{context}\n\n"
                "위 '작성 항목'을 참고 컨텍스트에 근거해 한국어로 작성하세요."
            )
            if mask:
                user_content = mask_facts(user_content)
                assistant = mask_facts(assistant)
            by_key[key] = {
                "project_id": project_id,
                "qid": qid,
                "label": label,
                "kind": kind,
                "source": source,
                "system": system_prompt,
                "user": user_content,
                "assistant": assistant,
            }
    return list(by_key.values())


def to_chat_jsonl(examples: list[dict[str, Any]]) -> str:
    """예시 목록 → chat messages JSONL 문자열(1줄 1예시)."""
    lines: list[str] = []
    for ex in examples:
        row = {
            "messages": [
                {"role": "system", "content": ex["system"]},
                {"role": "user", "content": ex["user"]},
                {"role": "assistant", "content": ex["assistant"]},
            ],
            "meta": {
                "project_id": ex["project_id"], "qid": ex["qid"],
                "label": ex["label"], "source": ex["source"],
            },
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def build_learned_snippets(
    traces: list[dict[str, Any]],
    feedbacks: list[dict[str, Any]],
    root=None,
) -> dict[str, list[str]]:
    """사람 승인본을 항목 라벨(정규화)로 묶은 few-shot 코퍼스. **항상 수치·PII 마스킹**.

    section 계열 서술 항목만 대상(표 셀=사실칸은 제외해 수치 유출·오전사 방지).
    """
    approved, _ = _feedback_maps(feedbacks)
    if not approved:
        return {}
    # qid → (label, kind) 를 draft trace 에서 확보.
    qid_meta: dict[tuple[str, str], tuple[str, str]] = {}
    for trace in _draft_traces(traces):
        parsed = _parse_bodies(trace, root)
        if parsed is None:
            continue
        _system, user_obj, _resp = parsed
        project_id = str(trace.get("project_id", ""))
        questions = user_obj.get("questions", [])
        if isinstance(questions, list):
            for q in questions:
                if not isinstance(q, dict):
                    continue
                qid = str(q.get("question_id", ""))
                kind = str(q.get("target", {}).get("kind", "")) if isinstance(q.get("target"), dict) else ""
                qid_meta[(project_id, qid)] = (str(q.get("label", "")), kind)
    out: dict[str, list[str]] = {}
    for (project_id, qid), answer in approved.items():
        label, kind = qid_meta.get((project_id, qid), ("", ""))
        if kind and kind != "section":
            continue
        norm = _normalize_label(label)
        if not norm:
            continue
        masked = mask_facts(answer).strip()
        if not masked:
            continue
        bucket = out.setdefault(norm, [])
        if masked not in bucket:
            bucket.append(masked)
    return out


def export_all(root=None, mask: bool = False) -> dict[str, Any]:
    """learning_store 에서 읽어 예시·learned_snippets 를 만든다(파일 쓰기는 CLI 담당)."""
    traces = learning_store.load_generation_traces(root=root)
    feedbacks = learning_store.load_feedback(root=root)
    examples = build_examples(traces, feedbacks, root=root, mask=mask)
    learned = build_learned_snippets(traces, feedbacks, root=root)
    human = sum(1 for e in examples if e["source"] == "human")
    return {
        "examples": examples,
        "jsonl": to_chat_jsonl(examples),
        "learned": learned,
        "counts": {
            "traces": len(traces),
            "feedbacks": len(feedbacks),
            "examples": len(examples),
            "human_approved": human,
            "ai_only": len(examples) - human,
            "learned_labels": len(learned),
        },
    }
