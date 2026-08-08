# Improvement opportunities

- **Generated:** 2026-08-07T13:54:20-03:00
- **Total:** 6

## imp-20260807-001 — Exibir o estado real do ciclo de credenciais RSD

- **Impact:** High
- **Category:** Feedback and system state
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** rsd, credenciais, status, ux
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `alembic/versions/`
- **Related opportunities:** imp-20260807-002, imp-20260807-003

### Location

`bases/xtreme_system/api/templates/configuracoes.html:221` — painel de status do Portal RSD

```html
      <div class="connection-status {{ 'connection-status--ok' if rsd_ok else 'connection-status--pending' }}">
        <span class="connection-status__icon">{{ ui.icon("search") }}</span>
        <div class="connection-status__text">
          <strong>{{ "Integração conectada" if rsd_ok else "Integração não configurada" }}</strong>
          <span>
            {% if rsd_ok %}
              Conta <code>{{ config_rsd.email }}</code> pronta para consultas.
            {% else %}
              Informe e-mail e senha do portal lojas.rsdsistema.com.br.
            {% endif %}
          </span>
        </div>
```

### Description

O painel chama a integração de “conectada” e “pronta para consultas” sempre que e-mail e senha existem. Ele não sabe se as credenciais foram testadas, quando o último teste ocorreu, se a configuração mudou depois do teste ou se o último uso falhou por autenticação.

### Why it matters

O administrador recebe confiança falsa depois de apenas salvar valores. Credenciais incorretas, expiradas ou sem permissão no RSD continuam verdes até uma consulta operacional falhar, deslocando o diagnóstico para outra tela e outro momento.

### Concrete fix

Persistir um estado explícito da credencial (`saved_unverified`, `verified`, `failed`), data do último teste, erro sanitizado e uma impressão digital dos valores testados. Toda alteração de e-mail, senha ou URL deve invalidar a verificação anterior. A UI deve usar rótulos como “Credenciais salvas — teste pendente”, “Conexão verificada em …” e “Último teste falhou”.

### Domain details

#### Acceptance criteria

- Uma configuração apenas salva nunca aparece como conectada.
- Alterar qualquer credencial converte imediatamente o estado para “teste pendente”.
- O estado verificado inclui data/hora e corresponde exatamente à versão ativa das credenciais.
- Falhas de autenticação e de disponibilidade são diferenciadas sem expor detalhes internos.

#### Success metric

- Nenhum chamado operacional precisa descobrir credenciais inválidas somente ao iniciar uma consulta de veículo.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - O texto e a condição que produzem o falso estado positivo estão visíveis no template atual.
  - O modelo atual foi verificado e não possui metadados de teste ou validade.
- **Weaknesses:**
  - Não há telemetria de suporte para quantificar quantos erros hoje começam com esse falso positivo.
- **Suggested checks:**
  - Levantar falhas `RsdAuthError` ocorridas depois de a tela ter exibido “Conectado”.

## imp-20260807-002 — Preservar o rascunho e distinguir testar de salvar

- **Impact:** High
- **Category:** Error presentation
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** rsd, formulário, teste-de-conexão, feedback
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`, `tests/test_rsd.py`, `tests/e2e/`
- **Related opportunities:** imp-20260807-001, imp-20260807-004, imp-20260807-005

### Location

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:183` — `ui_configuracoes_rsd_teste`

```python
    return _pagina_empresa(
        request,
        session,
        user,
        config_empresa,
        config=config_wa,
        config_rsd=config_rsd,
        sucesso="Conexão com o portal RSD OK.",
        aba="rsd",
    )
```

### Description

O teste usa corretamente os valores recém-digitados, mas a resposta renderiza novamente `config_rsd`, que é a versão persistida anterior. Em sucesso ou erro, e-mail e URL do rascunho somem; no primeiro cadastro, a mesma página pode mostrar simultaneamente “Conexão OK” no alerta e “Integração não configurada” no painel. O teste aprovado também não deixa claro que nada foi salvo.

### Why it matters

O usuário precisa redigitar dados, pode salvar valores diferentes dos que realmente testou e pode sair da tela acreditando que a integração já está ativa. Esse é um ponto de hesitação e erro exatamente entre as duas ações centrais do fluxo.

### Concrete fix

Manter e-mail e URL submetidos em um objeto de rascunho separado do modelo persistido e atualizar apenas uma região de resultado do teste. Nunca devolver a senha no HTML. Após sucesso, mostrar “Teste aprovado para este rascunho; ainda não salvo” com uma ação primária “Salvar credenciais testadas”, ou oferecer uma única ação atômica “Testar e salvar”.

### Domain details

#### Acceptance criteria

- Sucesso e erro mantêm e-mail e URL digitados.
- A senha continua somente no estado do formulário do navegador e nunca volta na resposta.
- O texto informa inequivocamente se a configuração testada está ou não ativa.
- Salvar depois do teste aplica exatamente a versão que recebeu o resultado positivo.

#### Screens

- Configurações → Portal RSD → primeiro cadastro.
- Configurações → Portal RSD → troca de conta existente.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - A rota mostra explicitamente que testa valores do formulário e depois renderiza o modelo persistido.
  - O comportamento contraditório pode ser deduzido sem depender do portal externo.
- **Weaknesses:**
  - A interface não foi inspecionada manualmente porque a CLI interativa não encontrou a distribuição Chrome; a suite Playwright existente foi executada.
- **Suggested checks:**
  - Adicionar um E2E que teste e-mail novo com configuração vazia e compare os valores antes/depois da resposta.

## imp-20260807-003 — Oferecer revogação explícita das credenciais

- **Impact:** High
- **Category:** Form ergonomics
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** rsd, credenciais, revogação, ciclo-de-vida
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`, `tests/test_rsd.py`
- **Related opportunities:** imp-20260807-001

### Location

`components/xtreme_system/rsd/core.py:205` — `atualizar_config`

```python
def atualizar_config(
    session: Session, data: RsdConfigUpdate, actor_id: int | None = None
) -> RsdConfig:
    config = get_config(session)
    antes = snapshot(config)
    config.email = data.email.strip()
    if data.senha:
        config.senha = _encriptar_senha(data.senha)
    base = (data.base_url or _DEFAULT_BASE_URL).strip().rstrip("/")
    config.base_url = base or _DEFAULT_BASE_URL
```

### Description

Senha vazia significa sempre “manter a atual”. A tela não possui ação “Desconectar” ou “Remover credenciais”, então o administrador não consegue concluir o ciclo de desativação: pode apagar o e-mail, mas o segredo cifrado continua no banco.

### Why it matters

Troca de fornecedor, desligamento de uma loja, suspeita de comprometimento ou simples correção de configuração exigem revogar o acesso, não apenas esconder o estado conectado. Manter uma credencial sem uso aumenta risco e deixa o comportamento futuro ambíguo.

### Concrete fix

Criar uma ação explícita “Remover credenciais RSD”, separada do campo senha, com confirmação, auditoria, limpeza de e-mail e senha, restauração da URL padrão e invalidação do cliente em cache. Não atribuir semântica de remoção ao campo vazio, pois ele já significa “manter”.

### Domain details

#### Acceptance criteria

- A ação exige confirmação e informa que consultas RSD deixarão de funcionar.
- Após confirmar, nenhum segredo permanece em `rsd_config` nem no cache do processo.
- A auditoria registra o ator e mascara os valores sensíveis.
- A tela retorna ao estado “Não configurado”.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - O contrato de atualização confirma que uma string vazia não pode apagar a senha.
  - Nenhuma ação alternativa de remoção foi encontrada no template ou nas rotas RSD.
- **Weaknesses:**
  - Não foi verificado se existe um procedimento operacional externo para limpar a linha diretamente no banco.
- **Suggested checks:**
  - Confirmar com operações se hoje a revogação é feita por SQL manual.

## imp-20260807-004 — Mostrar progresso e bloquear testes duplicados

- **Impact:** Medium
- **Category:** Feedback and system state
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** rsd, loading, dupla-submissão, htmx
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260807-002

### Location

`bases/xtreme_system/api/templates/configuracoes.html:263` — ações do formulário RSD

```html
              <span class="field__label">URL base</span>
              <input class="input" name="base_url" placeholder="https://lojas.rsdsistema.com.br"
                     value="{{ config_rsd.base_url }}" autocomplete="off">
            </label>
          </div>
        </div>
        <div class="field settings-actions settings-actions--split">
          <button class="btn btn--default" type="submit" formaction="/ui/configuracoes/rsd/teste">
            {{ ui.icon("refresh") }} Testar conexão
          </button>
          <button class="btn btn--primary" type="submit">{{ ui.icon("check") }} Salvar</button>
        </div>
```

### Description

O teste é uma submissão de página inteira sem indicador local, texto de progresso, `aria-busy` ou desabilitação dos botões. O login externo pode consumir até dois timeouts HTTP, e novos cliques podem iniciar testes paralelos.

### Why it matters

Durante lentidão do portal, o usuário não sabe se a ação foi aceita e tende a clicar novamente. Isso aumenta carga, pode gerar tentativas repetidas contra a conta RSD e torna o fluxo de configuração pouco confiável.

### Concrete fix

Submeter o teste por HTMX para um bloco `aria-live`, usar `hx-disabled-elt` nos dois botões, exibir spinner e texto “Validando credenciais…”, e restaurar as ações no término. Informar que o teste pode levar alguns segundos e manter um único request ativo por formulário.

### Domain details

#### Acceptance criteria

- Um clique desabilita Testar e Salvar até a resposta.
- O estado de progresso é anunciado por leitor de tela.
- Cliques repetidos não disparam autenticações concorrentes.
- Erro e sucesso aparecem junto às ações sem reposicionar o usuário para o topo da página.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - O template atual não contém atributos ou elementos de progresso na ação.
  - Os timeouts do cliente externo foram verificados no código.
- **Weaknesses:**
  - O navegador exibe seu próprio indicador de navegação, embora ele não identifique a ação nem impeça novo clique.
- **Suggested checks:**
  - Simular respostas de 5, 15 e 30 segundos no E2E e observar tentativas repetidas.

## imp-20260807-005 — Aplicar Post/Redirect/Get ao salvar credenciais

- **Impact:** Medium
- **Category:** Consistency
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** rsd, prg, refresh, histórico-do-navegador
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`, `tests/test_rsd.py`
- **Related opportunities:** imp-20260807-002

### Location

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:115` — `ui_configuracoes_rsd_salvar`

```python
    return _pagina_empresa(
        request,
        session,
        user,
        empresa.get_config(session),
        config_rsd=config_rsd,
        sucesso="Configurações RSD salvas.",
        aba="rsd",
        limpar_senha_rsd=True,
    )
```

### Description

O POST de salvamento devolve a página final diretamente. Atualizar a página pode pedir reenvio do formulário e repetir a alteração/auditoria; navegar para trás depende de `Cache-Control: no-store` e de limpeza client-side do campo senha para evitar um snapshot antigo.

### Why it matters

Gerenciamento de credenciais deve ter resultado estável no histórico do navegador. Reenvio acidental, alertas de confirmação do browser e estados recuperados do bfcache tornam a operação difícil de compreender e testar.

### Concrete fix

Depois do commit, responder `303` para `/ui/configuracoes?aba=rsd` e transportar a mensagem de sucesso por flash de sessão ou mecanismo equivalente de uso único. O GET deve reconstruir a tela apenas com valores persistidos e nunca com a senha enviada no POST.

### Domain details

#### Acceptance criteria

- Recarregar a página depois de salvar executa apenas GET.
- Voltar e avançar não repetem a gravação nem restauram senha digitada.
- A aba RSD permanece ativa no GET de destino.
- A mensagem de sucesso aparece uma vez.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - A resposta direta ao POST está explícita na rota.
  - O código local já contém uma mitigação de bfcache, evidenciando o problema de navegação.
- **Weaknesses:**
  - Outros formulários de configurações usam padrão semelhante; a correção pode exigir uma convenção compartilhada além do RSD.
- **Suggested checks:**
  - Verificar o comportamento de refresh/back/forward em Chromium, Firefox e Safari.

## imp-20260807-006 — Tornar a navegação por abas acessível por teclado

- **Impact:** Medium
- **Category:** Accessibility and responsiveness
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** acessibilidade, teclado, tabs, rsd
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/static/app.css`, `bases/xtreme_system/api/static/app.js`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/templates/configuracoes.html:19` — navegação de configurações

```html
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-banco" {% if aba_ativa == "banco" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-whatsapp" {% if aba_ativa == "whatsapp" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-rsd" {% if aba_ativa == "rsd" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-tema" {% if aba_ativa == "tema" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-empresa" {% if aba_ativa == "empresa" %}checked{% endif %}>

  <div class="settings-layout">
    <nav class="settings-nav" role="tablist" aria-label="Seções de configurações">
```

### Description

Os rádios que controlam as abas ficam com `pointer-events: none` e opacidade zero no CSS, enquanto os elementos visíveis são `label` com `role="tab"`, sem `tabindex`, `aria-selected`, `aria-controls` ou comportamento de setas. A aba Portal RSD não segue o padrão de interação esperado para tabs.

### Why it matters

Usuários de teclado ou tecnologia assistiva podem não alcançar ou compreender a aba, bloqueando o acesso ao gerenciamento de credenciais. A semântica parcial também anuncia controles sem o estado e relacionamento necessários.

### Concrete fix

Usar botões reais com `role="tab"` e painéis com `role="tabpanel"`, mantendo `aria-selected`, `aria-controls`, foco roving e teclas de seta; alternativamente, preservar os radios nativos como controles focáveis e remover os papéis ARIA incompatíveis.

### Domain details

#### Acceptance criteria

- Tab entra no conjunto de abas e setas percorrem as opções.
- O leitor de tela anuncia nome, seleção e painel relacionado.
- A seleção inicial do servidor continua abrindo Portal RSD após respostas do fluxo.
- Foco visível atende aos mesmos tokens usados nos demais controles.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - A estrutura ARIA incompleta e a remoção de eventos de ponteiro nos radios foram verificadas.
- **Weaknesses:**
  - Não houve teste manual com leitor de tela nesta execução.
- **Suggested checks:**
  - Validar com axe, navegação apenas por teclado e ao menos VoiceOver ou NVDA.

## Discarded candidates

### Trocar `autocomplete="new-password"` por `current-password`

Impacto incerto e provavelmente baixo: gerenciadores de senha variam, e desabilitar preenchimento automático pode ser uma decisão deliberada para credenciais de terceiros.

### Ajustar espaçamento e decoração visual do painel RSD

Descartado por ser preferência estética sem evidência de erro, hesitação ou perda de produtividade.
