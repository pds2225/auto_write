/**
 * session-resume 훅 — "이어서/세션마무리/체크포인트"일 때만 스킬을 주입.
 * 매 프롬프트에 안 떠든다. 배너·16:9 같은 일회성 키워드는 넣지 않는다.
 */
"use strict";

const RE =
  /세션\s*마무리|세션마무리|체크포인트\s*저장|이어서|세션\s*재개|어디까지\s*했|session-resume/i;

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
  });
}

// Windows 부모 프로세스가 기본 cp949로 stdout을 읽어도 JSON이 깨지지 않게
// 비ASCII 문자를 \uXXXX escape로 직렬화한다. JSON을 파싱하면 원문이 복원된다.
function stringifyAscii(value) {
  return JSON.stringify(value).replace(/[^\x00-\x7F]/g, (char) => {
    const code = char.charCodeAt(0);
    return `\\u${code.toString(16).padStart(4, "0")}`;
  });
}

async function main() {
  try {
    const payload = JSON.parse((await readStdin()) || "{}");
    const event = payload.hook_event_name || payload.hookEventName || "";
    if (event !== "UserPromptSubmit") return;
    const prompt = String(payload.prompt || payload.user_prompt || "");
    if (!RE.test(prompt)) return;
    process.stdout.write(
      stringifyAscii({
        continue: true,
        hookSpecificOutput: {
          hookEventName: "UserPromptSubmit",
          additionalContext:
            "[session-resume] `.claude/skills/session-resume/SKILL.md` 를 읽고 그 모드(재개/일시정지/종료)로 진행하라. " +
            "RESUME.md 가 SSOT. git fetch origin main 후 핀. 일회성 PNG는 스킬화·커밋하지 마라.",
        },
      })
    );
  } catch (_e) {
    // 훅 실패가 세션을 막지 않는다.
  }
}

main();
