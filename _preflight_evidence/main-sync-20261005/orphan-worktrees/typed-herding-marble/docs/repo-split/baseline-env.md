# Baseline Environment Inventory

> 브랜치: `refactor/repo-split-pm`
> 조사일: 2026-08-07
> 목적: Python 3.11 테스트 baseline 환경 조사 (설치 없음)

## 설치된 Python 목록

```
py -0p 결과:
 -V:3.12 *  C:\Users\ekth3\AppData\Local\Programs\Python\Python312\python.exe
```

Python 3.12만 설치되어 있습니다. Python 3.11은 **존재하지 않습니다**.

## Python 3.11 상태

| 항목 | 값 |
|------|-----|
| 존재 여부 | **없음** |
| 경로 | `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe` → False |
| py launcher 등록 | 없음 (`py -0p`에 3.11 미표시) |

## 현재 Python 명령 해석

| 명령 | 경로 | 버전 |
|------|------|------|
| `python` | `C:\Users\ekth3\AppData\Local\Programs\Python\Python312\python.exe` | 3.12.10 |
| `py` | `C:\Users\ekth3\AppData\Local\Programs\Python\Launcher\py.exe` | launcher |

## Python 3.12 패키지 상태

| 패키지 | 설치 여부 | 버전 |
|--------|----------|------|
| pytest | **설치됨** | 9.1.1 |
| python-docx | **미설치** | - |
| lxml | **미설치** | - |
| PyMuPDF (fitz) | **미설치** | - |
| openai | **미설치** | - |
| matplotlib | **미설치** | - |

## 직전 Python 3.12 테스트가 무효인 이유

1. **인터프리터 불일치**: 지시사항은 Python 3.11 기준이었으나 3.12로 실행
2. **핵심 의존성 미설치**: `python-docx`, `lxml`, `fitz`, `openai`, `matplotlib` 등 5개 패키지 미설치
3. **결과**: 100개 테스트 전부 `ModuleNotFoundError`로 collection error — 유효한 회귀 기준이 아님
4. **venv 미사용**: 시스템 Python 직접 사용. 프로젝트 의존성이 설치된 가상환경이 없음

## 다음 PM 승인 후 필요한 환경조치

1. Python 3.11 설치 (https://www.python.org/downloads/release/python-3119/ 또는 `py -3.11`로 설치)
2. 프로젝트 venv 생성: `py -3.11 -m venv .venv`
3. 핵심 패키지 설치: `pip install python-docx lxml PyMuPDF openai matplotlib pytest`
4. `requirements.txt` 또는 `pyproject.toml` 기반 설치
5. venv 활성화 후 `python -m pytest app/tests -q` 실행하여 유효 baseline 확보

> **현재 PM 승인 없이 패키지 설치 금지 상태.** 환경 조치는 PM 승인 후 수행.
