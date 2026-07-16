# Fluxo de Testes UI — Xtreme Motors

## Dados Base

- URL: `http://localhost:8000`
- Usuário admin: `admin` / `Admin123!`
- Navegador: Playwright CLI (`playwright-cli`)
- Pré-condição: banco migrado, app rodando (`make run`), admin ativo

## Convenção de Resultado

| Sigla | Significado |
|-------|-------------|
| PASS | Fluxo funcionou como esperado |
| FAIL | Bug encontrado |
| BLOCKED | Não foi possível continuar |
| N/A | Não se aplica |

---

## 1. Autenticação

### 1.1 Login — Fluxo Principal

**URL:** `/ui/login`

**Pré-condições:** Nenhuma (usuário deslogado)

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/login` | Título "Entrar · Xtreme Motors", formulário visível |
| 2 | Preencher `Usuário` com "admin" | Campo preenchido |
| 3 | Preencher `Senha` com "Admin123!" | Campo preenchido (mascarado) |
| 4 | Clicar "Entrar" | Redireciona para `/ui/veiculos` |
| 5 | Verificar cookie | `access_token` httpOnly presente |

### 1.2 Login — Senha Incorreta

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Preencher credenciais válidas + senha errada | HTTP 401 |
| 2 | Verificar mensagem | Alert: "Usuário ou senha inválidos" |
| 3 | Verificar URL | Permanece em `/ui/login` |

### 1.3 Login — Usuário Inexistente

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Preencher usuário inexistente | HTTP 401 |
| 2 | Verificar mensagem | Alert: "Usuário ou senha inválidos" (sem vazar info) |

### 1.4 Logout

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar botão de logout (sidebar) | Redireciona para `/ui/login` |
| 2 | Verificar cookie | `access_token` removido |
| 3 | Acessar página interna após logout | Redireciona para login |

### 1.5 Página Interna sem Autenticação

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/veiculos` sem cookie | Redireciona para `/ui/login` |
| 2 | Acessar `/ui/dashboard` sem cookie | Redireciona para `/ui/login` |

---

## 2. Sidebar / Layout Base

**URL:** Qualquer página autenticada

### 2.1 Estrutura da Sidebar

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Verificar seção "Visão Geral" | Link "Dashboard" visível (admin) |
| 2 | Verificar seção "Operações" | Links: Veículos, Compras, Custos, Vendas |
| 3 | Verificar seção "Pessoas" | Links: Investidores, Clientes Compradores, Clientes Vendedores |
| 4 | Verificar seção "Administração" | Links: Usuários, Auditoria, Perfis, Configurações |

### 2.2 Sidebar Footer

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Verificar tema | Botão "Alternar tema" visível |
| 2 | Verificar avatar | Inicial do username exibida |
| 3 | Verificar nome | Username visível |
| 4 | Verificar papel | "admin" visível |
| 5 | Verificar logout | Botão de logout presente |

### 2.3 Navegação entre Páginas

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Dashboard" | Carrega `/ui/dashboard` |
| 2 | Clicar "Veículos" | Carrega `/ui/veiculos` |
| 3 | Clicar "Compras" | Carrega `/ui/compras` |
| 4 | Clicar "Vendas" | Carrega `/ui/vendas` |
| 5 | Clicar "Investidores" | Carrega `/ui/investidores` |
| 6 | Clicar "Clientes Compradores" | Carrega `/ui/clientes/compradores` |
| 7 | Clicar "Clientes Vendedores" | Carrega `/ui/clientes/vendedores` |
| 8 | Clicar "Usuários" | Carrega `/ui/usuarios` (admin) |
| 9 | Clicar "Auditoria" | Carrega `/ui/auditoria` (admin) |
| 10 | Clicar "Perfis" | Carrega `/ui/perfis` (admin) |
| 11 | Clicar "Configurações" | Carrega `/ui/configuracoes` (admin) |

### 2.4 Link Ativo

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Verificar link ativo | Página atual destacada na sidebar |
| 2 | Navegar para outra página | Highlight muda para nova página |

### 2.5 Toggle Tema

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Alternar tema" | Tema alterna light/dark |
| 2 | Recarregar página | Tema persiste (localStorage) |

---

## 3. Dashboard

**URL:** `/ui/dashboard`

### 3.1 Carregamento

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/dashboard` | Título "Dashboard · Xtreme" |
| 2 | Verificar cards KPIs | Cards de resumo visíveis |
| 3 | Verificar filtro de período | Seletor de período (30d/90d/12m) |

---

## 4. Veículos

**URL:** `/ui/veiculos`

### 4.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/veiculos` | Título "Veículos · Xtreme" |
| 2 | Verificar cards de resumo | Total no estoque, Valor disponível, etc. |
| 3 | Verificar tabela | Colunas: Modelo, Placa, Tipo, Ano, KM, Status, Preço, etc. |
| 4 | Verificar colunas ordenáveis | Clique no header ordena a tabela |

### 4.2 Busca

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Buscar por modelo existente | Tabela filtra resultados |
| 2 | Buscar por placa existente | Tabela filtra resultados |
| 3 | Limpar busca | Lista completa restaurada |
| 4 | Buscar por termo inexistente | Tabela vazia ou mensagem "nenhum veículo" |

### 4.3 Exportar

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Exportar dados" | Download de CSV iniciado |
| 2 | Exportar com busca ativa | CSV filtrado pelo termo de busca |

### 4.4 Modal de Edição

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Editar" em um veículo | Modal abre com título "Editar veículo" |
| 2 | Verificar campos preenchidos | Dados do veículo carregados |
| 3 | Alterar um campo e salvar | Veículo atualizado na tabela |
| 4 | Clicar "Fechar" | Modal fecha sem alterar |

### 4.5 Wizard Novo Veículo

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Novo veículo" | Modal abre com "Passo 1 de 4" |
| 2 | Passo 1: selecionar Tipo e Tipo de Entrada | Campos preenchidos |
| 3 | Clicar "Próximo" | Avança para Passo 2 |
| 4 | Passo 2: preencher Placa, Modelo, Cor, Ano, Km | Campos preenchidos |
| 5 | Clicar "Próximo" | Avança para Passo 3 |
| 6 | Passo 3: preencher Preço, Débitos, Investidor | Campos preenchidos |
| 7 | Clicar "Próximo" | Avança para Passo 4 |
| 8 | Passo 4: selecionar/cadastrar cliente vendedor | Cliente selecionado/cadastrado |
| 9 | Clicar "Salvar" | Veículo criado, modal fecha, aparece na tabela |
| 10 | Clicar "Voltar" nos passos | Dados preservados ao voltar |
| 11 | Clicar "Cancelar" | Modal fecha sem criar |
| 12 | Salvar sem campos obrigatórios | Validação bloqueia envio |

### 4.6 Excluir Veículo

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Excluir" em um veículo | Diálogo de confirmação aparece |
| 2 | Confirmar exclusão | Veículo removido da tabela |
| 3 | Cancelar exclusão | Veículo permanece |

### 4.7 Imagens do Veículo

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Imagens de [modelo]" | Modal de imagens abre |
| 2 | Upload de imagem | Imagem carregada e exibida |
| 3 | Excluir imagem | Imagem removida |

### 4.8 Procuração do Veículo

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Procuração de [modelo]" | Modal de documentos abre |
| 2 | Upload de documento | Documento carregado |

### 4.9 Comprovante de Pagamento

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Comprovante de pagamento de [modelo]" | Modal abre |
| 2 | Upload de comprovante | Arquivo carregado |

### 4.10 Cliente Vendedor (documentos)

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Cliente vendedor de [modelo]" | Modal com docs do cliente abre |

---

## 5. Compras

**URL:** `/ui/compras`

### 5.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/compras` | Título "Compras · Xtreme" |
| 2 | Verificar tabela | Colunas de compra visíveis |

### 5.2 Cadastro

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Nova compra" | Formulário abre |
| 2 | Preencher campos obrigatórios | — |
| 3 | Salvar | Compra criada na tabela |

### 5.3 Edição / Exclusão

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Editar compra existente | Modal com dados preenchidos |
| 2 | Excluir compra | Confirmação + remoção |

---

## 6. Custos de Veículos

**URL:** `/ui/custos-veiculos`

### 6.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/custos-veiculos` | Título "Custos · Xtreme" |
| 2 | Verificar tabela | Colunas de custo visíveis |

### 6.2 CRUD

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Criar custo | Associar a veículo, salvar |
| 2 | Editar custo | Dados carregados no form |
| 3 | Excluir custo | Confirmar + remover |

---

## 7. Vendas

**URL:** `/ui/vendas`

### 7.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/vendas` | Título "Vendas · Xtreme" |
| 2 | Verificar tabela | Colunas de venda visíveis |

### 7.2 Cadastro de Venda

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Nova venda" | Formulário abre |
| 2 | Selecionar veículo disponível | Dropdown com veículos disponíveis |
| 3 | Preencher dados do comprador | Cliente comprador |
| 4 | Preencher valor de venda | — |
| 5 | Salvar | Venda criada |

### 7.3 Fechamento de Venda

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Fechamento" | Modal abre com distribuição de lucro |
| 2 | Configurar percentuais dos investidores | Soma deve ser 100% |
| 3 | Confirmar fechamento | Venda marcada como fechada |

### 7.4 Contrato

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Contrato" | Download/view do PDF |

---

## 8. Investidores

**URL:** `/ui/investidores`

### 8.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/investidores` | Título com tabela de investidores |
| 2 | Verificar colunas | Nome, Saldo, Veículos, Valor, Total Investido |
| 3 | Ordenar por coluna | Ordenação funciona |

### 8.2 Cadastro

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Novo investidor" | Form abre |
| 2 | Preencher nome e valor inicial | — |
| 3 | Salvar | Investidor criado |

### 8.3 Lançamentos

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar em um investidor | Abre tela de lançamentos |
| 2 | Criar lançamento manual | Aporte/retirada registrado |
| 3 | Editar lançamento | Dados atualizados |
| 4 | Tentar editar lançamento de veículo | Bloqueado (403) |
| 5 | Excluir lançamento | Confirmar + remover |

### 8.4 Exclusão com Histórico

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Tentar excluir investidor com lançamentos | Bloqueado |

---

## 9. Clientes Compradores

**URL:** `/ui/clientes/compradores`

### 9.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar página | Tabela com compradores |
| 2 | Verificar busca e ordenação | Funcionais |

### 9.2 CRUD

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Editar cliente | Form carrega dados |
| 2 | Excluir cliente | Confirmação + remoção |

---

## 10. Clientes Vendedores

**URL:** `/ui/clientes/vendedores`

### 10.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar página | Tabela com vendedores |

### 10.2 Veículos do Vendedor

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Veículos" | Modal com veículos do vendedor |

### 10.3 Documentos

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar "Documentos" | Modal de upload de documentos |

---

## 11. Usuários

**URL:** `/ui/usuarios` (admin)

### 11.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/usuarios` | Tabela com usuários |
| 2 | Verificar colunas | ID, Username, Papel, Ativo, Perfil |

### 11.2 Cadastro

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Preencher form inline e salvar | Usuário criado |
| 2 | Criar com username duplicado | Erro exibido |

### 11.3 Alterar Senha

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar no ícone de senha | Modal abre |
| 2 | Digitar nova senha e salvar | Senha alterada |

### 11.4 Alterar Perfil

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar no ícone de perfil | Modal com dropdown de perfis |
| 2 | Selecionar perfil e salvar | Perfil alterado |

### 11.5 Exclusão

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Excluir outro usuário | Confirmar + remover |
| 2 | Tentar excluir a si mesmo | Bloqueado |

---

## 12. Auditoria

**URL:** `/ui/auditoria` (admin)

### 12.1 Listagem

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/auditoria` | Tabela de logs de auditoria |
| 2 | Verificar filtros | Usuário, Tabela, Ação, Período |
| 3 | Aplicar filtro | Resultados filtrados via HTMX |
| 4 | Paginar resultados | Offset/Limit funcional |

### 12.2 Detalhe

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Clicar em um registro | Modal com diff JSON (antes/depois) |

---

## 13. Perfis

**URL:** `/ui/perfis` (admin)

### 13.1 Listagem e CRUD

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/perfis` | Tabela com perfis |
| 2 | Criar perfil com páginas | Checkboxes de páginas |
| 3 | Editar perfil | Páginas marcadas corretamente |
| 4 | Tentar excluir perfil com usuários | Bloqueado |

---

## 14. Configurações

**URL:** `/ui/configuracoes` (admin)

### 14.1 WhatsApp Config

| # | Passo | Resultado Esperado |
|---|-------|-------------------|
| 1 | Acessar `/ui/configuracoes` | Form com campos: API URL, Key, Instance, Group ID, Template |
| 2 | Preencher e salvar | Configuração persistida |
| 3 | Recarregar página | Dados carregados do banco |

---

## Resumo Executivo

| Área | Páginas | Endpoints UI |
|------|---------|-------------|
| Autenticação | Login, Logout | 3 |
| Sidebar/Layout | 12 links + tema + avatar | — |
| Dashboard | 1 | 1 |
| Veículos | Lista, Wizard, Edit, Imagens, Procuração, Comprovantes, Cliente Vendedor | 20 |
| Compras | Lista, CRUD, Comprovantes | 10 |
| Custos | Lista, CRUD | 7 |
| Vendas | Lista, CRUD, Fechamento, Contrato | 8 |
| Investidores | Lista, CRUD, Lançamentos | 14 |
| Clientes Compradores | Lista, CRUD, Veículos, Documentos | 9 |
| Clientes Vendedores | Lista, CRUD, Veículos, Documentos | 9 |
| Usuários | Lista, CRUD, Senha, Perfil | 8 |
| Auditoria | Lista, Filtros, Detalhe | 3 |
| Perfis | Lista, CRUD | 5 |
| Configurações | Form WhatsApp | 2 |
| **Total** | — | **~99 cenários** |
