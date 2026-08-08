# Improvement opportunities

- **Generated:** 2026-08-07T13:54:20-03:00
- **Total:** 6

## imp-20260807-001 — Restringir a URL RSD para impedir SSRF e envio de credenciais

- **Impact:** High
- **Category:** Input validation and boundaries
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** security, rsd, ssrf, credentials, url-validation
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`, `tests/test_rsd.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/rsd/core.py:274` — `client_from_values`

```python
    cache de `client_from_config` — o chamador é responsável por abrir e
    fechar o client.
    """
    email_final = (email or config.email).strip()
    senha_final = senha or _decriptar_senha(config.senha)
    base_final = (base_url or config.base_url or _DEFAULT_BASE_URL).strip().rstrip("/")
    if not email_final or not senha_final:
        raise RsdNotConfiguredError("Configure e-mail e senha do RSD em Configurações.")
    return RsdClient(
        base_url=base_final or _DEFAULT_BASE_URL, email=email_final, senha=senha_final
    )
```

### Description

`base_url` vem do formulário e é aceita sem validar esquema, host, porta, redirecionamentos ou destino de rede. O login seguinte envia e-mail e senha ao endereço resultante. Um administrador enganado, uma sessão administrativa comprometida ou uma requisição forjada pode apontar o cliente para um host atacante ou serviço interno.

### Why it matters

Além de SSRF contra a rede acessível ao servidor, a funcionalidade transforma o próprio teste de conexão em um canal de exfiltração das credenciais RSD. O risco é maior porque a senha persistida pode ser reutilizada quando o campo do formulário chega vazio.

### Concrete fix

Remover a URL base da UI se só existe um portal oficial. Se ambientes alternativos são necessários, validar no servidor uma allowlist explícita de hosts HTTPS e portas, rejeitar userinfo, fragmentos, IPs literais e destinos privados/loopback após resolução DNS, e bloquear redirects para fora da allowlist. Não iniciar nenhuma chamada antes dessa validação.

### Domain details

#### Security tests

- Rejeitar HTTP, localhost, IP privado, link-local, userinfo e host fora da allowlist.
- Revalidar cada destino após redirect e resolução DNS.
- Confirmar que nenhuma tentativa rejeitada instancia ou abre o cliente HTTP.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - A origem não confiável e o uso como destino do cliente estão no mesmo caminho de código.
  - O template confirma que o administrador pode editar livremente o valor.
- **Weaknesses:**
  - Não foi inspecionada a segmentação de rede do ambiente de produção; ela pode reduzir destinos alcançáveis, mas não impede envio para a internet.
- **Suggested checks:**
  - Inventariar endpoints RSD legítimos de homologação antes de definir a allowlist.

## imp-20260807-002 — Falhar de forma segura quando a chave não decriptar a senha

- **Impact:** High
- **Category:** Secrets and sensitive data
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** high
- **Tags:** security, encryption, key-rotation, fail-closed
- **Files affected:** `components/xtreme_system/rsd/core.py`, `alembic/versions/`, `tests/test_rsd.py`, `README.md`
- **Related opportunities:** imp-20260807-005

### Location

`components/xtreme_system/rsd/core.py:67` — `_decriptar_senha`

```python
    try:
        return _get_fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except InvalidToken:
        if valor.startswith(_FERNET_TOKEN_PREFIX):
            # O valor tem cara de ciphertext Fernet mas não decripta com a
            # chave atual — provável RSD_ENCRYPTION_KEY rotacionada/errada,
            # não senha legada em texto plano. Isso costuma se disfarçar de
            # "E-mail ou senha inválidos" no portal; loga para diagnóstico.
            logger.warning("rsd_decriptar_senha_falhou_chave_invalida")
        # Caso contrário: valor gravado em texto plano antes desta feature —
        # mantém funcionando até a próxima atualização de config recodificar.
        return valor
```

### Description

Quando um token Fernet não pode ser aberto com a chave atual, a função apenas registra aviso e devolve o próprio ciphertext como se fosse a senha. O fluxo então o envia ao portal externo, produzindo um erro de autenticação enganoso e propagando material cifrado desnecessariamente.

### Why it matters

Uma chave rotacionada, ausente ou incorreta deveria interromper o uso do segredo. Continuar mascara falhas operacionais, dificulta recuperação e viola o princípio de falhar fechado para credenciais protegidas.

### Concrete fix

Ao reconhecer formato cifrado inválido, lançar uma exceção específica de configuração/criptação e nunca construir o cliente. Manter compatibilidade com texto plano legado apenas por uma migração versionada e temporária, não por fallback permanente em runtime. Adotar rotação com chave atual e chaves anteriores identificadas por versão.

### Domain details

#### Acceptance criteria

- Ciphertext inválido nunca é enviado em uma requisição de login.
- A UI informa que a chave de criptografia/configuração precisa de intervenção administrativa, sem mostrar o token.
- A rotação recriptografa dados existentes de forma transacional e auditável.

### Self-critique

- **Confidence:** 10/10
- **Uncertain:** No
- **Strengths:**
  - O retorno inseguro está explícito e um teste atual confirma esse comportamento.
- **Weaknesses:**
  - O formato legado em texto plano pode ainda existir em instalações que não aplicaram a migração; a remoção exige plano de compatibilidade.
- **Suggested checks:**
  - Consultar, sem registrar valores, quantas linhas atuais não possuem formato Fernet válido.

## imp-20260807-003 — Implementar revogação completa da credencial armazenada

- **Impact:** Medium
- **Category:** Secrets and sensitive data
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** security, credentials, revocation, data-retention
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/templates/configuracoes.html`, `tests/test_rsd.py`
- **Related opportunities:** None

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

O contrato trata senha vazia exclusivamente como “preservar o valor atual” e não existe operação separada para apagá-la. Assim, mesmo que o e-mail seja removido, o segredo cifrado permanece no banco e pode continuar no cliente global em memória até invalidação.

### Why it matters

Credenciais suspeitas ou desativadas precisam ser eliminadas para reduzir retenção e impedir reativação acidental. Sem revogação, o sistema não atende ao ciclo mínimo de criação, uso, rotação e remoção de segredo.

### Concrete fix

Adicionar uma operação administrativa explícita e auditada que zere e-mail e senha, redefina a URL, invalide e feche todos os clientes cacheados e marque a configuração como revogada. Exigir confirmação e não reutilizar o POST genérico de atualização.

### Domain details

#### Security tests

- Confirmar que banco, cache e respostas não mantêm o segredo após revogação.
- Confirmar que consultas subsequentes falham como “não configurado”.
- Confirmar que usuário não administrador recebe 403.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - O modelo de atualização e a ausência de rota de remoção foram verificados.
- **Weaknesses:**
  - Objetos Python e backups anteriores não podem ser apagados retroativamente pela ação proposta.
- **Suggested checks:**
  - Definir política de retenção/rotação para backups que contenham `rsd_config`.

## imp-20260807-004 — Proteger os POSTs de credenciais com token CSRF

- **Impact:** Medium
- **Category:** Transport and configuration
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** security, csrf, cookie-auth, configuration
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/routes/ui_routes/auth.py`, `bases/xtreme_system/api/setup.py`, `tests/test_rsd.py`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/templates/configuracoes.html:240` — formulário de credenciais RSD

```html
      <form method="post" action="/ui/configuracoes/rsd" class="card card--pad settings-form">
        <div class="modal-section">
          <h4>{{ ui.icon("link") }} Credenciais</h4>
          <div class="form-grid">
            <label class="field field--full">
              <span class="field__label">E-mail</span>
              <input class="input" name="email" type="email" placeholder="loja@email.com"
                     value="{{ config_rsd.email }}" autocomplete="off">
            </label>
            <label class="field field--full">
              <span class="field__label">Senha</span>
```

### Description

Os POSTs de salvar e testar dependem do cookie `access_token`, mas o formulário não possui token CSRF e as rotas não validam origem/token. `SameSite=Lax` no cookie reduz ataques cross-site clássicos, porém não protege cenários same-site, subdomínio comprometido ou mudanças futuras na política do cookie.

### Why it matters

O endpoint altera e usa segredos e, combinado com a URL editável, pode ser induzido a autenticar contra um destino escolhido. Operações dessa sensibilidade não deveriam depender apenas do comportamento SameSite do navegador.

### Concrete fix

Emitir token CSRF ligado à sessão, incluí-lo em todos os formulários/headers HTMX e validá-lo em POST, PUT, PATCH e DELETE. Como defesa adicional, rejeitar `Origin`/`Referer` fora das origens configuradas. Manter `SameSite`, `HttpOnly` e `Secure` como camadas independentes.

### Domain details

#### Security tests

- POST autenticado sem token ou com token inválido retorna 403 e não chama o RSD.
- Token válido funciona em formulário convencional e HTMX.
- Origem não permitida é rejeitada antes de processar credenciais.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** Yes
- **Strengths:**
  - A ausência de token no formulário e a autenticação por cookie foram verificadas.
- **Weaknesses:**
  - `SameSite=Lax` reduz bastante a exploração cross-site comum; o impacto depende da topologia de domínios e de conteúdo same-site não confiável.
- **Suggested checks:**
  - Mapear subdomínios e origens same-site atendidos em produção antes de fechar a severidade.

## imp-20260807-005 — Rejeitar chaves de criptografia padrão e documentar rotação

- **Impact:** Medium
- **Category:** Transport and configuration
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** medium
- **Tags:** security, secret-management, startup-validation, documentation
- **Files affected:** `.env.example`, `components/xtreme_system/rsd/core.py`, `README.md`, `tests/test_rsd.py`
- **Related opportunities:** imp-20260807-002

### Location

`.env.example:1` — configuração de segredos

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme
# Opcional: usado se DATABASE_URL (ex.: container Docker) estiver inacessivel na
# inicializacao. Ex.: postgres local via brew, sem senha.
# DATABASE_URL_FALLBACK=postgresql+psycopg://postgres@localhost:5432/xtreme
AUTH_SECRET_KEY=your-secret-key-minimum-32-bytes-long-change-this-in-production
# Usada para cifrar a senha do portal RSD em repouso (rsd_config.senha).
# Trocar exige recodificar as linhas existentes — ver alembic a3b4c5d6e7f8.
RSD_ENCRYPTION_KEY=your-rsd-encryption-key-change-this-in-production
LOG_LEVEL=INFO
LOG_JSON=false
```

### Description

O arquivo de exemplo contém uma chave RSD pública e previsível, e `Settings` apenas exige que alguma string exista. O README ensina a gerar `AUTH_SECRET_KEY`, mas não estabelece geração, validação de placeholder, custódia ou rotação para `RSD_ENCRYPTION_KEY`.

### Why it matters

Uma instalação que copie o exemplo sem trocar a chave cifra todas as senhas com material conhecido. Nesse cenário, acesso ao banco é suficiente para recuperar as credenciais do portal.

### Concrete fix

Rejeitar em startup o placeholder conhecido e chaves abaixo de um requisito mínimo; documentar geração criptograficamente segura, armazenamento no secret manager e procedimento de rotação transacional. Preferir injetar a chave fora do `.env` em produção.

### Domain details

#### Acceptance criteria

- Produção não inicia com placeholder ou chave fraca.
- O setup gera valores independentes para autenticação e criptografia RSD.
- A documentação descreve backup e rotação sem perda das credenciais existentes.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - O placeholder e a ausência de validação específica foram verificados.
- **Weaknesses:**
  - Deployments existentes podem já injetar uma chave forte por infraestrutura externa.
- **Suggested checks:**
  - Auditar somente a presença/força, nunca o valor, das variáveis nos ambientes implantados.

## imp-20260807-006 — Limitar a permanência da senha em texto claro no cache global

- **Impact:** Medium
- **Category:** Secrets and sensitive data
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** security, memory, cache, plaintext-secret, concurrency
- **Files affected:** `components/xtreme_system/rsd/core.py`, `bases/xtreme_system/api/setup.py`, `tests/test_rsd.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/rsd/core.py:251` — `client_from_config`

```python
    key = _client_cache_key(config)
    with _client_cache_lock:
        client = _client_cache.get(key)
        if client is None:
            client = RsdClient(
                base_url=config.base_url or _DEFAULT_BASE_URL,
                email=config.email,
                senha=_decriptar_senha(config.senha),
            )
            client.open()
            _client_cache[key] = client
        return client
```

### Description

O cache global guarda um `RsdClient` que mantém a senha decriptada em um atributo por toda a vida do processo ou até uma alteração de configuração. Não há TTL, limite, limpeza por inatividade ou fechamento registrado no shutdown da aplicação.

### Why it matters

O reaproveitamento de sessão reduz logins, mas amplia a janela em que dumps de memória, introspecção acidental ou falhas adjacentes podem encontrar o segredo em claro. O mesmo objeto mutável também é compartilhado entre handlers concorrentes.

### Concrete fix

Dar TTL curto e tamanho máximo ao cache, registrar fechamento no lifespan da aplicação e remover a senha do objeto após estabelecer/renovar sessão, recuperando-a de um provedor controlado somente quando necessário. Serializar login/renovação por cliente ou usar sessões isoladas por request quando a segurança superar o ganho de performance.

### Domain details

#### Security tests

- Cliente ocioso expira e é fechado.
- Shutdown fecha todos os clientes.
- Alteração/revogação remove imediatamente clientes antigos.
- Renovações concorrentes não misturam cookies e CSRF.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** Yes
- **Strengths:**
  - A decriptação antes de inserir no cache global está explícita.
  - Não foi encontrado hook de shutdown ou política de expiração.
- **Weaknesses:**
  - Strings Python não oferecem apagamento seguro garantido; a redução de permanência diminui, mas não elimina resíduos de memória.
- **Suggested checks:**
  - Medir frequência real de login para escolher TTL sem degradar o portal.

## Discarded candidates

### Remover o e-mail do log `rsd_login_ok`

Descartado por impacto baixo: e-mail é dado pessoal, mas não segredo de autenticação por si só; a política central de logs deve decidir a minimização de PII de forma consistente.

### Adicionar rate limit específico ao teste RSD

Descartado nesta análise porque já existe rate limit geral por usuário autenticado. Um limite mais estreito pode ser útil operacionalmente, mas faltam evidências de abuso ou lockout do portal.
