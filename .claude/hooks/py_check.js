/**
 * Python 파일 자동 문법 검사 훅 (PostToolUse: Write|Edit)
 *
 * 목적: Claude가 .py 파일을 수정한 직후, 해당 파일에 파이썬 문법 오류가
 *       있는지 즉시 검사한다. 오류가 있으면 systemMessage로 사용자에게 경고한다.
 *
 * 설계 메모(비개발자용):
 * - 이 파일은 "검사 로직"이고, 등록(언제 실행할지)은 settings.local.json 에 있다.
 * - py_compile 은 import 를 실행하지 않고 "문법"만 빠르게 검사한다(보통 1초 이내).
 * - 검사에 쓰는 python 은 이 프로젝트 고정 버전(3.11)으로 직접 지정한다.
 *   (시스템 기본 python 3.14 가 아니라 3.11 을 써야 하므로 경로를 고정)
 * - jq 가 없는 환경이라, stdin 의 JSON 은 node 로 직접 파싱한다.
 */
"use strict";

const PYTHON = "C:/Users/ekth3/AppData/Local/Programs/Python/Python311/python.exe";

let data = "";
process.stdin.on("data", (chunk) => (data += chunk));
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(data || "{}");
    const filePath =
      (payload.tool_input && payload.tool_input.file_path) ||
      (payload.tool_response && payload.tool_response.filePath) ||
      "";

    // 파이썬 파일이 아니면 아무것도 하지 않는다(빠르게 통과).
    if (!filePath.endsWith(".py")) return;

    const { spawnSync } = require("child_process");
    const path = require("path");

    const result = spawnSync(PYTHON, ["-m", "py_compile", filePath], {
      encoding: "utf8",
    });

    // status 0 = 문법 정상 → 조용히 종료(메시지 없음)
    if (result.status === 0) return;

    // 문법 오류 또는 실행 실패 → 사용자에게 경고 메시지 표시
    const baseName = path.basename(filePath);
    const detail = (
      result.stderr ||
      (result.error && result.error.message) ||
      "문법 오류"
    )
      .trim()
      .slice(-600); // 너무 길면 끝부분(실제 오류 위치)만

    console.log(
      JSON.stringify({
        systemMessage: "⚠️ Python 문법 오류 감지 — " + baseName + "\n" + detail,
      })
    );
  } catch (e) {
    // 훅 자체 오류는 작업을 막지 않도록 조용히 무시한다.
  }
});
