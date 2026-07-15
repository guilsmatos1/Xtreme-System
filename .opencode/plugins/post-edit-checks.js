import { spawn } from "node:child_process";

let edited = false;
let running = false;

const EDIT_TOOLS = new Set([
  "edit",
  "write",
  "patch",
  "replace_content",
  "replace_symbol_body",
  "insert_after_symbol",
  "insert_before_symbol",
  "rename_symbol",
  "create_text_file",
]);

const SHELL_EDIT_RE = /\b(apply_patch|cat\s*>|tee\b|sed\s+-i|python\b|mv\b|cp\b|rm\b|touch\b)\b/;
const MAX_OUTPUT_CHARS = 12000;

function shellCommand(args) {
  return String(args?.command ?? args?.cmd ?? args?.script ?? "");
}

function looksLikeEdit(tool, args) {
  const name = String(tool ?? "").toLowerCase();
  if (EDIT_TOOLS.has(name)) return true;
  if (["bash", "shell", "terminal"].includes(name)) {
    return SHELL_EDIT_RE.test(shellCommand(args));
  }
  return false;
}

const CHECKS = [
  { name: "ruff", args: ["run", "ruff", "check", "."] },
  { name: "ruff-format", args: ["run", "ruff", "format", ".", "--check"] },
  { name: "mypy", args: ["run", "mypy"] },
];

function runCommand(args, cwd) {
  return new Promise((resolve) => {
    const child = spawn("uv", args, {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk;
    });
    child.stderr.on("data", (chunk) => {
      output += chunk;
    });
    child.on("error", (error) => {
      resolve({ code: 127, output: String(error?.message ?? error) });
    });
    child.on("close", (code) => {
      resolve({ code: code ?? 1, output });
    });
  });
}

async function runChecks(cwd) {
  for (const check of CHECKS) {
    const result = await runCommand(check.args, cwd);
    if (result.code !== 0) {
      return { name: check.name, ...result };
    }
  }
  return null;
}

function trimOutput(output) {
  if (output.length <= MAX_OUTPUT_CHARS) return output;
  return output.slice(-MAX_OUTPUT_CHARS);
}

export const PostEditChecks = async ({ client, directory, worktree }) => ({
  "tool.execute.after": async (input, output) => {
    const args = output?.args ?? output?.metadata?.args ?? {};
    if (looksLikeEdit(input?.tool, args)) {
      edited = true;
    }
  },

  event: async ({ event }) => {
    if (event.type !== "session.idle") return;
    if (!edited || running) return;

    edited = false;
    running = true;

    const cwd = worktree ?? directory ?? process.cwd();
    const result = await runChecks(cwd);
    running = false;

    if (result === null) return;

    const sessionID = event.properties?.sessionID ?? event.sessionID;
    if (!sessionID) return;

    const output = trimOutput(result.output || `${result.name} failed without output.`);
    await client.session.prompt({
      path: { id: sessionID },
      body: {
        parts: [
          {
            type: "text",
            text: [
              `Post-edit check "${result.name}" failed.`,
              "",
              `Command: uv ${CHECKS.find((c) => c.name === result.name).args.join(" ")}`,
              "",
              "```",
              output,
              "```",
              "",
              "Fix failures. Run checks again after edits.",
            ].join("\n"),
          },
        ],
      },
    });
  },
});
