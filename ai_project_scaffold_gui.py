#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9가-힣\s_-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "new-service"


def write_file(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def build_files(service_name: str, one_line: str, target_user: str, problem: str,
                core_features: str, folder_path: str, project_folder_name: str,
                tech_stack: str) -> Path:
    base_dir = Path(folder_path).expanduser().resolve() / project_folder_name
    base_dir.mkdir(parents=True, exist_ok=True)

    feature_list = [x.strip() for x in core_features.split(",") if x.strip()]
    feature_bullets = "\n".join(f"- {x}" for x in feature_list) or "- 핵심 기능 정의 필요"

    agents = """
# AGENTS.md

## 작업 원칙
1. 항상 PRD.md를 먼저 읽고 무엇을 만드는지 이해한다.
2. 항상 TASKS.md를 기준으로 현재 작업 범위를 확인한다.
3. 한 번에 하나의 TASK만 수행한다.
4. RULES.md를 위반하는 변경은 하지 않는다.
5. 구현 후 반드시 테스트 방법과 남은 문제를 함께 정리한다.
6. PRD에 없는 기능은 멋대로 확장하지 않는다.

## 작업 순서
spec -> plan -> build -> test -> review

## 응답 형식
1. 이번에 수행한 TASK
2. 변경한 파일
3. 구현 내용
4. 테스트 방법
5. 남은 문제 또는 다음 TASK
"""

    prd = f"""
# PRD.md

## 서비스명
{service_name}

## 한 줄 설명
{one_line}

## 대상 사용자
{target_user}

## 해결 문제
{problem}

## 핵심 기능
{feature_bullets}

## MVP 범위
- 기본 입력 화면 제공
- 핵심 기능 1~2개 우선 구현
- 결과 확인이 가능한 최소 UI 제공
- 실패/예외 상황에 대한 기본 안내 제공

## 제외 범위
- 관리자 페이지
- 복잡한 권한 관리
- 외부 서비스 대규모 연동
- 고도화된 통계/대시보드

## 성공 기준
- 핵심 기능이 최소 1회 정상 실행된다.
- 사용자가 입력 → 결과 확인까지 한 화면 또는 짧은 흐름에서 완료할 수 있다.
- 테스트 케이스 3종(정상/실패/경계)이 정의된다.

## 개발환경
- {tech_stack}
"""

    tasks = """
# TASKS.md

## TASK-01
프로젝트 기본 폴더/파일 구조 생성
- 실행 파일 생성
- 기본 README 또는 안내문 추가

## TASK-02
기본 입력 화면 구현
- 서비스 제목 표시
- 사용자 입력창 추가
- 실행 버튼 추가

## TASK-03
핵심 기능 1차 구현
- 입력값을 받아 처리하는 로직 작성
- 최소 결과 출력 구현

## TASK-04
예외 처리 추가
- 빈 입력 처리
- 잘못된 입력 처리
- 실패 시 안내 문구 출력

## TASK-05
테스트 및 검토
- 정상 케이스 1개
- 실패 케이스 1개
- 경계 케이스 1개
"""

    rules = """
# RULES.md

## 구현 규칙
- 한 번에 TASK 하나만 수행한다.
- PRD 범위를 벗어나는 기능은 추가하지 않는다.
- 복잡한 구조보다 단순한 구조를 우선한다.
- 함수 하나는 역할 하나만 담당하게 한다.

## UI 규칙
- 화면은 단순하게 유지한다.
- 사용자가 바로 이해할 수 있는 문구를 사용한다.
- 버튼과 입력 요소는 최소 개수로 구성한다.

## 테스트 규칙
- 정상 입력 테스트 1개 이상
- 실패 입력 테스트 1개 이상
- 경계값 테스트 1개 이상

## 금지
- 테스트 없이 완료 선언
- PRD에 없는 기능 임의 추가
- 개인정보/민감정보 하드코딩
"""

    start_prompt = f"""
이 프로젝트에서는 반드시 아래 파일을 먼저 읽고 작업해.
- {base_dir / 'AGENTS.md'}
- {base_dir / 'PRD.md'}
- {base_dir / 'TASKS.md'}
- {base_dir / 'RULES.md'}

작업 원칙:
- AGENTS.md의 작업 원칙을 따른다.
- PRD.md 범위를 넘는 기능은 추가하지 않는다.
- TASK는 한 번에 하나만 수행한다.
- 구현 후 테스트 방법을 반드시 함께 제시한다.
- 먼저 수정 계획을 짧게 보여준 뒤 작업한다.

지금 할 일:
- TASK-01만 수행해.

결과는 아래 형식으로 정리해:
1) 수행한 TASK
2) 변경 파일
3) 구현 내용
4) 테스트 방법
5) 남은 문제
"""

    readme = f"""
# {service_name}

자동 생성된 AI 프로젝트 시작 폴더입니다.

## 포함 파일
- AGENTS.md : AI 작업 규칙
- PRD.md : 서비스 기획 요약
- TASKS.md : 작업 목록
- RULES.md : 구현/테스트 규칙
- START_PROMPT.txt : AI에 바로 붙여넣을 시작 프롬프트

## 사용 순서
1. AI 코딩 도구를 연다.
2. START_PROMPT.txt 내용을 붙여넣는다.
3. TASK-01부터 하나씩 진행한다.
"""

    write_file(base_dir / "AGENTS.md", agents)
    write_file(base_dir / "PRD.md", prd)
    write_file(base_dir / "TASKS.md", tasks)
    write_file(base_dir / "RULES.md", rules)
    write_file(base_dir / "START_PROMPT.txt", start_prompt)
    write_file(base_dir / "README.md", readme)
    return base_dir


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("AI 프로젝트 자동 생성기")
        root.geometry("760x700")

        self.entries = {}
        fields = [
            ("서비스명", "웹 핸드폰 인증번호 자동입력 서비스"),
            ("한 줄 설명", "문자에서 인증번호를 추출해 입력창에 자동 반영하는 서비스"),
            ("대상 사용자", "반복 로그인 인증이 많은 개인 사용자"),
            ("해결 문제", "인증번호 복사/붙여넣기가 번거롭다"),
            ("핵심 기능(쉼표구분)", "입력, 추출, 결과출력"),
            ("프로젝트 폴더명", "otp-helper"),
            ("개발환경", "Streamlit"),
        ]

        frame = tk.Frame(root, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        row = 0
        for label, default in fields:
            tk.Label(frame, text=label, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
            ent = tk.Entry(frame, width=70)
            ent.insert(0, default)
            ent.grid(row=row, column=1, sticky="ew", pady=4)
            self.entries[label] = ent
            row += 1

        tk.Label(frame, text="생성할 폴더 경로", anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        self.path_entry = tk.Entry(frame, width=70)
        self.path_entry.insert(0, str(Path.home() / "Desktop"))
        self.path_entry.grid(row=row, column=1, sticky="ew", pady=4)
        tk.Button(frame, text="찾아보기", command=self.choose_folder).grid(row=row, column=2, padx=6)
        row += 1

        tk.Button(frame, text="자동 생성", command=self.generate, height=2).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1

        tk.Label(frame, text="결과", anchor="w").grid(row=row, column=0, sticky="w")
        row += 1
        self.output = scrolledtext.ScrolledText(frame, height=16)
        self.output.grid(row=row, column=0, columnspan=3, sticky="nsew")

        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(row, weight=1)

    def choose_folder(self):
        selected = filedialog.askdirectory()
        if selected:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, selected)

    def generate(self):
        service_name = self.entries["서비스명"].get().strip()
        one_line = self.entries["한 줄 설명"].get().strip()
        target_user = self.entries["대상 사용자"].get().strip()
        problem = self.entries["해결 문제"].get().strip()
        core_features = self.entries["핵심 기능(쉼표구분)"].get().strip()
        project_folder_name = self.entries["프로젝트 폴더명"].get().strip() or slugify(service_name)
        tech_stack = self.entries["개발환경"].get().strip() or "Streamlit"
        folder_path = self.path_entry.get().strip()

        if not service_name or not folder_path:
            messagebox.showerror("오류", "서비스명과 폴더 경로는 필수입니다.")
            return

        try:
            base_dir = build_files(
                service_name=service_name,
                one_line=one_line,
                target_user=target_user,
                problem=problem,
                core_features=core_features,
                folder_path=folder_path,
                project_folder_name=project_folder_name,
                tech_stack=tech_stack,
            )
            result = (
                f"생성 완료\n\n"
                f"폴더: {base_dir}\n\n"
                f"생성 파일:\n"
                f"- AGENTS.md\n- PRD.md\n- TASKS.md\n- RULES.md\n- START_PROMPT.txt\n- README.md\n\n"
                f"다음 단계:\n"
                f"1. START_PROMPT.txt 열기\n"
                f"2. 내용 전체 복사\n"
                f"3. Claude/Codex/Cursor에 붙여넣기\n"
            )
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, result)
            messagebox.showinfo("완료", f"프로젝트 문서 생성 완료\n{base_dir}")
        except Exception as e:
            messagebox.showerror("오류", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
