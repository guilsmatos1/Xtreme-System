#!/usr/bin/env python3
"""Helper: deleta permanentemente todas as issues concluídas (Done/Canceled/Duplicate)
do time GUI no Linear via API GraphQL, liberando slots do plano gratuito.

IMPORTANTE: issueDelete remove a issue permanentemente. Use delete_done_issues.py
apenas para liberar o limite de issues do plano gratuito.

Uso:
    python3 delete_done_issues.py [--team GUI] [--states done,canceled,duplicate] [--dry-run]
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

LINEAR_API_URL = "https://api.linear.app/graphql"
KEYCHAIN_SERVICE = "orca Safe Storage"
TOKEN_DIR = os.path.expanduser("~/.orca/linear-tokens")
WORKSPACE_FILE = os.path.expanduser("~/.orca/linear-workspaces.json")

# Mapeamento de tipo de estado -> nome humano
STATE_TYPES_DEFAULT = {"completed", "canceled", "duplicate"}


def get_linear_token() -> str:
    """Descriptografa o token do Linear armazenado pelo orca usando safeStorage do Electron."""
    # 1. Obter a senha do Keychain
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao ler Keychain ({KEYCHAIN_SERVICE}): {result.stderr.strip()}")

    password_b64 = result.stdout.strip()

    # 2. Derivar a chave AES usando PBKDF2 (parâmetros do Electron safeStorage macOS v10)
    key = hashlib.pbkdf2_hmac(
        "sha1",
        password_b64.encode("utf-8"),
        b"saltysalt",
        1003,
        dklen=16,
    )

    # 3. Encontrar o arquivo de token encriptado
    enc_files = [f for f in os.listdir(TOKEN_DIR) if f.endswith(".enc")]
    if not enc_files:
        raise RuntimeError(f"Nenhum token encontrado em {TOKEN_DIR}")

    token_path = os.path.join(TOKEN_DIR, enc_files[0])
    with open(token_path, "rb") as f:
        enc_data = f.read()

    # 4. Formato v10: b"v10" + ciphertext (IV fixo = 16 espaços)
    if not enc_data.startswith(b"v10"):
        raise RuntimeError(f"Formato de token desconhecido: {enc_data[:3]}")

    ciphertext = enc_data[3:]
    iv = b" " * 16

    # 5. Descriptografar com AES-128-CBC via openssl
    result = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
        input=ciphertext, capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao descriptografar token: {result.stderr.decode()}")

    raw = result.stdout
    # Remover PKCS7 padding
    pad_len = raw[-1]
    if 0 < pad_len <= 16:
        raw = raw[:-pad_len]

    token = raw.decode("utf-8").strip()
    if not token.startswith("lin_api_"):
        raise RuntimeError(f"Token inválido (não começa com lin_api_): {token[:20]}...")
    return token


def graphql(token: str, query: str, variables: dict | None = None) -> dict:
    """Faz uma requisição à API GraphQL do Linear."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        LINEAR_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code}: {body}")


LIST_ISSUES_QUERY = """
query($teamId: ID!, $stateTypes: [String!]!, $after: String) {
  issues(
    filter: {
      team: { id: { eq: $teamId } }
      state: { type: { in: $stateTypes } }
    }
    first: 100
    after: $after
  ) {
    nodes { id identifier title state { name type } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

DELETE_ISSUE_MUTATION = """
mutation($id: String!) {
  issueDelete(id: $id) {
    success
  }
}
"""


def get_team_id(token: str, team_key: str) -> str:
    """Retorna o UUID do time pelo key (ex: GUI)."""
    data = graphql(token, "query { teams { nodes { id key } } }")
    for team in data["data"]["teams"]["nodes"]:
        if team["key"] == team_key:
            return team["id"]
    raise RuntimeError(f"Time '{team_key}' não encontrado")


def list_issues_by_state_types(token: str, team_id: str, state_types: list[str]) -> list[dict]:
    """Lista todas as issues nos tipos de estado especificados (paginando)."""
    issues = []
    cursor = None
    while True:
        data = graphql(token, LIST_ISSUES_QUERY, {
            "teamId": team_id,
            "stateTypes": state_types,
            "after": cursor,
        })
        nodes = data["data"]["issues"]["nodes"]
        issues.extend(nodes)
        page_info = data["data"]["issues"]["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
    return issues


def delete_issue(token: str, issue_id: str, dry_run: bool) -> bool:
    """Deleta permanentemente uma issue. Retorna True se bem-sucedido."""
    if dry_run:
        return True
    data = graphql(token, DELETE_ISSUE_MUTATION, {"id": issue_id})
    return data.get("data", {}).get("issueDelete", {}).get("success", False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deleta permanentemente issues concluídas do Linear para liberar slots."
    )
    parser.add_argument("--team", default="GUI", help="Chave do time (padrão: GUI)")
    parser.add_argument(
        "--states",
        default="completed,canceled,duplicate",
        help="Tipos de estado a deletar (padrão: completed,canceled,duplicate)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simula sem deletar nada")
    args = parser.parse_args()

    state_types = [s.strip() for s in args.states.split(",")]
    mode = "[dry-run] " if args.dry_run else ""

    print(f"{mode}Obtendo token do Linear...")
    try:
        token = get_linear_token()
    except Exception as e:
        print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{mode}Buscando ID do time {args.team}...")
    try:
        team_id = get_team_id(token, args.team)
    except Exception as e:
        print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{mode}Listando issues com estados: {', '.join(state_types)}...")
    try:
        issues = list_issues_by_state_types(token, team_id, state_types)
    except Exception as e:
        print(f"  ✗ Falha ao listar issues: {e}", file=sys.stderr)
        sys.exit(1)

    if not issues:
        print("Nenhuma issue encontrada para deletar.")
        return

    total = len(issues)
    print(f"Encontradas {total} issue(s). {'Simulando deleção' if args.dry_run else 'Deletando'}...")

    success = 0
    for i, issue in enumerate(issues, 1):
        identifier = issue.get("identifier", "???")
        title = issue.get("title", "")[:60]
        state_name = issue.get("state", {}).get("name", "?")
        print(f"  [{i}/{total}] {identifier} ({state_name}): {title}")
        try:
            ok = delete_issue(token, issue["id"], args.dry_run)
            if ok:
                success += 1
            else:
                print(f"    ✗ Falha (API retornou success=false)", file=sys.stderr)
        except Exception as e:
            print(f"    ✗ Erro: {e}", file=sys.stderr)

    action = "seriam deletadas" if args.dry_run else "deletadas"
    print(f"\nDone! {success}/{total} issues {action}.")


if __name__ == "__main__":
    main()
