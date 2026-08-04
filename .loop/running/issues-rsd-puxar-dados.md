# Improvement opportunities

- **Generated:** 2026-08-04T12:51:23-03:00
- **Total:** 11
- **Status atual:** 7 concluídas, 4 pendentes
- **Última atualização:** 2026-08-04

## Status das tasks

- **Concluídas:** imp-20260804-001, imp-20260804-002, imp-20260804-003, imp-20260804-004, imp-20260804-008, imp-20260804-009 e imp-20260804-010.
- **Pendentes:** imp-20260804-005, imp-20260804-006, imp-20260804-007 e imp-20260804-011.
- **Validação:** 159 testes passaram e o Ruff passou nos arquivos Python alterados.

## imp-20260804-001 — Marca fica duplicada dentro de `modelo` ao puxar dados do RSD

- **Impact:** High
- **Category:** Code quality
- **Estimated effort:** Low
- **Priority:** high
- **Status:** concluída
- **Risk level:** low
- **Tags:** rsd, integracao, veiculo, dados-incorretos
- **Files affected:** `components/xtreme_system/rsd/core.py`, `tests/test_rsd.py`
- **Related opportunities:** imp-20260804-003, imp-20260804-007

### Location

`components/xtreme_system/rsd/core.py:391` — `mapear_para_veiculo`

```python
def mapear_para_veiculo(dados: PuxarDadosResult) -> dict[str, Any]:
    """Campos do formulário de veículo a partir do JSON puxar-dados."""
    out: dict[str, Any] = {}
    if dados.marca_modelo:
        out["modelo"] = dados.marca_modelo
        marca, _, _resto = dados.marca_modelo.partition("/")
        if marca.strip():
            out["marca"] = marca.strip()
    if dados.ano is not None:
        out["ano"] = dados.ano
    if dados.cor:
        out["cor"] = dados.cor
```

### Description

O portal devolve `marca_modelo` no formato `"CHEV/ONIX 10MT LT2"`. O código atribui a string
inteira a `modelo` e, em seguida, extrai a marca do mesmo valor. O `_resto` do `partition("/")` —
que é o modelo real — é calculado e descartado. O resultado gravado no veículo é
`marca="CHEV"` e `modelo="CHEV/ONIX 10MT LT2"`.

O teste `tests/test_rsd.py:177-185` afirma exatamente esse comportamento, então a divergência está
congelada por teste e não aparece como falha na suíte.

### Why it matters

Todo veículo cadastrado via RSD nasce com a marca repetida dentro do modelo. Isso contamina
listagem, busca por modelo, contratos gerados e qualquer agrupamento por modelo, e obriga correção
manual justamente no fluxo que existe para evitar digitação.

### Concrete fix

Atribuir o lado direito do `partition` a `modelo` quando houver `/`, mantendo a string completa
como fallback quando não houver separador. Atualizar a asserção correspondente em `tests/test_rsd.py`.

### Example

```python
def mapear_para_veiculo(dados: PuxarDadosResult) -> dict[str, Any]:
    """Campos do formulário de veículo a partir do JSON puxar-dados."""
    out: dict[str, Any] = {}
    if dados.marca_modelo:
        marca, sep, resto = dados.marca_modelo.partition("/")
        # "CHEV/ONIX 10MT LT2" -> marca="CHEV", modelo="ONIX 10MT LT2"
        if sep and resto.strip():
            out["modelo"] = resto.strip()
        else:
            out["modelo"] = dados.marca_modelo
        if sep and marca.strip():
            out["marca"] = marca.strip()
```

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Formato `MARCA/MODELO` confirmado pelo fixture do mock em `tests/test_rsd.py:88`.
  - `_resto` explicitamente descartado no código atual.
- **Weaknesses:**
  - Não foi verificado se algum modelo real do portal vem sem `/`; o fallback cobre o caso.
- **Suggested checks:**
  - Coletar alguns retornos reais de `/atpv/puxar-dados/` para confirmar o formato em placas antigas.

## imp-20260804-002 — Sessão expirada em `puxar_dados` vira erro "resposta não-JSON" em vez de relogin

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Status:** concluída
- **Risk level:** low
- **Tags:** rsd, integracao, sessao, erro-confuso
- **Files affected:** `components/xtreme_system/rsd/core.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/rsd/core.py:264` — `RsdClient.puxar_dados`

```python
        headers = self._csrf_headers("/atpv/nova/")
        resp = self._http().post(
            self._url(_PUXAR_DADOS_PATH),
            data={"placa": placa_norm},
            headers=headers,
        )
        if resp.status_code in (401, 403):
            # Sessão expirou — reloga uma vez
            self.login()
```

### Description

O retry de sessão só cobre 401/403. O cliente roda com `follow_redirects=False`
(`components/xtreme_system/rsd/core.py:176`), e a resposta típica do Django para sessão expirada é
**302 para `/accounts/login/`** — que não é `>= 400` nem 401/403. O fluxo segue para `resp.json()`,
falha, e o usuário recebe *"Resposta inválida do RSD (não-JSON)."*

`consultar_unitaria_be` trata o caso análogo corretamente em
`components/xtreme_system/rsd/core.py:303-305`, detectando o HTML de login e relogando; `puxar_dados`
não tem esse tratamento.

### Why it matters

É o modo de falha mais provável no uso diário: basta o portal expirar a sessão entre um uso e
outro. O usuário recebe uma mensagem que não indica ação nenhuma, e o suporte não tem como
distinguir sessão expirada de portal fora do ar.

### Concrete fix

Incluir os códigos de redirect na condição de relogin, ou detectar HTML de login no corpo antes de
tentar o parse — alinhando com o tratamento já existente em `consultar_unitaria_be`.

### Example

```python
_SESSAO_EXPIRADA = (301, 302, 303, 401, 403)

resp = self._http().post(
    self._url(_PUXAR_DADOS_PATH),
    data={"placa": placa_norm},
    headers=headers,
)
if resp.status_code in _SESSAO_EXPIRADA:
    # Sessão expirou — o portal redireciona para /accounts/login/
    self.login()
    resp = self._retry_puxar(placa_norm)
```

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - `follow_redirects=False` confirmado em `rsd/core.py:176`.
  - O tratamento correto existe no método irmão, o que confirma o padrão esperado do portal.
- **Weaknesses:**
  - Não confirmado empiricamente que `/atpv/puxar-dados/` responde 302 (e não 403) para sessão
    expirada — a rota pode ser AJAX-aware. O fix cobre ambos os casos.
- **Suggested checks:**
  - Adicionar caso no `MockTransport` de `tests/test_rsd.py` devolvendo 302 para login e afirmar
    que o relogin acontece.

## imp-20260804-003 — "Puxar dados" sobrescreve sem aviso campos já preenchidos pelo usuário

- **Impact:** High
- **Category:** Code quality
- **Estimated effort:** Medium
- **Priority:** high
- **Status:** concluída
- **Risk level:** medium
- **Tags:** rsd, ux, perda-de-dados
- **Files affected:** `bases/xtreme_system/api/templates/_rsd_status.html`
- **Related opportunities:** imp-20260804-001, imp-20260804-008

### Location

`bases/xtreme_system/api/templates/_rsd_status.html:21` — script de preenchimento

```html
(function () {
  var campos = {{ campos | tojson }};
  var root = document.getElementById("modal") || document;
  var form = root.querySelector("form");
  if (!form) return;
  Object.keys(campos).forEach(function (name) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el || campos[name] == null || campos[name] === "") return;
    el.value = campos[name];
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
```

### Description

O script escreve em todo campo cujo `name` bate com uma chave retornada, sem verificar se o campo
já tinha conteúdo e sem oferecer confirmação ou diff. Quem já digitou modelo, cor ou chassi perde o
que digitou ao clicar em "Puxar dados".

Combinado com imp-20260804-001, o efeito é pior: um `modelo` correto digitado à mão é substituído
pelo valor com a marca duplicada.

### Why it matters

O botão é apresentado como auxílio de preenchimento, mas se comporta como sobrescrita destrutiva.
Como não há undo no modal, o único caminho é redigitar — e o usuário pode nem perceber que um campo
fora do viewport mudou.

### Concrete fix

Preencher apenas campos vazios por padrão e sinalizar visualmente os que foram preenchidos pelo
RSD. Para campos já preenchidos com valor divergente, marcar o campo e deixar a substituição
explícita ao usuário, em vez de aplicar direto.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Comportamento lido diretamente do template; não há guarda de valor prévio.
- **Weaknesses:**
  - Pode existir intenção deliberada de "RSD é a fonte da verdade"; nesse caso o problema se reduz
    a sinalizar o que mudou.
- **Suggested checks:**
  - Confirmar com o usuário do sistema qual comportamento é esperado quando os valores divergem.

## imp-20260804-004 — Botão "Puxar dados" do wizard de compra é inerte; consignação não tem o botão

- **Impact:** High
- **Category:** Code quality
- **Estimated effort:** Medium
- **Priority:** high
- **Status:** concluída
- **Risk level:** medium
- **Tags:** rsd, ux, wizard, botao-morto
- **Files affected:** `bases/xtreme_system/api/templates/_form_compra.html`, `bases/xtreme_system/api/templates/_form_consignacao.html`, `components/xtreme_system/rsd/core.py`
- **Related opportunities:** imp-20260804-009

### Location

`bases/xtreme_system/api/templates/_form_compra.html:151` — botões do passo 2 do wizard

```html
        <fieldset class="wizard-step form-grid{% if dados.get('wizard_step', 1)|int == 2 %} is-active{% endif %}" data-step="2" :class="{ 'is-active': step === 2 }">
          {% if pode_ver_campo(user, 'compras', 'veiculo') %}
          <label class="field field--full">
            <span class="field__label">Placa *</span>
            <input class="input" name="vei_placa" data-testid="compra-wizard-vehicle-plate" data-novo-veiculo value="{{ dados.get('vei_placa', '') }}" required style="text-transform:uppercase">
          </label>
          <div class="field field--full" style="display:flex;gap:var(--s-2);flex-wrap:wrap">
            <button type="button" class="btn btn--ghost btn--sm">📝 Cadastrar manualmente</button>
            <button type="button" class="btn btn--ghost btn--sm">🔄 Puxar dados</button>
          </div>
```

### Description

Os dois botões do wizard de compra não têm `hx-post`, `id`, `x-on:` nem qualquer handler — a busca
por `"Puxar dados"` e `"Cadastrar manualmente"` em `static/*.js` e nos templates não encontra
nenhum binding. Clicar não faz nada.

O wizard de consignação (`_form_consignacao.html:158`) cria veículo inline pelo mesmo caminho e não
tem sequer o botão. Nos dois casos os campos são prefixados (`vei_placa`, `vei_modelo`), enquanto
`mapear_para_veiculo` devolve chaves sem prefixo — então reaproveitar a rota exige prefixar as
chaves ou parametrizar o prefixo.

### Why it matters

Compra e consignação são os momentos em que o veículo é cadastrado do zero — exatamente onde puxar
dados economiza mais digitação. Um botão visível que não responde é pior do que ausência: o usuário
tenta, conclui que a integração está quebrada, e digita tudo à mão.

### Concrete fix

Extrair o bloco RSD funcional de `_form_veiculo.html` para uma macro que aceite o prefixo dos
campos, ligar os botões da compra a ela, e adicionar o mesmo bloco ao wizard de consignação. Fazer
`mapear_para_veiculo` (ou a rota) aplicar o prefixo recebido. Se a decisão for não suportar RSD nos
wizards, remover os botões inertes.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Ausência de handler confirmada por busca em todos os `static/*.js` e templates.
- **Weaknesses:**
  - Não verifiquei se algum teste de UI clica nesses botões esperando no-op.
- **Suggested checks:**
  - Confirmar se os botões são placeholder de trabalho em andamento ou resquício de refactor.

## imp-20260804-005 — CPF/CNPJ e UF do proprietário são puxados do RSD e descartados

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** medium
- **Status:** pendente
- **Risk level:** medium
- **Tags:** rsd, modelagem, proprietario, contrato
- **Files affected:** `components/xtreme_system/rsd/core.py`, `components/xtreme_system/veiculo/core.py`
- **Related opportunities:** imp-20260804-007

### Location

`components/xtreme_system/rsd/core.py:76` — `PuxarDadosResult`

```python
class PuxarDadosResult(BaseModel):
    placa: str = ""
    renavam: str | None = None
    chassi: str | None = None
    marca_modelo: str | None = None
    ano: int | None = None
    cor: str | None = None
    nome_proprietario: str | None = None
    cpf_cnpj: str | None = None
    tipo_documento: str | None = None
    uf: str | None = None
    outro_estado: bool = False
```

### Description

O portal devolve `cpf_cnpj`, `tipo_documento`, `uf` e `origem`, e `mapear_para_veiculo`
(`rsd/core.py:391-411`) não mapeia nenhum deles. O modelo `Veiculo`
(`components/xtreme_system/veiculo/core.py:105`) guarda apenas `proprietario_registrado` como string
livre, sem documento associado.

### Why it matters

O CPF/CNPJ é o dado que amarra o veículo ao proprietário de forma inequívoca e é o que aparece nos
documentos de transferência e contrato. Hoje ele chega do portal, é validado pelo Pydantic e é
jogado fora — quem precisa do documento consulta o portal de novo, manualmente.

### Concrete fix

Decidir a modelagem antes de mapear: adicionar `proprietario_documento` (e possivelmente
`proprietario_uf`) a `Veiculo` com a migration correspondente, e então incluir os campos em
`mapear_para_veiculo` e no formulário. É mudança de schema, não só de mapeamento.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Ausência das colunas confirmada na definição de `Veiculo`.
  - Campos presentes no fixture do mock em `tests/test_rsd.py:92-93`.
- **Weaknesses:**
  - Não avaliei se o documento do proprietário já é capturado em outra entidade (cliente/compra),
    o que mudaria onde persistir.
- **Suggested checks:**
  - Verificar se `Compra` ou `Cliente` já carrega o documento do vendedor antes de criar coluna nova.

## imp-20260804-006 — Consulta unitária faz poll síncrono de até 120 s ocupando worker do threadpool

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** High
- **Priority:** medium
- **Status:** pendente
- **Risk level:** medium
- **Tags:** rsd, performance, threadpool, timeout
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/rsd.py`, `bases/xtreme_system/api/templates/_form_veiculo.html`
- **Related opportunities:** imp-20260804-007

### Location

`components/xtreme_system/rsd/core.py:344` — `RsdClient._poll_status`

```python
    def _poll_status(self, dossie_id: int, *, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        status_url = self._url(f"/dossie/{dossie_id}/status/")
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            resp = self._http().get(status_url, headers={"Accept": "application/json"})
            if resp.status_code >= 400:
                raise RsdConsultaError(
                    _msg_http(resp, f"Falha ao consultar status do dossiê {dossie_id}.")
                )
            try:
                last = resp.json()
```

### Description

`_POLL_TIMEOUT_S = 120.0` (`rsd/core.py:35`) e o cliente espera com `time.sleep` a cada 2 s. A rota
`ui_rsd_consulta_unitaria` é síncrona (`def`), então roda no threadpool do Starlette — cada consulta
prende um worker por até dois minutos. O front reforça isso com `hx-timeout="130000"`
(`_form_veiculo.html:65`).

Vale apenas para a consulta unitária; o "puxar dados" é uma requisição única e não tem esse perfil.

### Why it matters

Com o threadpool padrão (40 threads), algumas consultas simultâneas degradam o app inteiro,
incluindo telas que não têm relação com RSD. Não há cancelamento: fechar o modal não interrompe o
poll no servidor.

### Concrete fix

Tirar o poll do ciclo da requisição: iniciar a consulta, devolver o `dossie_id` imediatamente e
deixar o cliente consultar o status via `hx-trigger="every 3s"` numa rota leve que faz uma única
chamada de status. Isso também elimina o timeout de 130 s no front.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Rota síncrona e `time.sleep` confirmados no código.
- **Weaknesses:**
  - O volume real de consultas simultâneas nesta loja pode ser baixo o bastante para o risco ser
    teórico; o custo do refactor é alto.
- **Suggested checks:**
  - Medir quantas consultas unitárias por hora acontecem em pico antes de priorizar.

## imp-20260804-007 — Criar tabela `rsd_consulta` para persistir todos os dados puxados do portal

- **Impact:** High
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** high
- **Status:** pendente
- **Risk level:** medium
- **Tags:** rsd, auditoria, persistencia, custo, schema
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/rsd.py`, `alembic/versions/`
- **Related opportunities:** imp-20260804-001, imp-20260804-005, imp-20260804-006

### Location

`bases/xtreme_system/api/routes/ui_routes/rsd.py:69` — `ui_rsd_consulta_unitaria`

```python
@router.post("/ui/rsd/consulta-unitaria")
def ui_rsd_consulta_unitaria(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
) -> HTMLResponse:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(request, erro=str(exc), status_code=400)
```

### Description

Nenhuma das rotas grava o que foi consultado. `auditar` é chamado apenas para mudanças de
configuração (`components/xtreme_system/rsd/core.py:127`), nunca para consultas. O JSON completo que
o portal devolve é convertido em `PuxarDadosResult`, reduzido a um punhado de campos por
`mapear_para_veiculo` e descartado ao fim da requisição; o `dossie_id` da consulta unitária só existe
no HTML da resposta.

Se o navegador desistir antes do fim do poll, o dossiê existe e foi cobrado no portal, mas o sistema
perdeu a referência — não há como baixar o PDF sem voltar ao portal manualmente. Consultar a mesma
placa duas vezes gera duas chamadas.

### Why it matters

Consulta unitária tem custo por uso no portal. Sem registro não há como saber quem consultou o quê,
nem reaproveitar um dossiê recente, nem recuperar um PDF de uma consulta que já foi paga. E como o
payload bruto não é guardado, todo dado que o mapeamento hoje ignora (imp-20260804-005) ou mapeia
errado (imp-20260804-001) só pode ser recuperado com uma nova chamada ao portal.

### Concrete fix

Criar a tabela `rsd_consulta` gravando cada chamada ao portal com o payload bruto íntegro, e passar
a escrever nela nas duas rotas de consulta. O plano completo está em `Domain details`.

### Potential savings

Elimina consultas repetidas da mesma placa dentro da janela de validade do dossiê, que hoje são
sempre novas chamadas pagas ao portal. Com o payload bruto guardado, corrigir o mapeamento passa a
ser reprocessamento local em vez de reconsulta paga de todo o estoque.

### Domain details

#### Modelo proposto — `components/xtreme_system/rsd/core.py`

```python
class RsdConsulta(Base):
    __tablename__ = "rsd_consulta"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoConsultaRsd]
    placa: Mapped[str] = mapped_column(index=True)
    veiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id", ondelete="SET NULL"), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
```

#### Colunas restantes

- `tipo` — enum `TipoConsultaRsd` com `puxar_dados` e `unitaria`, mesmo padrão de `TipoVeiculo`
  em `components/xtreme_system/veiculo/core.py`
- `payload: JSON` — resposta bruta e íntegra do portal, sem filtragem. É o núcleo desta
  oportunidade: guardar tudo que foi puxado, não só o que o formulário usa hoje
- `campos_aplicados: JSON | None` — o dicionário devolvido por `mapear_para_veiculo`, para
  distinguir o que o portal mandou do que o sistema aproveitou
- `sucesso: bool` e `erro: str | None` — consultas que falharam também viram linha; hoje o erro
  só existe no HTML devolvido
- `dossie_id: int | None` e `status_dossie: str | None` — preenchidos apenas na consulta unitária
- `duracao_ms: int | None` — mede o custo real do poll e sustenta a decisão de imp-20260804-006
- `criado_em: Mapped[datetime]` com `DateTime` e `server_default=func.now()`, como em
  `components/xtreme_system/custo_veiculo/core.py:31`
- índice composto `(placa, criado_em)` para o lookup "última consulta desta placa"
- `veiculo_id` é nullable por necessidade: nos wizards de compra e consignação o veículo ainda não
  existe quando a consulta acontece

#### Pontos de escrita

- `bases/xtreme_system/api/routes/ui_routes/rsd.py:52` — após `client.puxar_dados(placa)`, tanto no
  caminho de sucesso quanto no `except rsd.RsdError`
- `bases/xtreme_system/api/routes/ui_routes/rsd.py:85` — idem para `consultar_unitaria_be`
- uma função `registrar_consulta(...)` em `components/xtreme_system/rsd/core.py`, chamada pelas duas
  rotas, mantém a rota fina e o teste concentrado no componente

#### Obstáculo de transação (decidir antes de implementar)

As duas rotas chamam `detach_request_session(request, keep=(user, config))`
(`bases/xtreme_system/api/routes/ui_routes/rsd.py:49` e `:82`) **antes** da chamada externa. Quando o
resultado do portal chega, a sessão do request já sofreu rollback e close, e `finish_request_session`
a ignora — não há sessão viva para gravar, e `safe_write` não se aplica.

Duas saídas, com custos diferentes:

1. Abrir sessão própria para o registro: `SessionLocal()` (`components/xtreme_system/database/core.py:82-85`)
   com `commit()` e `close()` explícitos, fora do `get_session` (`:182-200`) que centraliza
   rollback/commit. Funciona hoje, ao custo de um ponto de transação manual fora da convenção
   descrita em `docs/agents/transactions-rollbacks.md`.
2. Resolver imp-20260804-006 primeiro. Com o poll fora do ciclo da requisição, o `detach` deixa de
   ser necessário e o registro cabe na sessão normal do request, sem exceção à convenção.

A opção 2 é a ordem correta se as duas forem feitas; a opção 1 é a saída se esta tabela for entregue
isolada. O "puxar dados" (chamada única, rápida) pode dispensar o `detach` de imediato e usar a
sessão do request — a restrição real é só da consulta unitária.

#### Migration

- nova revision com `down_revision = "a1b2c3d4e5f6"`, head atual confirmado por `alembic heads`
- `op.create_table("rsd_consulta", ...)` no estilo de
  `alembic/versions/f9a0b1c2d3e4_add_rsd_config_table.py`
- FKs com `ondelete="SET NULL"`: apagar veículo ou usuário não pode apagar histórico de consulta paga
- `downgrade()` com `op.drop_table("rsd_consulta")`

#### Critérios de aceite

- toda chamada ao portal — sucesso ou falha — gera exatamente uma linha em `rsd_consulta`
- o `payload` gravado é o JSON íntegro devolvido pelo portal, sem campos removidos
- falha ao gravar o registro não derruba a resposta ao usuário: loga e segue
- nenhuma credencial (`email`, `senha` de `RsdConfig`) aparece no payload gravado
- testes: sucesso grava linha com `sucesso=True` e payload completo; erro do portal grava linha com
  `sucesso=False` e `erro` preenchido; ambos usando o `MockTransport` já existente em
  `tests/test_rsd.py`

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Ausência de `auditar` nas rotas de consulta confirmada por leitura completa de `rsd.py`.
  - Head do Alembic (`a1b2c3d4e5f6`) confirmado por `alembic heads`; padrão de coluna `JSON` já em
    uso em `components/xtreme_system/auditoria/core.py:39-40`.
  - Conflito com `detach_request_session` verificado no código das rotas e em
    `components/xtreme_system/database/core.py:134-154`.
- **Weaknesses:**
  - Não confirmei o modelo de cobrança do RSD nem a validade de um dossiê; a economia depende disso.
  - Não avaliei o volume de linhas ao longo do tempo nem política de retenção do payload bruto.
- **Suggested checks:**
  - Confirmar com o portal por quanto tempo um dossiê permanece válido para reemissão de PDF.

## imp-20260804-008 — Preenchimento escolhe o primeiro `<form>` do modal, sem vínculo com o botão clicado

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Status:** concluída
- **Risk level:** medium
- **Tags:** rsd, frontend, acoplamento
- **Files affected:** `bases/xtreme_system/api/templates/_rsd_status.html`
- **Related opportunities:** imp-20260804-003

### Location

`bases/xtreme_system/api/templates/_rsd_status.html:23` — resolução do form alvo

```html
  var root = document.getElementById("modal") || document;
  var form = root.querySelector("form");
  if (!form) return;
  Object.keys(campos).forEach(function (name) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el || campos[name] == null || campos[name] === "") return;
    el.value = campos[name];
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
})();
```

### Description

O script assume que o primeiro `<form>` dentro de `#modal` é o form que originou a requisição. Nada
liga o resultado ao botão clicado. Funciona hoje porque cada modal tem exatamente um form, mas
qualquer form aninhado, secundário ou fora de `#modal` quebra o preenchimento silenciosamente — sem
erro, apenas campos que não são preenchidos.

### Why it matters

É a peça que faz a feature funcionar, e ela depende de uma suposição estrutural não declarada em
lugar nenhum. A falha é silenciosa, o que a torna cara de diagnosticar.

### Concrete fix

Passar o form alvo explicitamente — por exemplo com `hx-target` apontando para um contêiner dentro
do próprio form e resolvendo via `closest("form")` a partir dele, em vez de `querySelector` no
modal inteiro.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Comportamento lido diretamente do template.
- **Weaknesses:**
  - Nenhum caso de falha real observado hoje; é risco estrutural, não bug ativo.
- **Suggested checks:**
  - Verificar se algum modal do sistema já renderiza mais de um form.

## imp-20260804-009 — Bloco de ações RSD duplicado nas duas variantes do formulário de veículo

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Status:** concluída
- **Risk level:** low
- **Tags:** rsd, template, duplicacao
- **Files affected:** `bases/xtreme_system/api/templates/_form_veiculo.html`, `bases/xtreme_system/api/templates/_macros.html`
- **Related opportunities:** imp-20260804-004, imp-20260804-010

### Location

`bases/xtreme_system/api/templates/_form_veiculo.html:53` — bloco RSD (variante de edição)

```html
          <div class="field field--full rsd-actions">
            <span class="field__label">RSD</span>
            <div style="display:flex;gap:var(--s-2);flex-wrap:wrap;align-items:center">
              <button type="button" class="btn btn--ghost btn--sm"
                      hx-post="/ui/rsd/puxar-dados" hx-include="[name='placa']"
                      hx-target="#rsd-status" hx-swap="outerHTML"
                      hx-indicator="#rsd-indicator">
                {{ ui.icon("refresh") }} Puxar dados
              </button>
              <button type="button" class="btn btn--ghost btn--sm"
                      hx-post="/ui/rsd/consulta-unitaria" hx-include="[name='placa']"
                      hx-target="#rsd-status" hx-swap="outerHTML"
```

### Description

O mesmo bloco de 18 linhas aparece em `_form_veiculo.html:53-71` (edição) e `:171-189` (wizard de
novo veículo), incluindo os ids `rsd-status` e `rsd-indicator`. As duas variantes são mutuamente
exclusivas via `{% if veiculo %}`, então não há colisão de id em runtime.

### Why it matters

Toda correção desta revisão que toque o bloco — o `hx-include` de imp-20260804-010, a extração para
compra e consignação de imp-20260804-004 — precisa ser aplicada duas vezes, com risco de divergência
entre as variantes.

### Concrete fix

Extrair uma macro em `_macros.html` recebendo o prefixo dos campos e um sufixo de id, e chamá-la nas
duas posições. Isso cria o ponto único de reuso de que imp-20260804-004 precisa.

### Domain details

#### Consolidation details

- **Duplicate type:** Template consolidation
- **All sites:** `bases/xtreme_system/api/templates/_form_veiculo.html:53-71`,
  `bases/xtreme_system/api/templates/_form_compra.html:150-153` (variante inerte, ver
  imp-20260804-004), `bases/xtreme_system/api/templates/_form_veiculo.html:171-189`
- **Differences between copies:** as duas cópias em `_form_veiculo.html` são literalmente idênticas,
  linha a linha, incluindo ids; a de `_form_compra.html` tem apenas os rótulos, sem atributos `hx-*`
- **Behavior preservation:** vence o comportamento de `_form_veiculo.html` (bloco funcional); a
  variante de compra ganha comportamento que hoje não tem, o que é a correção pretendida em
  imp-20260804-004
- **Verification plan:** renderizar os dois modos de `_form_veiculo.html` e comparar o HTML gerado
  antes e depois da extração; rodar os testes de UI existentes em `tests/test_ui.py` que abrem o
  modal de veículo

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Blocos comparados linha a linha nas duas posições.
- **Weaknesses:**
  - A macro precisa parametrizar os ids se algum dia as variantes coexistirem; hoje não coexistem.
- **Suggested checks:**
  - Confirmar que `_macros.html` já é importado em todos os templates que passariam a usar a macro.

## imp-20260804-010 — `hx-include="[name='placa']"` resolve contra o documento inteiro

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Status:** concluída
- **Risk level:** medium
- **Tags:** rsd, htmx, seletor-global
- **Files affected:** `bases/xtreme_system/api/templates/_form_veiculo.html`
- **Related opportunities:** imp-20260804-009

### Location

`bases/xtreme_system/api/templates/_form_veiculo.html:56` — atributos `hx-include` dos botões RSD

```html
              <button type="button" class="btn btn--ghost btn--sm"
                      hx-post="/ui/rsd/puxar-dados" hx-include="[name='placa']"
                      hx-target="#rsd-status" hx-swap="outerHTML"
                      hx-indicator="#rsd-indicator">
                {{ ui.icon("refresh") }} Puxar dados
              </button>
              <button type="button" class="btn btn--ghost btn--sm"
                      hx-post="/ui/rsd/consulta-unitaria" hx-include="[name='placa']"
                      hx-target="#rsd-status" hx-swap="outerHTML"
                      hx-timeout="130000" hx-indicator="#rsd-indicator">
                {{ ui.icon("search") }} Consulta unitária
              </button>
```

### Description

htmx resolve o seletor de `hx-include` contra o documento inteiro, não contra o form do botão. Hoje
não existe outro campo `name="placa"` fora do modal — a busca por `name="placa"` nos templates
retorna apenas as duas ocorrências dentro de `_form_veiculo.html`. Basta alguém adicionar um filtro
de placa na listagem de veículos para o POST passar a enviar dois valores de `placa`.

### Why it matters

A falha resultante seria silenciosa e enganosa: o FastAPI aceita o primeiro valor do form, então a
consulta passaria a usar a placa do filtro da listagem em vez da placa do modal, sem erro visível.

### Concrete fix

Trocar por um escopo explícito — `hx-include="closest form"` ou um id no input de placa — nas duas
ocorrências (ou na macro proposta em imp-20260804-009).

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Ausência atual de outros `name="placa"` confirmada por busca em todos os templates.
- **Weaknesses:**
  - É risco latente, não bug ativo; depende de uma mudança futura na listagem.
- **Suggested checks:**
  - Confirmar a precedência de valores duplicados no parsing de form do FastAPI para a rota.

## imp-20260804-011 — Senha do portal RSD armazenada em texto plano

- **Impact:** Medium
- **Category:** Security
- **Estimated effort:** Medium
- **Priority:** medium
- **Status:** pendente
- **Risk level:** medium
- **Tags:** rsd, security, credenciais
- **Files affected:** `components/xtreme_system/rsd/core.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/rsd/core.py:59` — `RsdConfig`

```python
class RsdConfig(Base):
    __tablename__ = "rsd_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(default="", server_default="")
    senha: Mapped[str] = mapped_column(default="", server_default="")
    base_url: Mapped[str] = mapped_column(
        default=_DEFAULT_BASE_URL, server_default=_DEFAULT_BASE_URL
    )


class RsdConfigUpdate(BaseModel):
    email: str = ""
    senha: str = ""
    base_url: str = _DEFAULT_BASE_URL
```

### Description

A coluna `senha` guarda a credencial do portal sem criptografia. As camadas adjacentes estão
corretas: a auditoria mascara o campo (`components/xtreme_system/auditoria/core.py:14-18` e `:54`) e a
UI usa `type="password"` com toggle (`bases/xtreme_system/api/templates/configuracoes.html:252`).
A exposição fica restrita a quem já tem acesso ao banco, a dumps e a backups.

É o mesmo padrão usado pela configuração do WhatsApp — decisão de projeto pré-existente, não uma
regressão introduzida por esta feature.

### Why it matters

A senha é reutilizável no portal externo, fora do controle do sistema: quem obtiver um backup do
banco consegue operar consultas pagas em nome da loja. Diferente de um hash de senha de usuário,
aqui a credencial precisa ser recuperável, então o único caminho é criptografia com chave fora do
banco.

### Concrete fix

Criptografar a coluna em repouso com chave derivada de variável de ambiente (a mesma abordagem
aplicável à config do WhatsApp), decifrando apenas em `client_from_config`. Requer migration com
recodificação dos valores existentes.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Mascaramento na auditoria verificado em `auditoria/core.py:14-18` e `:54`.
  - Ausência de criptografia confirmada na definição da coluna.
- **Weaknesses:**
  - Não avaliei quem tem acesso ao banco de produção nem como os backups são guardados; isso define
    se o risco é real ou aceito.
- **Suggested checks:**
  - Confirmar a política de acesso a dumps de produção antes de priorizar.

## Discarded candidates

### Respostas 4xx do RSD não seriam exibidas pelo htmx

As rotas devolvem `status_code=400` em erro e o htmx, por padrão, não faz swap de 4xx — o que
esconderia toda mensagem de erro. Descartado após verificar
`bases/xtreme_system/api/templates/base.html:7`, que sobrescreve `responseHandling` habilitando
`swap: true` para `[45]..`. O comportamento atual está correto.

### `detach_request_session` antes da chamada externa

Levantado como possível risco de sessão de banco presa durante I/O externo de longa duração.
Descartado: as três rotas em `bases/xtreme_system/api/routes/ui_routes/rsd.py:49`, `:82` e `:109`
já liberam a conexão antes da chamada, preservando `user` e `config` via `keep`. O padrão está
aplicado de forma consistente.
