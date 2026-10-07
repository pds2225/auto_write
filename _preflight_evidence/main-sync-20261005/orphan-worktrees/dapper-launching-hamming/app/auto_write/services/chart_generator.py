"""chart_generator.py

정부지원사업 사업계획서(.docx)에 삽입할 **데이터 차트·도식을 matplotlib 로
결정론적으로 생성**한다. 막대그래프·꺾은선·간트(추진일정)·조직도 4종을 지원하며,
각 함수는 PNG 파일을 만들고 저장 경로(str)를 반환한다.

설계 원칙(케이스 A):
  - 데이터(수치·항목·일정)는 **함수 인자로만** 받는다. 본 모듈은 어떤 숫자도
    임의로 지어내지 않으며, 더미데이터를 문서에 넣지 않는다.
  - 데이터가 없거나 형식이 잘못되면 차트를 만들지 않고 ``None`` 을 반환한다
    (예외를 던지지 않는다).

환경:
  - headless 환경에서 동작하도록 matplotlib backend 를 ``Agg`` 로 강제한다.
  - 한글 라벨 깨짐 방지를 위해 Windows ``Malgun Gothic``(맑은 고딕)을 사용한다.
    폰트가 없으면 fallback 경고만 출력하고 계속 진행한다.
"""

from __future__ import annotations

import warnings
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")  # headless 강제 (반드시 pyplot import 전에)

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

# --------------------------------------------------------------------------- 폰트
_KOREAN_FONT = "Malgun Gothic"


def _apply_korean_font() -> bool:
    """한글 폰트(맑은 고딕)를 적용한다. 사용 가능하면 True, 아니면 경고 후 False."""
    try:
        from matplotlib import font_manager

        available = {f.name for f in font_manager.fontManager.ttflist}
        if _KOREAN_FONT in available:
            matplotlib.rcParams["font.family"] = _KOREAN_FONT
            matplotlib.rcParams["axes.unicode_minus"] = False
            return True
    except Exception:  # pragma: no cover - 폰트 매니저 자체 실패
        pass
    warnings.warn(
        f"'{_KOREAN_FONT}' 폰트를 찾을 수 없어 기본 폰트로 대체합니다. "
        "한글 라벨이 깨질 수 있습니다.",
        RuntimeWarning,
        stacklevel=2,
    )
    matplotlib.rcParams["axes.unicode_minus"] = False
    return False


_FONT_OK = _apply_korean_font()

_DPI = 150


def _save(fig, out_png: str) -> str:
    """tight_layout 적용 후 저장하고 메모리를 해제한 뒤 경로를 반환한다."""
    fig.tight_layout()
    fig.savefig(out_png, dpi=_DPI)
    plt.close(fig)
    return out_png


def _is_num_seq(seq: Any) -> bool:
    """리스트/튜플이며 모든 원소가 숫자(bool 제외)인지 검사."""
    if not isinstance(seq, (list, tuple)) or not seq:
        return False
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in seq)


# --------------------------------------------------------------------------- 막대
def bar_chart(
    out_png: str,
    title: str,
    categories: list[str],
    values: list[float],
    ylabel: str = "",
) -> Optional[str]:
    """막대그래프(매출/실적 추이 등)를 PNG 로 저장하고 경로를 반환한다.

    categories/values 가 비었거나 길이가 다르거나 values 가 숫자가 아니면 None.
    """
    if not categories or not _is_num_seq(values):
        return None
    if len(categories) != len(values):
        return None
    try:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        bars = ax.bar(
            [str(c) for c in categories], values, color="#4C72B0", edgecolor="white"
        )
        ax.set_title(title, fontweight="bold", fontsize=14)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.bar_label(bars, fmt="%g", padding=3, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        return _save(fig, out_png)
    except Exception as exc:  # pragma: no cover - 렌더 실패 방어
        warnings.warn(f"bar_chart 생성 실패: {exc}", RuntimeWarning, stacklevel=2)
        return None


# --------------------------------------------------------------------------- 꺾은선
def line_chart(
    out_png: str,
    title: str,
    x: list,
    series: dict[str, list[float]],
    ylabel: str = "",
) -> Optional[str]:
    """다계열 꺾은선(성장 추이 등)을 PNG 로 저장하고 경로를 반환한다.

    x 가 비었거나 series 가 비었거나, 한 계열이라도 숫자가 아니거나 x 와 길이가
    다르면 None.
    """
    if not x or not isinstance(series, dict) or not series:
        return None
    for name, ys in series.items():
        if not _is_num_seq(ys) or len(ys) != len(x):
            return None
    try:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        xs = [str(v) for v in x]
        for name, ys in series.items():
            ax.plot(xs, ys, marker="o", linewidth=2, label=str(name))
        ax.set_title(title, fontweight="bold", fontsize=14)
        if ylabel:
            ax.set_ylabel(ylabel)
        if len(series) > 1:
            ax.legend()
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, linestyle="--", alpha=0.4)
        return _save(fig, out_png)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"line_chart 생성 실패: {exc}", RuntimeWarning, stacklevel=2)
        return None


# --------------------------------------------------------------------------- 간트
def gantt_chart(
    out_png: str,
    title: str,
    tasks: list[dict],
) -> Optional[str]:
    """추진일정 가로 막대 간트차트를 PNG 로 저장하고 경로를 반환한다.

    각 task = {"name": str, "start": int, "end": int} (start/end 는 월 인덱스/주차).
    tasks 가 비었거나, 항목에 name/start/end 가 없거나 start>=end 면 해당 항목을
    건너뛴다. 유효 항목이 하나도 없으면 None.
    """
    if not isinstance(tasks, list) or not tasks:
        return None
    valid: list[tuple[str, float, float]] = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        name = t.get("name")
        start = t.get("start")
        end = t.get("end")
        if name is None or start is None or end is None:
            continue
        if isinstance(start, bool) or isinstance(end, bool):
            continue
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        if end <= start:
            continue
        valid.append((str(name), float(start), float(end)))
    if not valid:
        return None
    try:
        fig, ax = plt.subplots(figsize=(8, max(2.0, 0.6 * len(valid) + 1.0)))
        names = [v[0] for v in valid]
        y_pos = range(len(valid))
        for i, (_, start, end) in enumerate(valid):
            ax.barh(
                i, end - start, left=start, height=0.5,
                color="#55A868", edgecolor="white",
            )
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(names)
        ax.invert_yaxis()  # 첫 task 가 위로
        ax.set_xlabel("기간(월/주차)")
        ax.set_title(title, fontweight="bold", fontsize=14)
        min_start = min(v[1] for v in valid)
        max_end = max(v[2] for v in valid)
        ax.set_xlim(min_start, max_end)
        ax.set_xticks(range(int(min_start), int(max_end) + 1))
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        return _save(fig, out_png)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"gantt_chart 생성 실패: {exc}", RuntimeWarning, stacklevel=2)
        return None


# --------------------------------------------------------------------------- 조직도
def _layout_tree(nodes: list[dict]) -> Optional[dict[str, tuple[float, float, str]]]:
    """노드 목록을 받아 {id: (x, y, label)} 좌표를 트리 레이아웃으로 계산한다.

    외부 graphviz 의존 없이 단순 부모-자식 트리를 직접 레이아웃한다.
    유효하지 않은 입력(루트 없음/순환/중복 id)이면 None.
    """
    by_id: dict[str, dict] = {}
    for n in nodes:
        if not isinstance(n, dict):
            return None
        nid = n.get("id")
        label = n.get("label")
        if nid is None or label is None:
            return None
        nid = str(nid)
        if nid in by_id:  # 중복 id
            return None
        by_id[nid] = {"label": str(label), "parent": n.get("parent")}

    children: dict[str, list[str]] = {nid: [] for nid in by_id}
    roots: list[str] = []
    for nid, info in by_id.items():
        parent = info["parent"]
        if parent is None:
            roots.append(nid)
        else:
            parent = str(parent)
            if parent not in by_id:
                return None  # 미존재 부모
            children[parent].append(nid)
    if len(roots) != 1:
        return None  # 루트가 정확히 1개여야 단순 트리

    # 후위 순회로 잎 x 좌표 부여, 내부 노드는 자식 중앙
    pos: dict[str, tuple[float, float, str]] = {}
    leaf_counter = [0.0]
    visited: set[str] = set()

    def assign(nid: str, depth: int) -> float:
        if nid in visited:  # 순환 방지
            raise ValueError("cycle detected")
        visited.add(nid)
        kids = children[nid]
        if not kids:
            x = leaf_counter[0]
            leaf_counter[0] += 1.0
        else:
            xs = [assign(k, depth + 1) for k in kids]
            x = sum(xs) / len(xs)
        pos[nid] = (x, float(-depth), by_id[nid]["label"])
        return x

    try:
        assign(roots[0], 0)
    except ValueError:
        return None
    if len(pos) != len(by_id):  # 도달 못한 노드(분리된 서브트리) 존재
        return None
    return pos


def org_chart(
    out_png: str,
    title: str,
    nodes: list[dict],
) -> Optional[str]:
    """팀 조직도(박스+연결선 단순 트리)를 PNG 로 저장하고 경로를 반환한다.

    각 node = {"id": str, "label": str, "parent": str|None}.
    노드가 비었거나, 루트가 정확히 1개가 아니거나, 부모 참조가 깨졌거나,
    순환/중복이 있으면 None.
    """
    if not isinstance(nodes, list) or not nodes:
        return None
    pos = _layout_tree(nodes)
    if pos is None:
        return None
    try:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        width = max(8.0, (max(xs) - min(xs) + 1) * 2.0)
        height = max(3.0, (max(ys) - min(ys) + 1) * 1.6)
        fig, ax = plt.subplots(figsize=(width, height))

        # id -> 부모 매핑 재구성(연결선용)
        parent_of: dict[str, Optional[str]] = {}
        for n in nodes:
            parent = n.get("parent")
            parent_of[str(n["id"])] = None if parent is None else str(parent)

        box_w, box_h = 0.8, 0.5
        for nid, (x, y, label) in pos.items():
            parent = parent_of.get(nid)
            if parent is not None and parent in pos:
                px, py, _ = pos[parent]
                ax.plot([x, px], [y + box_h / 2, py - box_h / 2],
                        color="#888888", linewidth=1.2, zorder=1)
        for nid, (x, y, label) in pos.items():
            box = FancyBboxPatch(
                (x - box_w / 2, y - box_h / 2), box_w, box_h,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                linewidth=1.2, edgecolor="#4C72B0", facecolor="#EAF0F9",
                zorder=2,
            )
            ax.add_patch(box)
            ax.text(x, y, label, ha="center", va="center", fontsize=10, zorder=3)

        ax.set_title(title, fontweight="bold", fontsize=14)
        ax.set_xlim(min(xs) - 1, max(xs) + 1)
        ax.set_ylim(min(ys) - 1, max(ys) + 1)
        ax.axis("off")
        return _save(fig, out_png)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"org_chart 생성 실패: {exc}", RuntimeWarning, stacklevel=2)
        return None
