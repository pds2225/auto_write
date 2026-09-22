"""Public-console gate.

Local 127.0.0.1 stays open. Render and any other non-loopback bind stay
closed until AUTO_WRITE_ACCESS_PASSWORD is set. Git and L-rule writes stay
off on Render unless AUTO_WRITE_ALLOW_GIT_WRITE=1.
"""

from __future__ import annotations

import hmac
import os
from hashlib import sha256
from html import escape
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE_NAME = "aw_access"
_TOKEN_PREFIX = b"auto-write-access-v1"


def access_password() -> str:
    return os.getenv("AUTO_WRITE_ACCESS_PASSWORD", "").strip()


def on_render() -> bool:
    return os.getenv("RENDER", "").strip().lower() == "true"


def public_bind() -> bool:
    if on_render():
        return True
    host = os.getenv("AUTO_WRITE_HOST", "127.0.0.1").strip().lower()
    return host not in {"", "127.0.0.1", "localhost", "::1"}


def git_writes_allowed() -> bool:
    if on_render() and os.getenv("AUTO_WRITE_ALLOW_GIT_WRITE", "").strip() != "1":
        return False
    return True


def _token(password: str) -> str:
    return hmac.new(password.encode("utf-8"), _TOKEN_PREFIX, sha256).hexdigest()


def cookie_valid(request: Request) -> bool:
    password = access_password()
    if not password:
        return False
    presented = request.cookies.get(COOKIE_NAME, "")
    expected = _token(password)
    if len(presented) != len(expected):
        return False
    return hmac.compare_digest(presented, expected)


def safe_next(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\") or "\\" in value:
        return "/console"
    return value


def _secure_cookie(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "")
    proto = forwarded.split(",")[0].strip().lower()
    return proto == "https" or request.url.scheme == "https"


def _login_page(error: str = "", next_path: str = "/console") -> str:
    message = f"<p class='error'>{error}</p>" if error else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Auto Write 로그인</title>
  <style>
    body {{ margin: 0; font-family: "Malgun Gothic", "Segoe UI", sans-serif; background: #f4f7fb; color: #142033; }}
    main {{ max-width: 420px; margin: 12vh auto; padding: 24px; background: #fff; border: 1px solid #dbe3ee; border-radius: 16px; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    p {{ color: #67758a; font-size: 14px; }}
    label {{ display: grid; gap: 6px; font-size: 13px; font-weight: 700; }}
    input {{ font-size: 16px; min-height: 44px; padding: 8px 10px; border: 1px solid #c5d1df; border-radius: 9px; }}
    button {{ margin-top: 14px; width: 100%; min-height: 44px; border: 0; border-radius: 9px; background: #2563eb; color: #fff; font-weight: 800; font-size: 15px; }}
    .error {{ color: #8d1d17; }}
  </style>
</head>
<body>
  <main>
    <h1>Auto Write</h1>
    <p>이 콘솔은 문서와 L규칙을 바꿀 수 있습니다. 비밀번호를 입력하세요.</p>
    {message}
    <form method="post" action="/login">
      <input type="hidden" name="next" value="{escape(next_path, quote=True)}">
      <label>비밀번호
        <input type="password" name="password" autocomplete="current-password" required>
      </label>
      <button type="submit">들어가기</button>
    </form>
  </main>
</body>
</html>"""


_LOCKED_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Auto Write 잠금</title>
</head>
<body>
  <h1>콘솔이 잠겨 있습니다</h1>
  <p>Render 환경변수 <code>AUTO_WRITE_ACCESS_PASSWORD</code>를 설정한 뒤 다시 배포하세요.</p>
</body>
</html>"""


def install_access_gate(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_gate(request: Request, call_next):
        path = request.url.path
        if path == "/health" or path == "/login" or path == "/logout" or path.startswith("/static"):
            return await call_next(request)
        if not access_password():
            if public_bind():
                return HTMLResponse(_LOCKED_HTML, status_code=503)
            return await call_next(request)
        if cookie_valid(request):
            return await call_next(request)
        target = safe_next(path if not request.url.query else f"{path}?{request.url.query}")
        return RedirectResponse(url=f"/login?next={quote(target, safe='')}", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request):
        if access_password() and cookie_valid(request):
            return RedirectResponse(url=safe_next(request.query_params.get("next")), status_code=303)
        if not access_password() and public_bind():
            return HTMLResponse(_LOCKED_HTML, status_code=503)
        return HTMLResponse(_login_page(next_path=safe_next(request.query_params.get("next"))))

    @app.post("/login")
    async def login_submit(request: Request, password: str = Form(default=""), next: str = Form(default="/console")):
        expected = access_password()
        provided = password.strip()
        destination = safe_next(next)
        if not expected or len(provided) != len(expected) or not hmac.compare_digest(provided, expected):
            return HTMLResponse(_login_page("비밀번호가 맞지 않습니다.", destination), status_code=401)
        response = RedirectResponse(url=destination, status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            _token(expected),
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            max_age=60 * 60 * 24 * 14,
            path="/",
        )
        return response

    @app.get("/logout")
    async def logout():
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response
