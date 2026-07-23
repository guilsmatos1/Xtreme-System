#!/usr/bin/env bash
# Pipeline contínuo: mantém até MAX_CONCURRENT workers de issues Linear (GUI, priority 1/2,
# estado Backlog) rodando ao mesmo tempo, repondo automaticamente cada slot assim que um
# worker termina, até o backlog elegível se esgotar.
#
# Usa `orca terminal wait --for exit` (primitivo nativo do Orca, fora da feature experimental
# "Orchestration") como sinal de conclusão — não faz polling manual.
#
# Compatível com bash 3.2 (padrão do macOS) — usa arrays indexados por slot fixo em vez de
# arrays associativos (declare -A só existe a partir do bash 4).
#
# Rode isto em background/tmux/nohup, não numa sessão interativa curta:
#   nohup ./run-loop.sh > run-loop.log 2>&1 &
#
# Para parar: mate o processo (os workers em si continuam rodando em seus próprios terminais
# Orca até concluir; isto só para de lançar NOVOS workers).

set -uo pipefail

REPO_DIR="/Users/guilsmatos/orca/projects/xtreme-system"
SPEC_FILE="$REPO_DIR/.agents/skills/0002-linear-batch-worktrees/orchestration-spec.txt"
MAX_CONCURRENT=3
WAIT_TIMEOUT_MS=$((2 * 60 * 60 * 1000))  # 2h de teto de segurança por worker

# Slots fixos 1..MAX_CONCURRENT. Vazio ("") = slot livre.
# Índices atribuídos explicitamente (1,2,3): sob `set -u`, o bash 3.2 trata leitura de um
# índice de array nunca atribuído como "unbound variable" (só foi corrigido no bash 4.4+).
SLOT_ID=([1]="" [2]="" [3]="")
SLOT_HANDLE=([1]="" [2]="" [3]="")
SLOT_WAITPID=([1]="" [2]="" [3]="")

log() { echo "[$(date '+%H:%M:%S')] $*"; }

active_ids_csv() {
  local csv=""
  local i
  for i in 1 2 3; do
    if [[ -n "${SLOT_ID[$i]}" ]]; then
      csv+="${SLOT_ID[$i]},"
    fi
  done
  echo "${csv:-nenhuma}"
}

active_count() {
  local c=0
  local i
  for i in 1 2 3; do
    [[ -n "${SLOT_ID[$i]}" ]] && c=$((c + 1))
  done
  echo "$c"
}

launch_next() {
  local slot="$1"
  local active_ids
  active_ids=$(active_ids_csv)

  local picker_prompt
  picker_prompt=$(cat <<EOF
Siga a lógica descrita em ${SPEC_FILE} (time GUI, prioridade 1 ou 2, estado Backlog), mas
selecione e processe SOMENTE UMA issue nesta chamada, não um lote de 3.

Issues já em andamento agora (não escolha nenhuma que conflite em arquivos com estas): ${active_ids}

Se não houver nenhuma issue elegível restante (respeitando prioridade, estado Backlog, preflight
de worktree/branch existente, e a checagem de conflito de arquivos contra as issues acima),
imprima em stdout SOMENTE a palavra NONE e pare, sem criar nada.

Caso contrário: rode o preflight, crie o worktree vinculado, mova a issue Linear para
"In Progress", e lance o worker (opencode --auto) dentro do worktree exatamente como descrito
no passo 8 do spec.

IMPORTANTE: assim que o comando \`orca terminal create\` do worker retornar com sucesso, sua
tarefa termina IMEDIATAMENTE. NÃO chame \`orca terminal wait\`, \`orca terminal read\` ou
qualquer outra checagem no terminal do worker. NÃO espere o worker terminar, progredir, ou
produzir qualquer saída — isso é feito por outro processo, não por você. Imprima o JSON de
retorno na hora, logo após o \`orca terminal create\` responder, e finalize sua execução.

Imprima em stdout, e SOMENTE na última linha, um JSON de uma linha, sem formatação extra, no
formato:
{"identifier":"<identifier>","handle":"<terminal handle do worker recém-criado>"}
EOF
)

  local out
  out=$(cd "$REPO_DIR" && opencode --auto --model openai/gpt-5.5 --prompt "$picker_prompt" 2>/dev/null | tail -n1)

  if [[ -z "$out" || "$out" == "NONE" ]]; then
    return 1
  fi

  local id handle
  id=$(echo "$out" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin)["identifier"])
except Exception:
    pass' 2>/dev/null)
  handle=$(echo "$out" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin)["handle"])
except Exception:
    pass' 2>/dev/null)

  if [[ -z "$id" || -z "$handle" ]]; then
    log "slot $slot: picker não retornou JSON válido, pulando esta rodada. Saída bruta: $out"
    return 1
  fi

  SLOT_ID[$slot]="$id"
  SLOT_HANDLE[$slot]="$handle"

  (
    orca terminal wait --terminal "$handle" --for exit --timeout-ms "$WAIT_TIMEOUT_MS" --json >/dev/null 2>&1
    exit 0
  ) &
  SLOT_WAITPID[$slot]=$!

  log "slot $slot: $id lançado (terminal $handle, wait pid ${SLOT_WAITPID[$slot]})"
  return 0
}

log "iniciando pipeline contínuo (max $MAX_CONCURRENT simultâneos)"

for slot in 1 2 3; do
  launch_next "$slot" || true
done

while true; do
  if [[ "$(active_count)" -eq 0 ]]; then
    log "nenhum worker ativo e nenhuma issue elegível restante. Encerrando."
    break
  fi

  # bash 3.2 (padrão do macOS) não tem `wait -n`, então fazemos um poll leve nos PIDs
  # locais dos subshells de `orca terminal wait` até um deles sair. Isto não faz polling
  # na API do Orca — só checa se o processo local já encerrou.
  finished_slot=""
  while [[ -z "$finished_slot" ]]; do
    for slot in 1 2 3; do
      pid="${SLOT_WAITPID[$slot]}"
      if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        finished_slot="$slot"
        break
      fi
    done
    [[ -z "$finished_slot" ]] && sleep 5
  done

  log "slot $finished_slot (${SLOT_ID[$finished_slot]}) terminou (via orca terminal wait --for exit)."
  SLOT_ID[$finished_slot]=""
  SLOT_HANDLE[$finished_slot]=""
  SLOT_WAITPID[$finished_slot]=""

  launch_next "$finished_slot" || true
done
