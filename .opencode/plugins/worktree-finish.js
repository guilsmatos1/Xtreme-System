import { spawn } from "node:child_process";

let ran = false;

function run(cmd, args, cwd) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    child.stdout.on("data", (chunk) => (output += chunk));
    child.stderr.on("data", (chunk) => (output += chunk));
    child.on("error", (error) => resolve({ code: 127, output: String(error?.message ?? error) }));
    child.on("close", (code) => resolve({ code: code ?? 1, output }));
  });
}

async function isLinkedWorktree(cwd) {
  const gitDir = await run("git", ["rev-parse", "--absolute-git-dir"], cwd);
  const commonDir = await run("git", ["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd);
  if (gitDir.code !== 0 || commonDir.code !== 0) return false;
  return gitDir.output.trim() !== commonDir.output.trim();
}

export const WorktreeFinish = async ({ client, directory, worktree }) => ({
  event: async ({ event }) => {
    if (event.type !== "session.idle" || ran) return;

    const cwd = worktree ?? directory ?? process.cwd();
    if (!(await isLinkedWorktree(cwd))) return;

    ran = true;

    const sessionID = event.properties?.sessionID ?? event.sessionID;
    if (!sessionID) return;

    await client.session.prompt({
      path: { id: sessionID },
      body: {
        parts: [
          {
            type: "text",
            text: [
              "Estamos num worktree linkado e o trabalho terminou. Faca, em ordem:",
              "1) Use a skill commit-merge para: stage + commit das mudancas pendentes",
              "(mensagem concisa no estilo do repo) e merge --no-ff desta branch no master.",
              "Se nao houver nada para commitar e o master ja contiver a branch, pule este passo.",
              "2) SEMPRE ao final (mesmo que o passo 1 seja pulado), rode a skill",
              `0005-analyze-token-efficiency para esta sessao (SID=${sessionID}),`,
              "gravando os 5 blocos de melhoria no .loop do checkout principal.",
            ].join(" "),
          },
        ],
      },
    });
  },
});
