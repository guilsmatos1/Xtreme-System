#!/usr/bin/env bash
set -uo pipefail

BASE_URL="http://localhost:8000"
SUFFIX="$(date +%s)"   # uniqueness for repeated pre-commit runs
PASS=0
FAIL=0
RESULTS=""

# ── helpers ──────────────────────────────────────────────────────────────

pw() { playwright-cli --raw "$@" 2>/dev/null; }

check() {
  local label="$1" found
  found=$(playwright-cli --raw find "$2" 2>/dev/null || true)
  if [[ -n "$found" ]]; then
    ((PASS++))
    RESULTS+="PASS  $label"$'\n'
  else
    ((FAIL++))
    RESULTS+="FAIL  $label"$'\n'
  fi
}

check_no() {
  local label="$1" found
  found=$(playwright-cli --raw find "$2" 2>/dev/null || true)
  if [[ -z "$found" ]]; then
    ((PASS++))
    RESULTS+="PASS  $label"$'\n'
  else
    ((FAIL++))
    RESULTS+="FAIL  $label"$'\n'
  fi
}

check_url() {
  local label="$1" expected="$2"
  local url
  url=$(playwright-cli --raw eval "document.location.href" 2>/dev/null || true)
  url="${url//\"/}"   # strip quotes from JS string
  if [[ "$url" == "$expected" ]]; then
    ((PASS++))
    RESULTS+="PASS  $label"$'\n'
  else
    ((FAIL++))
    RESULTS+="FAIL  $label (got: $url)"$'\n'
  fi
}

check_http_status() {
  local label="$1" expected="$2"
  local status
  status=$(playwright-cli --raw eval "document.querySelector('meta[name=status]')?.content" 2>/dev/null || true)
  check "$label" "$expected"
}

# ── setup ───────────────────────────────────────────────────────────────

echo "=== Testes UI Xtreme Motors ==="
echo ""

pw open "$BASE_URL/ui/login" >/dev/null

# ── 1. Login ────────────────────────────────────────────────────────────

echo "--- 1. Login ---"

pw fill "getByRole('textbox', { name: 'Usuário' })" "admin" >/dev/null
pw fill "getByRole('textbox', { name: 'Senha' })" "Admin123!" >/dev/null
pw click "getByRole('button', { name: 'Entrar' })" >/dev/null
check_url "1.1 login redireciona para veículos" "$BASE_URL/ui/veiculos"
check "1.2 título após login" "Veículos · Xtreme"

# ── 2. Login — senha incorreta ─────────────────────────────────────────

echo "--- 2. Login negativo ---"

pw goto "$BASE_URL/ui/login" >/dev/null
pw fill "getByRole('textbox', { name: 'Usuário' })" "admin" >/dev/null
pw fill "getByRole('textbox', { name: 'Senha' })" "errada" >/dev/null
pw click "getByRole('button', { name: 'Entrar' })" >/dev/null
check "2.1 mensagem de erro" "Usuário ou senha inválidos"
check_url "2.2 permanece login (erro 401)" "$BASE_URL/ui/login"

# ── login novamente ────────────────────────────────────────────────────

pw fill "getByRole('textbox', { name: 'Usuário' })" "admin" >/dev/null
pw fill "getByRole('textbox', { name: 'Senha' })" "Admin123!" >/dev/null
pw click "getByRole('button', { name: 'Entrar' })" >/dev/null

# ── 3. Sidebar — navegação entre páginas ───────────────────────────────

echo "--- 3. Sidebar ---"

nav_to() {
  local label="$1" url="$2"
  pw click "getByRole('link', { name: '$label' })" >/dev/null || true
  check_url "3. nav $label" "$url"
}

nav_to "Dashboard"       "$BASE_URL/ui/dashboard"
nav_to "Veículos"        "$BASE_URL/ui/veiculos"
nav_to "Compras"         "$BASE_URL/ui/compras"
nav_to "Vendas"          "$BASE_URL/ui/vendas"
nav_to "Investidores"    "$BASE_URL/ui/investidores"
nav_to "Clientes Compradores"  "$BASE_URL/ui/clientes/compradores"
nav_to "Clientes Vendedores"   "$BASE_URL/ui/clientes/vendedores"
nav_to "Usuários"        "$BASE_URL/ui/usuarios"
nav_to "Auditoria"       "$BASE_URL/ui/auditoria"
nav_to "Perfis"          "$BASE_URL/ui/perfis"
nav_to "Configurações"   "$BASE_URL/ui/configuracoes"

pw click "getByRole('link', { name: 'Veículos' })" >/dev/null
check_url "3.2 nav volta veículos" "$BASE_URL/ui/veiculos"

# ── 4. Sidebar — elementos fixos ───────────────────────────────────────

echo "--- 4. Sidebar elementos ---"

check "4.1 botão tema" "Alternar tema"
check "4.2 avatar admin" "admin"
check "4.3 botão logout" "logout"

# ── 5. Veículos — busca ────────────────────────────────────────────────

echo "--- 5. Veículos ---"

check "5.1 resumo estoque" "Resumo do estoque"
check "5.2 tabela veículos" "Modelo"

pw fill "getByRole('searchbox', { name: 'Buscar veículos' })" "XRE" --submit >/dev/null
check "5.3 busca XRE" "XRE 190 SE"

pw fill "getByRole('searchbox', { name: 'Buscar veículos' })" "" --submit >/dev/null
check "5.4 limpar busca" "ONIX"

# ── 6. Veículos — editar ───────────────────────────────────────────────

echo "--- 6. Veículos editar ---"

pw click "getByRole('button', { name: 'Editar XRE 190 SE' })" >/dev/null
check "6.1 modal editar abre" "Editar veículo"
pw click "getByRole('button', { name: 'Fechar' })" >/dev/null
check_url "6.2 modal fecha" "$BASE_URL/ui/veiculos"

# ── 7. Veículos — wizard novo ──────────────────────────────────────────

echo "--- 7. Wizard novo veículo ---"

pw click "getByRole('button', { name: 'Novo veículo' })" >/dev/null
check "7.1 passo 1 abre" "Passo 1 de 4"

pw click "getByRole('button', { name: 'Próximo' })" >/dev/null
check "7.2 passo 2" "Passo 2 de 4"

pw fill "getByRole('textbox', { name: 'Placa' })" "TST$SUFFIX" >/dev/null
pw fill "getByRole('textbox', { name: 'Modelo' })" "Teste $SUFFIX" >/dev/null
pw fill "getByRole('textbox', { name: 'Cor' })" "Azul" >/dev/null
pw fill "getByRole('spinbutton', { name: 'Ano' })" "2023" >/dev/null
pw fill "getByRole('spinbutton', { name: 'Quilometragem' })" "10000" >/dev/null

pw click "getByRole('button', { name: 'Próximo' })" >/dev/null
check "7.3 passo 3" "Passo 3 de 4"

pw fill "getByRole('spinbutton', { name: 'Preço de Compra (R\$)' })" "25000" >/dev/null
pw fill "getByRole('spinbutton', { name: 'Débitos (R\$)' })" "1000" >/dev/null

pw click "getByRole('button', { name: 'Próximo' })" >/dev/null
check "7.4 passo 4" "Passo 4 de 4"

pw fill "getByRole('textbox', { name: 'Nome' })" "Cliente $SUFFIX" >/dev/null
pw fill "getByRole('textbox', { name: 'CPF' })" "$SUFFIX" >/dev/null
pw fill "getByRole('textbox', { name: 'Telefone' })" "11988888888" >/dev/null
pw fill "getByRole('textbox', { name: 'Email' })" "cli@teste.com" >/dev/null
pw fill "getByRole('textbox', { name: 'Endereço' })" "Av Teste, 1" >/dev/null
pw fill "getByRole('textbox', { name: 'Cidade' })" "SP" >/dev/null
pw fill "getByRole('textbox', { name: 'CEP' })" "01001000" >/dev/null

pw click "getByRole('button', { name: 'Salvar' })" >/dev/null

pw fill "getByRole('searchbox', { name: 'Buscar veículos' })" "Teste $SUFFIX" --submit >/dev/null
check "7.5 veículo criado na tabela" "Teste $SUFFIX"
check "7.6 placa correta" "TST$SUFFIX"

# ── 8. Compras ─────────────────────────────────────────────────────────

echo "--- 8. Compras ---"

pw click "getByRole('link', { name: 'Compras' })" >/dev/null
check "8.1 página compras" "Compras · Xtreme"

# ── 9. Vendas ──────────────────────────────────────────────────────────

echo "--- 9. Vendas ---"

pw click "getByRole('link', { name: 'Vendas' })" >/dev/null
check "9.1 página vendas" "Vendas · Xtreme"

# ── 10. Custos ─────────────────────────────────────────────────────────

echo "--- 10. Custos ---"

pw click "getByRole('link', { name: 'Custos' })" >/dev/null
check "10.1 página custos" "Custos"

# ── 11. Investidores ───────────────────────────────────────────────────

echo "--- 11. Investidores ---"

pw click "getByRole('link', { name: 'Investidores' })" >/dev/null
check "11.1 página investidores" "Investidores"

# ── 12. Clientes Compradores ───────────────────────────────────────────

echo "--- 12. Clientes Compradores ---"

pw click "getByRole('link', { name: 'Clientes Compradores' })" >/dev/null
check "12.1 página compradores" "Compradores"

# ── 13. Clientes Vendedores ────────────────────────────────────────────

echo "--- 13. Clientes Vendedores ---"

pw click "getByRole('link', { name: 'Clientes Vendedores' })" >/dev/null
check "13.1 página vendedores" "Vendedores"

# ── 14. Usuários ───────────────────────────────────────────────────────

echo "--- 14. Usuários ---"

pw click "getByRole('link', { name: 'Usuários' })" >/dev/null
check "14.1 página usuários" "Usuários"

# ── 15. Auditoria ──────────────────────────────────────────────────────

echo "--- 15. Auditoria ---"

pw click "getByRole('link', { name: 'Auditoria' })" >/dev/null
check "15.1 página auditoria" "Auditoria"

# ── 16. Perfis ─────────────────────────────────────────────────────────

echo "--- 16. Perfis ---"

pw click "getByRole('link', { name: 'Perfis' })" >/dev/null
check "16.1 página perfis" "Perfis"

# ── 17. Configurações ──────────────────────────────────────────────────

echo "--- 17. Configurações ---"

pw click "getByRole('link', { name: 'Configurações' })" >/dev/null
check "17.1 página configurações" "Configurações"

# ── 18. Toggle tema ────────────────────────────────────────────────────

echo "--- 18. Tema ---"

pw click "getByRole('button', { name: 'Alternar tema' })" >/dev/null
check "18.1 tema alternou" "theme"

# ── 19. Logout ─────────────────────────────────────────────────────────

echo "--- 19. Logout ---"

playwright-cli eval "document.querySelector('form[action=\"/ui/logout\"]').submit()" >/dev/null 2>&1 || true
sleep 2

check_url "19.1 logout redireciona para login" "$BASE_URL/ui/login"

playwright-cli goto "$BASE_URL/ui/veiculos" >/dev/null 2>&1 || true
sleep 1
check_url "19.2 página protegida redireciona" "$BASE_URL/ui/login"

# ── close ──────────────────────────────────────────────────────────────

pw close >/dev/null 2>/dev/null || true

# ── summary ────────────────────────────────────────────────────────────

echo ""
echo "===================================="
echo "          RESULTADO FINAL"
echo "===================================="
echo ""
echo "$RESULTS"
echo "---"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $((PASS + FAIL))"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "❌ $FAIL teste(s) falharam"
  exit 1
else
  echo "✅ Todos os $PASS testes passaram"
fi
