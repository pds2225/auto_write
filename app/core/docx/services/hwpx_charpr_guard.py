# -*- coding: utf-8 -*-
"""hwpx_charpr_guard — charPr append-only 불변(L076).

검정 클론·서식 추가는 항상 목록 **끝**에 append 해야 한다.
중간에 끼워 넣으면 id 와 자식 인덱스가 어긋나 한글이 엉뚱한 charPr 를
참조한다(실측 교훈 L076).
"""
from __future__ import annotations

from typing import Any, Optional


def _local(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def iter_charpr_elements(header_root) -> list:
    """header 안 charPr 요소를 문서 순서로 반환."""
    if header_root is None:
        return []
    return [el for el in header_root.iter() if _local(getattr(el, "tag", "")) == "charPr" and el.get("id")]


def check_charpr_append_only(header_root) -> list[str]:
    """숫자 id charPr 가 오름차순·끝 append 체계를 지키는지 검사.

    반환: 위반 메시지 목록(비어 있으면 OK).
    - 숫자 id 가 아니면 해당 항목은 건너뛴다(비숫자 체계는 보수적으로 통과).
    - 숫자 id 들만 모아, 문서 순서상의 숫자 id 수열이 비감소인지 확인.
    - 같은 parent 안에서 숫자 id 의 최대값이 마지막 숫자-id 자식이어야 한다
      (중간에 더 큰 id 를 끼워 넣은 경우 검출).
    """
    violations: list[str] = []
    els = iter_charpr_elements(header_root)
    numeric = [(el, int(el.get("id"))) for el in els if str(el.get("id", "")).isdigit()]
    if not numeric:
        return violations

    # 문서 순서 숫자 id 비감소(같거나 증가)
    prev: Optional[int] = None
    for el, nid in numeric:
        if prev is not None and nid < prev:
            violations.append(
                f"charPr id={nid} 가 이전 id={prev} 보다 작음(중간 삽입 의심)"
            )
        prev = nid

    # parent 별: 마지막 숫자-id 자식 == max(id)
    by_parent: dict[int, list[tuple[Any, int]]] = {}
    for el, nid in numeric:
        par = el.getparent()
        by_parent.setdefault(id(par) if par is not None else 0, []).append((el, nid))
    for group in by_parent.values():
        if len(group) < 2:
            continue
        max_id = max(nid for _, nid in group)
        last_id = group[-1][1]
        if last_id != max_id:
            violations.append(
                f"parent 끝 charPr id={last_id} != max id={max_id} (append-only 위반)"
            )
    return violations


def assert_charpr_append_only(header_root) -> None:
    """위반 시 ValueError — BlackCharPr 클론 직후 호출용."""
    bad = check_charpr_append_only(header_root)
    if bad:
        raise ValueError("charPr append-only 위반(L076): " + "; ".join(bad))
