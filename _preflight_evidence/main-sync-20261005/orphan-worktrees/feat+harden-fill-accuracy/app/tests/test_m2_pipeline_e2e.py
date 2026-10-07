"""M2 E2E: 라이브러리 분류·매칭·contact sheet."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from auto_write.image_automation.m2_pipeline import run_m2


def _lib(tmp: Path) -> Path:
    lib = tmp / "library"
    mapping = {
        "1.문제인식": ("market.png", (200, 80, 80)),
        "2.실현가능성": ("arch.png", (80, 200, 80)),
        "3.성장전략": ("roadmap.png", (80, 80, 200)),
        "4.기업구성": ("org.png", (200, 200, 80)),
    }
    for folder, (name, color) in mapping.items():
        p = lib / folder
        p.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (640, 480), color).save(p / name)
    return lib


def test_m2_library_classify_and_match(tmp_path: Path):
    lib = _lib(tmp_path)
    result = run_m2(
        results_root=tmp_path / "runs",
        library=lib,
        document_text_blocks=[
            "시장규모와 고객 문제",
            "핵심 기술 아키텍처와 실현가능성",
            "성장전략 로드맵",
            "팀 구성 조직도",
        ],
    )
    assert result.report["library"]["count"] == 4
    counts = result.report["classify"]["counts"]
    assert counts.get("01_problem", 0) == 1
    assert counts.get("02_solution", 0) == 1
    assert counts.get("03_scale_up", 0) == 1
    assert counts.get("04_team", 0) == 1
    assert (result.run_dir / "classify" / "classify_manifest.json").is_file()
    assert (result.run_dir / "match" / "match_report.json").is_file()
    assert (result.run_dir / "match" / "review_list.md").is_file()
    # contact sheet may exist when auto/review picked images
    match = result.report["match"]
    assert match["auto"] + match["review"] + match["skip"] >= 1
    # originals untouched
    assert (lib / "1.문제인식" / "market.png").is_file()
