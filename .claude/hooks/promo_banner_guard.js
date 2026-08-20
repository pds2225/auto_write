/**
 * promo-banner-localize 가드 훅
 *
 * UserPromptSubmit: 배너/16:9/K-Navi 요청이면 스킬 경로와 실측 규칙을 주입.
 * PostToolUse(GenerateImage): aspect_ratio=16:9 인데 파일이 3:2 이면 크롭 절차를 주입.
 *
 * 등록: .claude/settings.json (이 파일은 로직, 언제 돌지는 settings).
 * 매 프롬프트에 떠들지 않는다 — 키워드/16:9 생성에만 stdout JSON.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const SKILL = ".claude/skills/promo-banner-localize/SKILL.md";

const PROMPT_RE = new RegExp(
  [
    "k-?navi",
    "k-?네비",
    "케이내비",
    "kicxup",
    "16\\s*[:x×대]\\s*9",
    "16대9",
    "홍보\\s*(이미지|배너)",
    "배너\\s*(영문|한글|영어|한/영|한영)",
    "왼쪽\\s*상단\\s*숫자",
    "01\\s*빼",
    "같은\\s*구도.{0,12}(영문|한글|번역)",
  ].join("|"),
  "i"
);

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
  });
}

function emit(eventName, additionalContext) {
  process.stdout.write(
    JSON.stringify({
      continue: true,
      hookSpecificOutput: {
        hookEventName: eventName,
        additionalContext,
      },
    })
  );
}

function promptContext() {
  return (
    "[promo-banner-localize] 홍보 배너 요청으로 감지됨. " +
    "스킬 `" +
    SKILL +
    "` 를 읽고 따라라. " +
    "GenerateImage aspect_ratio=16:9 는 픽셀을 보장하지 않는다(실측 1536×1024=3:2). " +
    "생성 후 PIL/IHDR 로 가로÷세로를 재고, 1.7778 이 아니면 위(하늘)를 많이·아래(푸터)를 적게 잘라 1920×1080. " +
    "`01` 배지 금지. 푸터 철자 KICXUP 유지. PNG 는 사용자가 원할 때만 git 커밋."
  );
}

function pngSize(filePath) {
  try {
    const fd = fs.openSync(filePath, "r");
    const buf = Buffer.alloc(24);
    const n = fs.readSync(fd, buf, 0, 24, 0);
    fs.closeSync(fd);
    if (n < 24) return null;
    if (buf[0] !== 0x89 || buf[1] !== 0x50 || buf[2] !== 0x4e || buf[3] !== 0x47) {
      return null;
    }
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  } catch (_e) {
    return null;
  }
}

function collectPaths(payload) {
  const out = [];
  const input = payload.tool_input || payload.toolInput || {};
  const resp = payload.tool_response || payload.toolResponse || {};
  for (const v of [
    input.filename,
    input.path,
    input.file_path,
    resp.filename,
    resp.path,
    resp.file_path,
    resp.filePath,
  ]) {
    if (typeof v === "string" && v.length > 2) out.push(v);
  }
  const text = typeof resp === "string" ? resp : JSON.stringify(resp || {});
  const re = /(?:\/opt\/cursor\/artifacts|[\w./\\-]+)\S+\.(?:png|jpg|jpeg|webp)/gi;
  let m;
  while ((m = re.exec(text))) out.push(m[0]);
  return [...new Set(out)];
}

function isSixteenNineRequest(payload) {
  const input = payload.tool_input || payload.toolInput || {};
  const ar = String(input.aspect_ratio || input.aspectRatio || "").trim();
  if (ar === "16:9" || ar === "16x9") return true;
  const desc = String(input.description || input.prompt || "");
  return /16\s*[:x×]\s*9|1920\s*[x×]\s*1080/i.test(desc);
}

function ratioOk(w, h) {
  return Math.abs(w / h - 16 / 9) < 0.01;
}

function postImageContext(size, filePath) {
  return (
    "[promo-banner-localize] GenerateImage 가 16:9 로 요청됐지만 파일은 " +
    size.w +
    "×" +
    size.h +
    " (비율 " +
    (size.w / size.h).toFixed(4) +
    ") 이다. 16:9 완료로 보고하지 마라. `" +
    SKILL +
    "` 대로 가로 1920 스케일 후 위≈172px·아래≈28px 크롭 → 1920×1080. 파일: " +
    filePath
  );
}

function looksLikeImageTool(name) {
  return /generateimage|generate_image|image/i.test(String(name || ""));
}

async function main() {
  try {
    const raw = await readStdin();
    const payload = JSON.parse(raw || "{}");
    const event =
      payload.hook_event_name ||
      payload.hookEventName ||
      process.env.CLAUDE_HOOK_EVENT ||
      "";

    if (event === "UserPromptSubmit") {
      const prompt = String(payload.prompt || payload.user_prompt || "");
      if (PROMPT_RE.test(prompt)) emit(event, promptContext());
      return;
    }

    if (event === "PostToolUse") {
      if (!isSixteenNineRequest(payload)) return;
      const paths = collectPaths(payload).map((p) => {
        if (path.isAbsolute(p)) return p;
        const cwd = payload.cwd || process.cwd();
        return path.resolve(cwd, p);
      });
      for (const p of paths) {
        const size = pngSize(p);
        if (!size) continue;
        if (!ratioOk(size.w, size.h)) {
          emit(event, postImageContext(size, p));
          return;
        }
      }
    }
  } catch (_e) {
    // 훅 실패가 작업을 막지 않는다.
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  PROMPT_RE,
  pngSize,
  ratioOk,
  isSixteenNineRequest,
  looksLikeImageTool,
  promptContext,
};
