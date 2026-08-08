# Improvement opportunities

- **Generated:** 2026-08-07T13:54:20-03:00
- **Total:** 7

## imp-20260807-001 — Cobrir em E2E o ciclo completo da aba Portal RSD

- **Impact:** High
- **Category:** Untested critical paths
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** testing, e2e, rsd, credentials, playwright
- **Files affected:** `tests/e2e/test_rsd_puxar_dados.py`, `tests/e2e/`, `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
- **Related opportunities:** imp-20260807-002, imp-20260807-004, imp-20260807-005

### Location

`tests/e2e/test_rsd_puxar_dados.py:40` — `test_puxar_dados_substitui_campos_do_modal`

```python
def test_puxar_dados_substitui_campos_do_modal(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")

    page.locator("tr", has_text="Onix").get_by_role(
        "button", name="Editar Onix"
    ).click()
    dialog = page.get_by_role("dialog", name="Editar veículo")
    expect(dialog).to_be_visible()

    page.route(
        "**/ui/rsd/puxar-dados",
```

### Description

Os quatro E2E RSD exercitam “Puxar dados” em formulários de veículo/compra, mas nenhum abre Configurações → Portal RSD. O ciclo digitar → testar → tratar erro → salvar → recarregar → trocar → remover credenciais fica validado apenas por leitura de template e testes de rota.

### Why it matters

Regressões de valores perdidos, aba errada, estado contraditório, senha restaurada pelo navegador, loading e histórico passam pela suite mesmo quando o backend unitário está verde. Foram executados 4 E2E atuais, todos aprovados, sem tocar a jornada de configuração.

### Concrete fix

Criar `tests/e2e/test_rsd_configuracao.py` com o portal externo interceptado. Cobrir primeiro cadastro, credencial inválida, timeout, sucesso não salvo, salvamento, reload/back, edição com senha em branco e revogação. Assertar estado visível, valores dos campos, foco, botões e quantidade de requests.

### Domain details

#### Test matrix

- Não configurado → teste inválido → rascunho preservado.
- Não configurado → teste válido → salvar → reload → verificado.
- Configurado → alterar só e-mail → senha preservada e status invalidado.
- Configurado → remover → consultas bloqueadas como não configurado.
- Teste lento → um único request e controles desabilitados.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - A suite E2E foi enumerada e executada; nenhum teste visita a tela de configurações RSD.
- **Weaknesses:**
  - A futura revogação ainda não existe e só poderá ser testada junto da implementação.
- **Suggested checks:**
  - Executar a nova matriz nos navegadores suportados pela CI.

## imp-20260807-002 — Assertar que o teste preserva o rascunho e não ativa a configuração

- **Impact:** High
- **Category:** Assertion quality
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** high
- **Tags:** testing, rsd, form-state, assertions
- **Files affected:** `tests/test_rsd.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`
- **Related opportunities:** imp-20260807-001

### Location

`tests/test_rsd.py:829` — `test_ui_teste_conexao_usa_valores_do_formulario_nao_do_banco`

```python
    resp = client.post(
        "/ui/configuracoes/rsd/teste",
        data={
            "email": "digitado@test.com",
            "senha": "senha-digitada",
            "base_url": "https://rsd.test",
        },
    )

    assert resp.status_code == 200
    assert "Conexão com o portal RSD OK." in resp.text
    assert recebido == {
        "base_url": "https://rsd.test",
```

### Description

O teste confirma os argumentos enviados ao cliente e a mensagem de sucesso, mas não inspeciona os campos renderizados nem o painel de status. Por isso aprova uma resposta que perdeu o e-mail/URL digitados e que simultaneamente afirma sucesso e “não configurado”.

### Why it matters

Uma asserção centrada só na chamada interna protege o wiring, não o comportamento observável do usuário. O bug principal da jornada permanece verde.

### Concrete fix

Após o POST, parsear a resposta e afirmar que e-mail e URL do rascunho continuam presentes, senha não aparece, o estado persistido segue não configurado e a mensagem diz explicitamente “testado, ainda não salvo”. Repetir para erro de autenticação e timeout.

### Domain details

#### Tests

- Sucesso com banco vazio preserva campos seguros e não marca ativo.
- Erro preserva campos seguros e associa mensagem ao bloco RSD.
- Resposta nunca contém a senha digitada.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - As asserções atuais e a resposta da rota foram lidas em conjunto.
- **Weaknesses:**
  - A forma exata de representar “rascunho testado” depende da decisão de UX.
- **Suggested checks:**
  - Definir o contrato HTML/HTMX antes de estabilizar locators excessivamente específicos.

## imp-20260807-003 — Cobrir expiração entre o GET e o POST da consulta unitária

- **Impact:** High
- **Category:** Missing negative and edge-case coverage
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** testing, rsd, csrf, session-expiry, retry
- **Files affected:** `components/xtreme_system/rsd/core.py`, `tests/test_rsd.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/rsd/core.py:711` — `RsdClient.iniciar_unitaria`

```python
        resp = self._request(
            "POST",
            _UNITARIA_PATH,
            data={
                "csrfmiddlewaretoken": csrf,
                "fonte": "be",
                "placa": placa_norm,
            },
            headers={
                "Origin": self.base_url,
                "Referer": self._url(_UNITARIA_PATH),
                "Content-Type": "application/x-www-form-urlencoded",
```

### Description

O wrapper reloga ao receber 401/403, mas este POST leva o CSRF antigo tanto no corpo quanto nos headers estáticos. Se a sessão expirar depois do GET da página unitária e antes do POST, o retry faz login e reenvia os mesmos dados obsoletos. Os testes atuais cobrem expiração no GET, não essa janela entre etapas.

### Why it matters

É uma corrida real de autenticação: a lógica promete recuperação automática, mas a consulta ainda pode falhar após o relogin. O cache compartilhado e requests concorrentes aumentam a chance dessa janela.

### Concrete fix

Escrever primeiro um teste MockTransport em que o GET retorna formulário válido, o primeiro POST retorna 403, o relogin gera novo CSRF e apenas um POST reconstruído com token novo retorna 302. Depois adaptar o cliente para reconstruir página, corpo e headers antes do retry, evitando retry genérico de mutações com CSRF estático.

### Domain details

#### Expected assertions

- O login ocorre novamente exatamente uma vez.
- O segundo POST contém o novo token no corpo e nos headers.
- A consulta retorna o `dossie_id` e não reutiliza cookie/token antigo.
- Falha persistente termina após limite explícito, sem loop.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - O token local e o retry genérico foram verificados no mesmo caminho.
  - A suite possui infraestrutura MockTransport adequada para reproduzir a sequência.
- **Weaknesses:**
  - O portal pode aceitar token mascarado anterior em algumas condições, mas a troca de sessão invalida a suposição segura.
- **Suggested checks:**
  - Confirmar a política CSRF real do portal RSD em homologação sem executar consulta paga.

## imp-20260807-004 — Fazer o teste de conexão validar permissões operacionais

- **Impact:** High
- **Category:** Untested critical paths
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** testing, rsd, authentication, authorization, capability-check
- **Files affected:** `components/xtreme_system/rsd/core.py`, `tests/test_rsd.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
- **Related opportunities:** imp-20260807-001

### Location

`components/xtreme_system/rsd/core.py:660` — `RsdClient.testar_conexao`

```python
        if not csrf:
            raise RsdAuthError("CSRF token ausente após login.")
        return {
            "X-CSRFToken": csrf,
            "Origin": self.base_url,
            "Referer": self._url(referer_path),
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def testar_conexao(self) -> None:
        self.login()
```

### Description

`testar_conexao` considera sucesso assim que o login cria sessão. Não verifica se a conta consegue abrir as páginas/recursos usados por “Puxar dados” e “Consulta unitária”. Os testes reproduzem a mesma definição estreita e não cobrem conta autenticada sem assinatura/permissão.

### Why it matters

Autenticação válida não implica autorização para as capacidades vendidas pelo portal. A tela pode aprovar credenciais que falham na primeira operação real, reduzindo o valor do teste e do estado “conectado”.

### Concrete fix

Definir uma checagem não faturável que, depois do login, abra os endpoints necessários e valide os marcadores esperados/permissões sem iniciar dossiê. Testar separadamente credencial inválida, sessão válida sem permissão, mudança de HTML do portal e disponibilidade parcial.

### Domain details

#### Test matrix

- Login inválido → erro de autenticação.
- Login válido + acesso às duas capacidades → sucesso.
- Login válido + uma capacidade proibida → estado degradado com ação recomendada.
- Login válido + página inesperada → erro de compatibilidade, não “conectado”.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** Yes
- **Strengths:**
  - A implementação prova que o teste chama apenas `login`.
- **Weaknesses:**
  - É necessário confirmar quais páginas do portal podem ser consultadas sem custo ou efeito colateral.
- **Suggested checks:**
  - Alinhar com o contrato RSD uma rota de health/capabilities ou uma navegação segura.

## imp-20260807-005 — Adicionar testes negativos de autorização nas rotas de credenciais

- **Impact:** Medium
- **Category:** Missing negative and edge-case coverage
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** high
- **Tags:** testing, security, authorization, rsd, admin
- **Files affected:** `tests/test_rsd.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
- **Related opportunities:** imp-20260807-001

### Location

`tests/test_rsd.py:744` — fixture das rotas RSD

```python
@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(usuarios=[("admin", usuario.Papel.admin)])


def _login_ui(client: TestClient) -> None:
    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)
```

### Description

Todos os testes de `/ui/configuracoes/rsd` usam somente a fixture admin. Há teste 403 para o histórico RSD, mas nenhum garante que usuário anônimo ou não administrador não possa salvar, testar ou futuramente revogar credenciais.

### Why it matters

Essas rotas manipulam segredo reutilizável e disparam autenticação externa. Uma regressão em `UIAdmin`, no registro de rotas ou nos prefixos autorizados poderia passar pela suite sem testar o caso proibido.

### Concrete fix

Parametrizar as rotas salvar/testar/remover com clientes sem cookie, funcionário e admin. Afirmar redirect de login para anônimo, 403 para não admin, sucesso para admin e, nos casos bloqueados, ausência de alteração no banco e ausência de chamada ao cliente RSD.

### Domain details

#### Test matrix

- Anônimo × salvar/testar/remover.
- Funcionário × salvar/testar/remover.
- Admin × salvar/testar/remover.
- Verificação de que caminhos proibidos não produzem side effects.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - As ocorrências exatas das rotas na suite foram verificadas e só usam admin.
- **Weaknesses:**
  - A dependência compartilhada `UIAdmin` tem cobertura indireta em outras áreas, mas não nestes endpoints sensíveis.
- **Suggested checks:**
  - Reutilizar a fábrica de usuários/perfis já adotada em `tests/test_ui.py`.

## imp-20260807-006 — Exercitar concorrência entre uso e invalidação do cliente cacheado

- **Impact:** Medium
- **Category:** Missing negative and edge-case coverage
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** testing, concurrency, cache, rsd, session
- **Files affected:** `tests/test_rsd.py`, `components/xtreme_system/rsd/core.py`
- **Related opportunities:** None

### Location

`tests/test_rsd.py:707` — `test_client_from_config_reaproveita_client_entre_chamadas`

```python
def test_client_from_config_reaproveita_client_entre_chamadas(
    db_session: Session,
) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )

    primeiro = rsd.client_from_config(config)
    segundo = rsd.client_from_config(config)

    assert primeiro is segundo
```

### Description

A cobertura do novo cache é sequencial: prova identidade e fechamento depois de invalidar, mas não executa duas consultas simultâneas nem salva configuração enquanto um client está em uso. `invalidar_client_cache` pode fechar o objeto compartilhado após outro handler tê-lo obtido.

### Why it matters

Rotas FastAPI síncronas podem executar em threads diferentes. Corridas entre login, cookies, CSRF e fechamento podem aparecer apenas sob carga e produzir falhas de autenticação difíceis de reproduzir.

### Concrete fix

Usar barreiras/eventos e `ThreadPoolExecutor` para testar: criação simultânea retorna uma única instância válida; duas renovações não misturam estado; atualização de configuração espera/libera uso ativo com segurança; cliente antigo fecha apenas depois da requisição em voo; nenhuma entrada antiga vaza no cache.

### Domain details

#### Expected assertions

- Nenhuma thread usa `httpx.Client` já fechado.
- Um único login/renovação acontece por sessão expirada.
- O cliente novo usa somente a nova versão das credenciais.
- O cache fica vazio/limitado após repetidas trocas de configuração.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** Yes
- **Strengths:**
  - O cache global e os testes apenas sequenciais foram verificados.
- **Weaknesses:**
  - `httpx.Client` suporta uso concorrente, então o risco principal está nas sequências mutáveis de login/CSRF/close, não no transporte isoladamente.
- **Suggested checks:**
  - Executar o teste repetidamente e sob TSAN não é aplicável a Python puro; preferir sincronização determinística por eventos.

## imp-20260807-007 — Corrigir o teste que normaliza ciphertext inválido como senha

- **Impact:** Medium
- **Category:** Assertion quality
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** medium
- **Tags:** testing, encryption, fail-closed, rsd
- **Files affected:** `tests/test_rsd.py`, `components/xtreme_system/rsd/core.py`
- **Related opportunities:** None

### Location

`tests/test_rsd.py:650` — `test_decriptar_senha_avisa_quando_ciphertext_nao_decripta`

```python
    )
    # Tem cara de token Fernet (prefixo gAAAAA) mas não decripta com a
    # chave atual — deve ser tratado como chave rotacionada, não senha
    # legada em texto plano.
    valor = "gAAAAA-token-invalido-para-a-chave-atual"

    resultado = rsd._decriptar_senha(valor)  # noqa: SLF001

    assert resultado == valor
    assert any(
        a["event"] == "rsd_decriptar_senha_falhou_chave_invalida" for a in avisos
```

### Description

O teste reconhece corretamente que o valor representa chave rotacionada/errada, mas afirma que a função deve devolver esse mesmo token como senha. Assim, a suite cristaliza o comportamento inseguro em vez de exigir falha fechada e nenhuma chamada externa.

### Why it matters

Uma regressão de segurança pode parecer intencional porque está coberta por teste. O contrato correto deve proteger o limite do segredo, não apenas verificar que houve um log.

### Concrete fix

Substituir a expectativa por exceção específica, afirmar que a mensagem não contém o token e adicionar um teste de nível de rota/client factory garantindo que `RsdClient`/transporte nunca é criado quando a decriptação falha. Manter um teste separado e temporário para migração de texto plano legado.

### Domain details

#### Expected assertions

- Ciphertext inválido lança erro de configuração seguro.
- O token não aparece em resposta nem log.
- Nenhuma requisição HTTP ocorre.
- Texto plano legado é tratado somente no caminho de migração acordado.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - O comentário do teste já identifica a causa e contradiz diretamente a expectativa de retorno.
- **Weaknesses:**
  - A alteração depende da decisão de remover o fallback de runtime para instalações legadas.
- **Suggested checks:**
  - Inventariar compatibilidade de dados antes de mudar o contrato.

## Discarded candidates

### Aumentar testes do mapeamento simples de campos de veículo

Descartado por impacto baixo para o escopo de autenticação/configuração e porque já existem testes unitários e E2E dos principais campos.

### Executar E2E contra o portal RSD real na CI

Descartado por risco de flakiness, exposição de credenciais e possíveis efeitos/custos externos. O contrato deve ser simulado; smoke tests reais pertencem a um ambiente controlado separado.
