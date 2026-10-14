"""F5 첨부서류 개인정보 가림: PDF 의 주민등록번호 뒷자리 7자리를 검은 박스로 가린다.

방식: PyMuPDF 로 각 페이지를 dpi 해상도 이미지로 렌더 -> 탐지된 뒷자리 bbox 위에
검은 사각형 -> 이미지들로 새 PDF 재생성. 원본 텍스트 레이어는 결과에 남지 않는다.

스캔본(텍스트 레이어 없는 이미지 페이지): Windows 내장 OCR(Windows.Media.Ocr, 'ko')을
powershell.exe 로 호출해 단어 bbox 를 얻고, 주민번호 뒷자리 영역만 검게 칠한다(새 의존성 없음).
OCR 불가·판독 부족·앞 6자리만 보이는 등 불확실하면 가리지 못한 것으로 보고하고
undetected_pages 와 REVIEW Finding 으로 남긴다(사용자 확인·수동 가림 필요).
원본은 수정하지 않고 사본만 새로 만든다. 보고 문구에는 금지 표현·개인정보 원문을 넣지 않는다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

from .status import Finding, Status

# 앞 6자리(생년월일) + 선택적 하이픈 + 뒤 7자리(성별 1~4 로 시작).
_RRN_RE = re.compile(r"(?<!\d)(\d{6})[-‐-―−]?([1-4]\d{6})(?!\d)")
_TAIL_LEN = 7
_PAD_PT = 0.8  # 박스 여백(pt). 앞 6자리·하이픈과의 간격보다 작게 유지한다.
_OCR_MIN_WORDS = 3  # 이보다 적게 읽히면 판독 실패로 보고 REVIEW
_OCR_PAD_FRAC = 0.25  # OCR 박스 좌우 여백(숫자 1자 폭 대비 비율)
_OCR_PAD_Y = 3  # OCR 박스 상하 여백(px)
_OCR_TIMEOUT = 120
_DASHES = "-‐‑‒–—―−"
_HYPHEN_W = 0.5  # 글자 폭 가중치: 숫자 1.0, 하이픈류 0.5
# 앞 6자리(생년월일 YYMMDD) 후보: 월 01~12, 일 01~31.
_FRONT_RE = re.compile(r"(?<!\d)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)")
# 날짜 문맥: 앞에 '숫자+구분자'(예: 19.05.) 또는 뒤에 '구분자+1~2자리+구분자'(예: -05-15) 가 오면 주민번호 앞자리가 아니다.
_DATE_BEFORE_RE = re.compile(r"\d{1,4}[-./]$")
_DATE_AFTER_RE = re.compile(r"[-./]\d{1,2}[-./]")
# 이미 가려진 표기: 하이픈 + (성별 숫자) + 가림 문자 3개 이상.
_MASKED_AFTER_RE = re.compile(r"^[-‐‑‒–—―−]?[1-4]?[*＊●○◯■□Xx•·∙]{3,}")
_BOX_DARK_LUMA = 80      # 이 밝기 미만이면 어두운 화소
_BOX_DARK_FRAC = 0.6     # 확인 영역 중 어두운 화소 비율이 이 이상이면 검은 박스로 가려진 것으로 본다


@dataclass
class RedactResult:
    findings: list[Finding] = field(default_factory=list)
    redacted_boxes: int = 0
    pages: int = 0
    undetected_pages: list[int] = field(default_factory=list)  # 0 기반 페이지 번호

    @property
    def status(self) -> Status:
        """전체 요약 상태: FAIL > REVIEW > PASS(가림 수행) > N/A(대상 없음)."""
        sts = {f.status for f in self.findings}
        if Status.FAIL in sts:
            return Status.FAIL
        if Status.REVIEW in sts or self.undetected_pages:
            return Status.REVIEW
        if self.redacted_boxes:
            return Status.PASS
        return Status.NA


def _page_chars(page: "fitz.Page") -> list[tuple[str, "fitz.Rect"]]:
    """페이지의 공백 제외 문자와 bbox 를 읽기 순서대로 돌려준다."""
    out: list[tuple[str, fitz.Rect]] = []
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch.get("c", "")
                    if c and not c.isspace():
                        out.append((c, fitz.Rect(ch["bbox"])))
    return out


def _find_tail_rects(page: "fitz.Page") -> list["fitz.Rect"]:
    """주민번호 뒷자리 7자리가 놓인 영역(줄 단위로 합친 사각형)들."""
    chars = _page_chars(page)
    joined = "".join(c for c, _ in chars)
    rects: list[fitz.Rect] = []
    for m in _RRN_RE.finditer(joined):
        tail = chars[m.start(2):m.start(2) + _TAIL_LEN]
        # 같은 줄(세로 중심이 가까운 것)끼리 묶어 줄별 박스를 만든다.
        cur: fitz.Rect | None = None
        for _, r in tail:
            if cur is not None and abs((r.y0 + r.y1) / 2 - (cur.y0 + cur.y1) / 2) <= cur.height * 0.5:
                cur |= r
            else:
                if cur is not None:
                    rects.append(cur)
                cur = fitz.Rect(r)
        if cur is not None:
            rects.append(cur)
    return rects


def _has_visual_content(page: "fitz.Page") -> bool:
    return bool(page.get_images(full=True)) or bool(page.get_drawings())


@dataclass
class OcrWord:
    """OCR 이 읽은 단어 하나. 좌표는 렌더 이미지 픽셀 기준. line 은 줄 번호."""
    text: str
    x: float
    y: float
    w: float
    h: float
    line: int = 0


OcrFn = Callable[[bytes, int], "list[OcrWord] | None"]  # None 반환 = OCR 사용 불가

_OCR_PS1 = r"""param([string]$Png, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await($op, $type) {
    $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $null = $t.Wait(-1)
    $t.Result
}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Png)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language('ko')))
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { throw 'no-ocr-engine' }
$res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
$words = New-Object System.Collections.ArrayList
$li = 0
foreach ($line in $res.Lines) {
    foreach ($w in $line.Words) {
        $r = $w.BoundingRect
        [void]$words.Add(@{ t = $w.Text; x = $r.X; y = $r.Y; w = $r.Width; h = $r.Height; l = $li })
    }
    $li++
}
$json = ConvertTo-Json -InputObject @($words) -Compress -Depth 4
[System.IO.File]::WriteAllText($Out, $json, (New-Object System.Text.UTF8Encoding($false)))
"""


def windows_ocr(png: bytes, dpi: int = 250) -> "list[OcrWord] | None":
    """Windows 내장 OCR(ko)로 PNG 의 단어와 bbox 를 읽는다. 사용 불가·실패면 None."""
    if sys.platform != "win32":
        return None
    with tempfile.TemporaryDirectory(prefix="pii_ocr_") as td:
        tdp = Path(td)
        png_p, out_p, ps_p = tdp / "page.png", tdp / "out.json", tdp / "ocr.ps1"
        png_p.write_bytes(png)
        ps_p.write_text(_OCR_PS1, encoding="utf-8-sig")  # PS 5.1 은 BOM 이 있어야 UTF-8 로 읽음
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(ps_p), str(png_p), str(out_p)],
                capture_output=True, timeout=_OCR_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0 or not out_p.is_file():
            return None
        try:
            raw = json.loads(out_p.read_text(encoding="utf-8-sig") or "[]")
        except ValueError:
            return None
    if isinstance(raw, dict):  # 단어 1개면 배열이 풀릴 수 있음
        raw = [raw]
    return [OcrWord(str(d.get("t", "")), float(d["x"]), float(d["y"]), float(d["w"]),
                    float(d["h"]), int(d.get("l", 0))) for d in raw]


def _char_weight(c: str) -> float:
    return _HYPHEN_W if c in _DASHES else 1.0


def _ocr_scan(words: list[OcrWord]):
    """OCR 단어에서 (뒷자리 박스 [(x0,y0,x1,y1)...], 앞6자리만 보이고 뒷자리 미확정 여부)."""
    chars: list[tuple[str, int, int]] = []  # (문자, 단어 idx, 단어 내 offset)
    prev_line = None
    for wi, wd in enumerate(words):
        if prev_line is not None and wd.line != prev_line:
            chars.append(("\n", -1, 0))
        prev_line = wd.line
        for ci, c in enumerate(wd.text):
            if not c.isspace():
                chars.append((c, wi, ci))
    # 흔한 OCR 오인식(O->0, l/I/|->1)은 숫자 판독 보조로만 정규화한다(과가림 방향).
    trans = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1"})
    joined = "".join(c.translate(trans) for c, _, _ in chars)
    dash_cls = re.escape(_DASHES)
    rrn = re.compile(rf"(?<!\d)(\d{{6}})[{dash_cls}]?([1-4]\d{{6}})(?!\d)")
    boxes: list[tuple[float, float, float, float]] = []
    covered: list[tuple[int, int]] = []
    for m in rrn.finditer(joined):
        covered.append((m.start(1), m.end(2)))
        per_word: dict[int, list[int]] = {}
        for idx in range(m.start(2), m.end(2)):
            _, wi, ci = chars[idx]
            per_word.setdefault(wi, []).append(ci)
        for wi, offs in per_word.items():
            wd = words[wi]
            ws = [_char_weight(c) for c in wd.text]
            total = sum(ws) or 1.0
            lo, hi = min(offs), max(offs)
            x0 = wd.x + wd.w * sum(ws[:lo]) / total
            x1 = wd.x + wd.w * sum(ws[:hi + 1]) / total
            pad = (wd.w / total) * _OCR_PAD_FRAC  # 숫자 1자 폭 기준 여백
            boxes.append((x0 - pad, wd.y - _OCR_PAD_Y, x1 + pad, wd.y + wd.h + _OCR_PAD_Y))
    # 앞 6자리만 보이고 뒷자리가 확정되지 않은 후보. 날짜(…-05-15)·이미 가려진 표기(920101-*******)는 제외한다.
    front_boxes: list[tuple[float, float, float, float]] = []
    for fm in _FRONT_RE.finditer(joined):
        if any(a <= fm.start() < b for a, b in covered):
            continue
        before = joined[max(0, fm.start() - 6):fm.start()]
        after = joined[fm.end():fm.end() + 12]
        if _DATE_BEFORE_RE.search(before) or _DATE_AFTER_RE.match(after) or _MASKED_AFTER_RE.match(after):
            continue
        wi = chars[fm.end() - 1][1]
        if wi >= 0:
            wd = words[wi]
            front_boxes.append((wd.x, wd.y, wd.x + wd.w, wd.y + wd.h))
    return boxes, front_boxes


def _black_box_right_of(pix: "fitz.Pixmap", box: tuple[float, float, float, float]) -> bool:
    """앞자리 단어 오른쪽(글자 높이의 7배 폭)이 어두운 박스인지 격자 표본으로 확인한다."""
    x0, y0, x1, y1 = box
    height = max(y1 - y0, 1.0)
    left, right = int(x1 + 0.3 * height), int(x1 + 7 * height)
    top, bottom = int(y0 + 0.2 * height), int(y1 - 0.2 * height)
    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, pix.width - 1), min(bottom, pix.height - 1)
    if right <= left or bottom <= top:
        return False
    dark = total = 0
    for yy in range(top, bottom + 1, max((bottom - top) // 4, 1)):
        for xx in range(left, right + 1, max((right - left) // 12, 1)):
            r, g, b = pix.pixel(xx, yy)[:3]
            total += 1
            if (0.299 * r + 0.587 * g + 0.114 * b) < _BOX_DARK_LUMA:
                dark += 1
    return total > 0 and dark / total >= _BOX_DARK_FRAC


def redact_pdf(src, dst, *, dpi: int = 250, overwrite: bool = False,
               use_ocr: bool = True, ocr_fn: OcrFn | None = None) -> RedactResult:
    """src PDF 의 주민번호 뒷자리를 가린 사본을 dst 에 만든다(원본 불변).

    텍스트 레이어 없는 이미지 페이지는 OCR 로 찾는다. ocr_fn(png_bytes, dpi) -> list[OcrWord]
    (None 반환 = OCR 사용 불가)를 주입하면 그것을, 없으면 Windows 내장 OCR 을 쓴다.
    use_ocr=False 면 OCR 을 시도하지 않고 스캔 페이지를 REVIEW 로 보고한다.
    """
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.is_file():
        raise FileNotFoundError(f"입력 PDF 없음: {src_p.name}")
    if src_p.resolve() == dst_p.resolve():
        raise ValueError("출력 경로가 입력 경로와 같다(원본 덮어쓰기 금지)")
    if dst_p.exists() and not overwrite:
        raise ValueError(f"출력 파일이 이미 있다(overwrite=False): {dst_p.name}")
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    result = RedactResult()
    scale = dpi / 72.0
    out = fitz.open()
    try:
        with fitz.open(str(src_p)) as doc:
            result.pages = doc.page_count
            for pno, page in enumerate(doc):
                rects = _find_tail_rects(page)
                has_text = bool(page.get_text("text").strip())
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                if rects:
                    for r in rects:
                        rr = fitz.Rect(r.x0 - _PAD_PT, r.y0 - _PAD_PT, r.x1 + _PAD_PT, r.y1 + _PAD_PT)
                        rr = rr * page.rotation_matrix * fitz.Matrix(scale, scale)
                        irect = fitz.IRect(int(rr.x0), int(rr.y0), int(rr.x1) + 1, int(rr.y1) + 1)
                        irect &= pix.irect
                        if not irect.is_empty:
                            pix.set_rect(irect, (0, 0, 0))
                            result.redacted_boxes += 1
                    result.findings.append(Finding(
                        code="PII-REDACT", status=Status.PASS,
                        message=f"주민번호 뒷자리 {len(rects)}곳을 검은 박스로 가림", source="engine",
                        page=pno + 1, evidence="텍스트 레이어 문자 단위 bbox 기준"))
                elif not has_text and _has_visual_content(page):
                    words = None
                    if use_ocr:
                        try:
                            words = (ocr_fn or windows_ocr)(pix.tobytes("png"), dpi)
                        except Exception:  # noqa: BLE001 - OCR 실패는 REVIEW 로 정직하게 보고
                            words = None
                    if words is None:
                        result.undetected_pages.append(pno)
                        result.findings.append(Finding(
                            code="PII-UNDETECTED", status=Status.REVIEW,
                            message="텍스트 레이어가 없고 OCR 도 쓸 수 없어 주민번호 위치를 찾지 못함 - 이 페이지는 가리지 못했으므로 사용자 확인 필요",
                            source="engine", page=pno + 1,
                            evidence="OCR 미사용(use_ocr=False)" if not use_ocr
                            else "OCR 사용 불가 또는 실패(Windows OCR 'ko' 엔진/powershell.exe 확인)"))
                    elif len(words) < _OCR_MIN_WORDS:
                        result.undetected_pages.append(pno)
                        result.findings.append(Finding(
                            code="PII-UNDETECTED", status=Status.REVIEW,
                            message="스캔 페이지에서 OCR 이 글자를 거의 읽지 못함 - 이 페이지는 가리지 못했을 수 있어 사용자 확인 필요",
                            source="engine", page=pno + 1,
                            evidence=f"OCR 판독 단어 {len(words)}개(<{_OCR_MIN_WORDS})"))
                    else:
                        boxes, front_boxes = _ocr_scan(words)
                        # 앞 6자리 바로 오른쪽이 이미 검은 박스로 가려져 있으면 확인된 것으로 본다(스캔 시 가림 처리된 서류).
                        front_boxes = [fb for fb in front_boxes if not _black_box_right_of(pix, fb)]
                        front_only = bool(front_boxes)
                        n_ok = 0
                        for x0, y0, x1, y1 in boxes:
                            irect = fitz.IRect(int(x0), int(y0), int(x1) + 1, int(y1) + 1)
                            irect &= pix.irect
                            if not irect.is_empty:
                                pix.set_rect(irect, (0, 0, 0))
                                result.redacted_boxes += 1
                                n_ok += 1
                        if front_only:
                            result.undetected_pages.append(pno)
                            result.findings.append(Finding(
                                code="PII-UNDETECTED", status=Status.REVIEW,
                                message="스캔 페이지에서 주민번호 앞 6자리 후보는 보이나 뒷자리 패턴이 확정되지 않음 - 사용자 확인 필요"
                                        + (f" (확정된 {n_ok}곳은 가림)" if n_ok else ""),
                                source="engine", page=pno + 1, evidence="스캔본 OCR 기반 탐지(불확실)"))
                        elif n_ok:
                            result.findings.append(Finding(
                                code="PII-REDACT", status=Status.PASS,
                                message=f"주민번호 뒷자리 {n_ok}곳을 검은 박스로 가림", source="engine",
                                page=pno + 1, evidence="스캔본 OCR 기반 탐지(단어 bbox, 오인식 가능)"))
                        else:
                            result.findings.append(Finding(
                                code="PII-NONE", status=Status.NA,
                                message="스캔 페이지 OCR 결과에서 주민번호 형태가 발견되지 않음",
                                source="engine", page=pno + 1,
                                evidence=f"스캔본 OCR 기반 탐지(판독 단어 {len(words)}개)"))
                op = out.new_page(width=page.rect.width, height=page.rect.height)
                op.insert_image(op.rect, stream=pix.tobytes("png"))
        out.save(str(dst_p), deflate=True)
    finally:
        out.close()

    if result.redacted_boxes == 0 and not result.undetected_pages:
        result.findings.append(Finding(
            code="PII-NONE", status=Status.NA,
            message="주민번호 형태가 발견되지 않아 가림 박스 0개", source="engine"))
    result.findings.extend(verify_redacted(dst_p))
    return result


def verify_redacted(pdf_path, rrn_tails: list[str] | None = None) -> list[Finding]:
    """결과 PDF 텍스트 레이어에 주민번호 뒷자리가 남았는지 검사한다(남으면 FAIL).

    rrn_tails 를 주면 그 값(숫자 7자리)도 직접 찾는다. 이미지 안의 글자는 검사 대상이 아니다.
    """
    findings: list[Finding] = []
    leaks: dict[int, int] = {}
    with fitz.open(str(pdf_path)) as doc:
        for pno, page in enumerate(doc):
            text = "".join(c for c, _ in _page_chars(page))
            n = len(_RRN_RE.findall(text))
            digits = re.sub(r"\D", "", text)
            for t in rrn_tails or []:
                d = re.sub(r"\D", "", t)
                if d and d in digits:
                    n += 1
            if n:
                leaks[pno + 1] = n
    for pg, n in leaks.items():
        findings.append(Finding(
            code="PII-LEAK", status=Status.FAIL,
            message=f"텍스트 레이어에 주민번호 뒷자리 형태가 {n}곳 남아 있음 (구조 검사 FAIL)",
            source="structural", page=pg))
    if not leaks:
        findings.append(Finding(
            code="PII-VERIFY", status=Status.PASS,
            message="텍스트 레이어 기준 자동 검사에서 추가 이상 미발견(이미지 안 글자는 검사 대상 아님)",
            source="structural"))
    return findings
