"""
sync_dev_status.py — auto_write 개발 현황 및 TODO 구글 시트 자동 동기화 스크립트.

기능:
1. Git 수집: 현재 브랜치, 최근 커밋, 워크트리 목록, 열린 PR(gh CLI) 상태.
2. RESUME.md 파싱: 백로그(B01~B10) 및 마일스톤(M1~M4) 진행 상황.
3. 코드 주석 수집: codebase 내 # TODO, # FIXME 스캔.
4. 구글 시트 동기화: '[자동] 개발 현황' 및 '[자동] TODO 백로그' 탭에 갱신.

사용법:
  # 콘솔 미리보기 (구글 시트 수정 없음)
  python scripts/sync_dev_status.py --dry-run

  # 구글 시트 실시간 자동 업그레이드/동기화
  python scripts/sync_dev_status.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Google Sheets API imports
try:
    import gspread
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    HAS_GOOGLE_LIBS = True
except ImportError:
    HAS_GOOGLE_LIBS = False


DEFAULT_SPREADSHEET_ID = "1cH5W1kGgO1AAK-moUrhou6rUc2oP_PDBjAAFRsojiWg"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_SECRET_PATHS = [
    BASE_DIR / "client_secret.json",
    Path("D:/google-tasks-mcp/client_secret.json"),
]
TOKEN_PATH = Path("D:/google-tasks-mcp/token_sheets.json")


def run_command(cmd, cwd=None):
    """안전한 셸 명령 실행 유틸리티."""
    try:
        res = subprocess.run(
            cmd,
            cwd=cwd or BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


def collect_git_info():
    """Git 정보 (브랜치, 커밋, 워크트리, PR, status) 수집."""
    info = {}

    # 현재 브랜치 및 최근 커밋
    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit_hash = run_command(["git", "log", "-1", "--format=%h"])
    commit_msg = run_command(["git", "log", "-1", "--format=%s"])
    commit_date = run_command(["git", "log", "-1", "--format=%cd", "--date=iso-short"])

    info["current_branch"] = branch
    info["last_commit"] = f"[{commit_hash}] {commit_msg} ({commit_date})"

    # 미커밋 변경사항 개수
    status_lines = run_command(["git", "status", "--short"]).splitlines()
    info["uncommitted_count"] = len(status_lines)

    # Git Worktrees
    wt_raw = run_command(["git", "worktree", "list"]).splitlines()
    worktrees = []
    for line in wt_raw:
        if line.strip():
            parts = line.split(maxsplit=2)
            wt_path = parts[0]
            wt_commit = parts[1] if len(parts) > 1 else ""
            wt_branch = parts[2] if len(parts) > 2 else ""
            worktrees.append({
                "path": os.path.basename(wt_path),
                "commit": wt_commit,
                "branch": wt_branch.strip("[]"),
            })
    info["worktrees"] = worktrees

    # 열린 PR (gh CLI)
    pr_raw = run_command(["gh", "pr", "list", "--json", "number,title,state,headRefName,url,updatedAt"])
    prs = []
    if pr_raw and not pr_raw.startswith("Error"):
        try:
            prs = json.loads(pr_raw)
        except Exception:
            pass
    info["pull_requests"] = prs

    return info


def collect_resume_backlog():
    """RESUME.md에서 백로그(B01~B10) 및 마일스톤 현황 추출."""
    resume_path = BASE_DIR / "RESUME.md"
    if not resume_path.exists():
        return []

    content = resume_path.read_text(encoding="utf-8", errors="ignore")
    items = []

    # B01~B10 항목 파싱
    audit_file = BASE_DIR / ".omc" / "plans" / "google-sheet-backlog-audit-20260723.md"
    if audit_file.exists():
        audit_text = audit_file.read_text(encoding="utf-8", errors="ignore")
        for line in audit_text.splitlines():
            # 예: | B01 | 부분 충족 | 경로형... | mktemp... |
            m = re.match(r"^\|\s*(B\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", line)
            if m:
                item_id, status_raw, desc, gap = m.groups()
                items.append({
                    "id": item_id.strip(),
                    "category": "백로그 항목",
                    "status": status_raw.strip(),
                    "description": desc.strip(),
                    "detail": gap.strip(),
                    "source": "google-sheet-backlog-audit",
                })

    # 마일스톤 파싱 (M1~M4)
    milestone_matches = re.findall(r"M[1-4]", content)
    for m_id in sorted(set(milestone_matches)):
        # 간단 현황 매핑
        items.append({
            "id": m_id,
            "category": "마일스톤",
            "status": "진행/완료" if m_id in ["M1", "M2"] else "대기/작업중",
            "description": f"이미지 자동화 마일스톤 {m_id}",
            "detail": "RESUME.md 참조",
            "source": "RESUME.md",
        })

    return items


def collect_code_todos():
    """코드베이스 내 # TODO 및 # FIXME 주석 수집."""
    todos = []
    target_dirs = [BASE_DIR / "app", BASE_DIR / "scripts"]

    for t_dir in target_dirs:
        if not t_dir.exists():
            continue
        for py_file in t_dir.rglob("*.py"):
            if py_file.name == "sync_dev_status.py":
                continue
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                for idx, line in enumerate(lines, 1):
                    m = re.search(r"#\s*(TODO|FIXME)\b(.*)", line, re.IGNORECASE)
                    if m:
                        tag, msg = m.groups()
                        rel_path = py_file.relative_to(BASE_DIR)
                        todos.append({
                            "file": str(rel_path),
                            "line": idx,
                            "type": tag.upper(),
                            "content": msg.strip(),
                        })
            except Exception:
                pass

    return todos


def get_google_credentials():
    """OAuth 인증 토큰을 가져오거나 새로 발급합니다."""
    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            print(f"⚠️ 기존 토큰 읽기 실패 ({e}), 재인증 진행합니다.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️ 토큰 갱신 실패 ({e}), 새 로그인 진행합니다.")
                creds = None

        if not creds:
            secret_file = None
            for p in CLIENT_SECRET_PATHS:
                if p.exists():
                    secret_file = p
                    break

            if not secret_file:
                raise FileNotFoundError(
                    f"Google OAuth client_secret.json을 찾을 수 없습니다. (검색 경로: {CLIENT_SECRET_PATHS})"
                )

            print(f"🔑 OAuth 브라우저 인증 시작... ({secret_file})")
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")

            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            print(f"✅ 인증 완료! 토큰 저장됨: {TOKEN_PATH}")

    return creds


def sync_to_google_sheet(spreadsheet_id, git_info, resume_items, code_todos):
    """구글 시트에 수집 데이터를 업로드/동기화합니다."""
    if not HAS_GOOGLE_LIBS:
        print("❌ gspread / google-auth 라이브러리가 설치되어 있지 않습니다.")
        return False

    print("📡 구글 시트 API 연결 중...")
    creds = get_google_credentials()
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(spreadsheet_id)
    print(f"📄 대상 시트 열기 성공: '{sh.title}'")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -------------------------------------------------------------
    # 탭 1: [자동] 개발 현황 (Dev Status)
    # -------------------------------------------------------------
    sheet1_title = "[자동] 개발 현황"
    try:
        ws1 = sh.worksheet(sheet1_title)
    except gspread.WorksheetNotFound:
        ws1 = sh.add_worksheet(title=sheet1_title, rows=100, cols=10)
        print(f"✨ 탭 생성됨: '{sheet1_title}'")

    ws1.clear()

    rows1 = [
        ["구분", "항목 / 값", "비고 / 상태", "최종 업데이트"],
        ["현재 브랜치", git_info.get("current_branch", "-"), "", now_str],
        ["최근 커밋", git_info.get("last_commit", "-"), "", now_str],
        ["미커밋 변경 파일 수", f"{git_info.get('uncommitted_count', 0)} 개", "", now_str],
        ["활성 Worktree 수", f"{len(git_info.get('worktrees', []))} 개", "", now_str],
    ]

    # Worktrees 내역 추가
    for wt in git_info.get("worktrees", []):
        rows1.append(["Worktree", wt["path"], f"Branch: {wt['branch']} ({wt['commit']})", now_str])

    # PR 목록 추가
    prs = git_info.get("pull_requests", [])
    rows1.append(["열린 PR 수", f"{len(prs)} 개", "", now_str])
    for pr in prs:
        pr_str = f"#{pr.get('number')} {pr.get('title')}"
        rows1.append(["Open PR", pr_str, f"State: {pr.get('state')} | URL: {pr.get('url')}", now_str])

    ws1.update(range_name="A1", values=rows1)
    print(f"✅ '{sheet1_title}' 탭 업데이트 완료 ({len(rows1)} 행)")

    # -------------------------------------------------------------
    # 탭 2: [자동] TODO 백로그 (TODO List)
    # -------------------------------------------------------------
    sheet2_title = "[자동] TODO 백로그"
    try:
        ws2 = sh.worksheet(sheet2_title)
    except gspread.WorksheetNotFound:
        ws2 = sh.add_worksheet(title=sheet2_title, rows=100, cols=10)
        print(f"✨ 탭 생성됨: '{sheet2_title}'")

    ws2.clear()

    rows2 = [
        ["ID / 코드", "카테고리 / 파일", "상태 / 위치", "설명 / 내용", "세부 격차 / 비고", "출처", "업데이트 일시"],
    ]

    # RESUME & Audit 백로그 항목 추가
    for item in resume_items:
        rows2.append([
            item["id"],
            item["category"],
            item["status"],
            item["description"],
            item["detail"],
            item["source"],
            now_str,
        ])

    # 코드 주석 TODO/FIXME 추가
    for td in code_todos:
        rows2.append([
            f"{td['type']}",
            td["file"],
            f"L{td['line']}",
            td["content"],
            "-",
            "Code Comment",
            now_str,
        ])

    if len(rows2) == 1:
        rows2.append(["-", "등록된 TODO 없음", "Clean", "코드 내 TODO/FIXME 없음", "-", "-", now_str])

    ws2.update(range_name="A1", values=rows2)
    print(f"✅ '{sheet2_title}' 탭 업데이트 완료 ({len(rows2)} 행)")

    return True


def main():
    parser = argparse.ArgumentParser(description="auto_write 개발 현황 및 TODO 구글 시트 자동 동기화")
    parser.add_argument("--sheet-id", default=DEFAULT_SPREADSHEET_ID, help="Google Spreadsheet ID")
    parser.add_argument("--dry-run", action="store_true", help="구글 시트 업로드 없이 콘솔 미리보기")
    args = parser.parse_args()

    print("🔍 개발 현황 및 TODO 데이터 수집 시작...")
    git_info = collect_git_info()
    resume_items = collect_resume_backlog()
    code_todos = collect_code_todos()

    if args.dry_run:
        print("\n================ [DRY-RUN 모드 : 수집 데이터 요약] ================")
        print(f"📌 현재 브랜치: {git_info['current_branch']}")
        print(f"📌 최근 커밋: {git_info['last_commit']}")
        print(f"📌 미커밋 변경 파일: {git_info['uncommitted_count']}개")
        print(f"📌 활성 Worktrees ({len(git_info['worktrees'])}개):")
        for wt in git_info['worktrees']:
            print(f"   - {wt['path']} [{wt['branch']}]")
        print(f"📌 열린 PR ({len(git_info['pull_requests'])}개):")
        for pr in git_info['pull_requests']:
            print(f"   - #{pr.get('number')} {pr.get('title')}")

        print(f"\n📋 RESUME & Audit 백로그 항목 ({len(resume_items)}개):")
        for item in resume_items[:5]:
            print(f"   - [{item['id']}] {item['category']} | {item['status']} | {item['description']}")

        print(f"\n📝 코드 내 TODO/FIXME 주석 ({len(code_todos)}개):")
        if not code_todos:
            print("   - (발견된 TODO/FIXME 주석 없음)")
        for td in code_todos[:5]:
            print(f"   - [{td['type']}] {td['file']}:L{td['line']} {td['content']}")

        print("===================================================================\n")
        print("💡 Dry-run 완료. 구글 시트를 실제 업데이트하려면 '--dry-run' 없이 실행하세요.")
        return

    try:
        success = sync_to_google_sheet(args.sheet_id, git_info, resume_items, code_todos)
        if success:
            print(f"\n🎉 성공적으로 구글 시트에 업데이트되었습니다!")
            print(f"🔗 링크: https://docs.google.com/spreadsheets/d/{args.sheet_id}/edit")
    except Exception as e:
        print(f"\n❌ 구글 시트 동기화 중 오류가 발생했습니다: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
