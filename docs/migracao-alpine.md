# Migração para Alpine.js — etapas restantes e achados

Documento de continuidade da adoção do Alpine no frontend (branch
`guilsmatos1/alpine-frontend-dedup`). Cobre:

1. O que falta implementar — [etapa 7](#etapa-7--painel-de-colunas-columnsjs) e
   [etapa 8](#etapa-8--campos-decimais-via-x-mask)
2. [Por que a suíte de testes falha de forma intermitente](#a-suíte-de-testes-é-instável-por-banco-compartilhado)
3. [O wizard de veículo, que está inalcançável](#o-wizard-de-veículo-é-inalcançável-e-estava-quebrado)

Estado atual: 6 das 8 frentes concluídas. JS mantido à mão saiu de **954 para
781 linhas**, e `_form_compra.html`, `_form_venda.html` e `_form_veiculo.html`
ficaram com zero `<script>` inline.

---

## Convenções a seguir

Antes de mexer em qualquer uma das etapas abaixo, três regras que já valem no
código migrado (registradas em `rules/frontend.md`):

**Toda lógica vai em `static/components.js`, via `Alpine.data()`.** Os templates
só referenciam o componente pelo nome e usam diretivas simples. Isso mantém a
lógica em um arquivo em vez de espalhá-la por 78 templates, e deixa aberto o
caminho para o build CSP-friendly do Alpine, que proíbe arrow functions,
template literals, destructuring, spread e acesso a `document`/`window`/`JSON`
dentro de atributos.

**`x-show` não serve quando o próprio CSS esconde o elemento.** `x-show` alterna
`display` inline; quando falso aplica `display:none`, quando verdadeiro **remove**
o estilo inline e o elemento volta ao valor da folha de estilos. Se a regra CSS
já é `display:none` — como `.wizard-step` em `app.css:471` — o elemento nunca
aparece. Nesses casos, ligue a classe de estado existente com `:class`. Foi
exatamente o que obrigou o wizard a usar `:class="{ 'is-active': step === N }"`.

**Script carregado uma vez precisa reinicializar em `htmx:load`.** Os formulários
chegam por swap, muito depois do `DOMContentLoaded`. Enquanto o `<script>` era
inline no fragmento, ele executava junto com o swap; como arquivo externo, não.
Veja `reference.js` e o teste que trava esse contrato,
`tests/e2e/test_reference_field.py`.

**Atenção a testes que assertam HTML literal.** `tests/test_ui.py` compara
substrings exatas como `name="houve_troca" value="1" type="checkbox" checked`.
Inserir uma diretiva Alpine no meio quebra a asserção sem que haja mudança de
comportamento. Como ordem de atributo é arbitrária, ponha a diretiva **antes** do
`name`/`value` em vez de alterar o teste.

---

## Etapa 7 — Painel de colunas (`columns.js`)

### Situação

`bases/xtreme_system/api/static/columns.js` tem 256 linhas e faz três coisas
distintas:

| bloco | linhas aprox. | migra? |
|---|---|---|
| `openPanel()` — monta o modal por `innerHTML` | ~70 | **sim** |
| `load`/`save`/`reset` em `localStorage` | ~15 | sim, com ressalva |
| `applyPrefs`/`applyRow`/`resolvedOrder`/`defaultCols` | ~90 | **não** |
| `dragAfter` + drag-and-drop HTML5 | ~50 | **não** |
| `ensureButton` + hook `htmx:afterSwap` | ~15 | não |

O alvo é só o primeiro bloco. Reordenar células de `<tr>` e a API de drag nativa
não têm equivalente declarativo — Alpine não substitui isso, e tentar seria
piorar. O hook `htmx:afterSwap` continua necessário justamente porque
`applyPrefs` manipula a tabela inteira, que não é um componente Alpine.

### Passos

**1. Extrair o painel para um partial Jinja.** Criar
`templates/_modal_colunas.html` com a estrutura que hoje é string em
`openPanel()`: `.modal` > `.modal__panel` > head/body/foot, a `<ul class="cols-list">`
e os botões "Restaurar padrão" e "Fechar".

A lista vira `<template x-for="col in colunas" :key="col.key">`, com o grip, o
checkbox (`x-model="col.visivel"`) e o rótulo.

**2. Registrar `Alpine.data("colunas", ...)`** em `components.js` com:

- `colunas`: array de `{ key, label, visivel }` montado no `init()` a partir do
  `thead` (reaproveitando a lógica de `defaultCols` e `colLabels`, que devem ser
  movidas para o componente ou expostas por `columns.js`)
- `persistir()`: grava ordem e ocultas, e chama o `applyPrefs` que permanece em
  `columns.js`
- `restaurar()`: limpa a preferência e recarrega o padrão

**3. Substituir os listeners manuais por diretivas.** O `close()` atual registra
e remove `keydown` na mão — clássico vazamento se alguém esquecer o
`removeEventListener`. Vira `x-on:keydown.escape.window="fechar()"` e
`x-on:click.self="fechar()"` no backdrop.

**4. `$persist` com chave dinâmica.** A preferência é por tabela
(`cols:<data-table>`), então o `.as()` precisa ser montado dentro do `x-data`.
**Ressalva:** `$persist` serializa em JSON. Se `columns.js` continuar lendo a
mesma chave com `JSON.parse(localStorage.getItem(...))` o formato bate, mas
qualquer leitura crua quebra. Se isso complicar, mantenha `load`/`save` como
estão — o ganho aqui é pequeno e o risco de perder as preferências salvas dos
usuários não compensa.

**5. Drag-and-drop.** Manter em `columns.js`. Ao reordenar, atualizar o array
`colunas` do componente para que Alpine e DOM não divirjam. Este é o ponto de
maior atrito da etapa: há duas fontes de verdade (o `<ul>` reordenado pelo drag
e o array reativo). Uma alternativa é reescrever o drag com base em índices no
array em vez de mover nós — mais trabalho, porém elimina a divergência.

### Ganho esperado

Cerca de **−50 linhas de JS, +30 de markup**. O valor real não é o volume: é
apagar a montagem de DOM por concatenação de string e o cleanup manual de
listener.

### Como verificar

**Não há nenhum teste cobrindo o painel de colunas hoje.** Antes de migrar,
escreva o e2e — caso contrário a etapa vai às cegas. O teste precisa cobrir:

- abrir o painel pelo botão "Colunas"
- desmarcar uma coluna e confirmar que as células somem do `thead` e do `tbody`
- recarregar a página e confirmar que a preferência persistiu
- "Restaurar padrão" e confirmar que a coluna volta
- reordenar por drag e confirmar a nova ordem após um swap do htmx

O último item é o mais importante: `applyPrefs` roda de novo em
`htmx:afterSwap`, e é aí que uma divergência entre o array do Alpine e o DOM
apareceria.

---

## Etapa 8 — Campos decimais via `x-mask`

### Situação

`static/filters.js` tem 58 linhas e três responsabilidades:

1. `formatDecimalInput` — formata para pt-BR (`1.234,56`) no `blur` e no load
2. `normalizeDecimal` — desfaz a formatação antes de cada request
3. `htmx:configRequest` — aplica a normalização e remove parâmetros vazios em
   formulários com `data-omit-empty-params`

Só o item 1 é candidato ao `x-mask`. **Os itens 2 e 3 devem permanecer**: são
integração com htmx, não estado de view. Remover a normalização enviaria
`"130.000,00"` para o servidor, que espera `130000.00`.

### Passos

1. Trocar `formatDecimalInput`/`formatDecimalInputs` por
   `x-mask:dynamic="$money($input, ',', '.')"` nos inputs com
   `inputmode="decimal"`. O plugin `alpine-mask.min.js` já está vendorizado.

   A assinatura é `$money($input, separadorDecimal, separadorMilhar, precisão)`
   — a ordem é fácil de inverter. Para o formato brasileiro `1.234,56`, o
   decimal é `','` e o milhar é `'.'`, exatamente como acima. A precisão padrão
   é 2, que é o que `formatDecimalInput` já usa.
2. Remover o listener de `blur` e o hook `htmx:load` **apenas** para os campos
   que virarem componentes Alpine — o Alpine reinicializa sozinho via
   MutationObserver.
3. Manter `normalizeDecimal` e o handler de `htmx:configRequest` intactos.

### Riscos, que são maiores do que o tamanho da etapa sugere

**A formatação passa a ser durante a digitação, não no `blur`.** O `x-mask`
reformata a cada tecla; o código atual só formata ao sair do campo. É uma
mudança de sensação para quem usa o sistema todo dia — vale confirmar com o
usuário antes.

**`$money` e `normalizeDecimal` precisam concordar exatamente.** Hoje
`normalizeDecimal` trata dois formatos: com vírgula (`1.234,56` → remove pontos,
troca vírgula por ponto) e sem vírgula (devolve como está). Se o `x-mask` passar
a garantir sempre o formato com vírgula, o segundo ramo vira código morto — mas
só depois de confirmar que nenhum campo escapa da máscara.

**Cobertura atual é indireta.** Os testes e2e preenchem valores como
`"130000"` e `"123.45"` e verificam o resultado salvo; nenhum testa a formatação
em si. Vale um e2e específico: digitar `1234,5`, sair do campo, conferir o
exibido, submeter e conferir o que chegou ao servidor.

### Recomendação

Esta é a etapa de **pior relação custo/benefício** do plano: elimina ~15 linhas,
muda comportamento perceptível de digitação e mexe num caminho (formatação
monetária) onde erro silencioso vira valor errado no banco. Sugiro deixá-la por
último, ou descartá-la.

---

## Achados durante a migração

### A suíte de testes é instável, por banco compartilhado

**Sintoma.** `make test` falha com um conjunto de testes **diferente a cada
execução** — ou passa inteira. Os erros mais comuns são
`UsernameJaExisteError: username já existe` em `tests/test_api_auth.py`,
`tests/test_route_factories_ui.py` e `tests/test_create_admin.py`.

**Isso não foi introduzido por esta migração.** Verificado rodando o commit base
`c78f3a5`, sem nenhuma alteração, três vezes sobre banco recém-criado:

```
3 failed, 471 passed
2 failed, 472 passed
1 failed, 473 passed
```

**Duas causas somadas.**

*Primeira: as duas suítes compartilham o mesmo banco e nenhuma limpa.* A fixture
`live_server_url` (`tests/e2e/conftest.py`) semeia usuários `seed` e `admin`, um
investidor e um veículo em `xtreme_test` — o mesmo banco que `tests/` usa. Rodar
o e2e e em seguida `make test` faz os testes que criam um usuário `admin`
esbarrarem na constraint de unicidade. Reproduzível de forma determinística:

```bash
dropdb -U postgres xtreme_test && createdb -U postgres xtreme_test
make test                 # 474 passed
# roda o e2e
make test                 # 2 failed
```

*Segunda: `PYTEST_ARGS` usa `-n auto`.* Os workers do xdist rodam em paralelo
contra o mesmo banco, então mesmo sem o e2e há corrida entre testes que inserem
usuários com o mesmo `username`. É o que explica o conjunto de falhas variar.

**Contorno em uso.** Recriar o banco entre as suítes:

```bash
dropdb -U postgres xtreme_test; createdb -U postgres xtreme_test
make test

dropdb -U postgres xtreme_test; createdb -U postgres xtreme_test
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme_test \
  uv run python -m pytest tests/e2e/ -q --browser chromium -p pytest_playwright
```

**Correções possíveis, em ordem de preferência.**

1. Isolar por worker: dar a cada worker do xdist seu próprio banco
   (`xtreme_test_gw0`, `gw1`, ...), derivando o nome de `PYTEST_XDIST_WORKER`.
   Resolve as duas causas de uma vez.
2. Fazer os testes usarem usernames únicos (sufixo aleatório) em vez de `admin`
   fixo. Mais barato, mas trata o sintoma.
3. Dar à fixture `live_server_url` um teardown que remova o que semeou. Resolve
   a contaminação entre suítes, não a corrida do `-n auto`.

**Bug de ergonomia relacionado.** O target `test-e2e-headless` do `Makefile` não
define `TEST_DATABASE_URL` (diferente de `test-postgres`), então falha de cara:

```
ERROR: TEST_DATABASE_URL is required so tests run against an Alembic-migrated
PostgreSQL database.
```

Correção de uma linha: replicar no target de e2e o mesmo prefixo de variável que
`test-postgres` usa.

**Cuidado ao diagnosticar.** Nem toda falha aqui é ruído. Durante esta migração
uma regressão real (`test_ui_criar_venda_troca_placa_ja_cadastrada_retorna_erro`)
apareceu no meio das falhas intermitentes. O que a distinguiu foi o
**determinismo**: falhou 3 de 3 vezes isolada, enquanto as instáveis variam.
Antes de descartar uma falha como flaky, rode-a isolada três vezes.

---

### O wizard de veículo é inalcançável, e estava quebrado

Dois problemas independentes em `_form_veiculo.html`, ambos anteriores a esta
migração.

#### 1. Não há entrada para ele na interface

`vendas.html` e `compras.html` têm botão de criação:

```html
<button data-testid="vendas-create" hx-get="/ui/vendas/novo"
        hx-target="#modal" hx-swap="innerHTML">
```

`veiculos.html` **não tem equivalente** — o `.page-head__actions` só oferece
"Exportar dados". A rota `GET /ui/veiculos/novo` existe (registrada pela fábrica
CRUD em `routes/ui_routes/veiculos.py:176`) e responde, mas nenhum usuário
consegue abri-la. Veículos entram no sistema pelo wizard de **compra**, que
cadastra o veículo junto.

Consequência prática: a variante de criação de `_form_veiculo.html` — 4 passos de
formulário — é código morto de UI.

#### 2. O script lançava exceção e abortava o wizard

O JS inline referenciava um elemento que não existe no markup:

```js
var selectVendedor = document.getElementById('cliente-vendedor-select');
...
selectVendedor.addEventListener('change', sincronizarVendedor);  // TypeError
sincronizarVendedor();

show(current);   // nunca chegava aqui
```

Não existe `#cliente-vendedor-select` em lugar nenhum do template — só
`#cliente-vendedor-input`, que é o typeahead. Sem guarda de nulo, a chamada
estourava `TypeError` e abortava a IIFE inteira.

Como `show(current)` era a **última** instrução, ele nunca executava. Os
listeners de "Próximo"/"Voltar" já tinham sido registrados antes do erro, então
a navegação entre passos funcionava — mas a visibilidade dos botões nunca era
inicializada. Efeito visível: **"Salvar" jamais aparecia no último passo**, e
"Voltar" ficava escondido para sempre. O wizard era impossível de concluir.

A migração para `x-show="step === total"` corrigiu isso de lado, já que a
visibilidade passou a ser derivada do estado em vez de aplicada por um `show()`
que não rodava. Os 10 campos `[data-novo-cliente]` desse formulário continuam
sem nada que os controle — não há select de cliente existente ali —, então
permanecem sempre visíveis, que é o comportamento efetivo de hoje.

#### O que decidir

Três caminhos, e a escolha é de produto, não técnica:

1. **Adicionar o botão** em `veiculos.html` (`hx-get="/ui/veiculos/novo"`), se
   cadastrar veículo sem compra associada for um fluxo desejado. Exige revisar o
   passo de cliente/vendedor, hoje sem controle.
2. **Remover a variante de criação** de `_form_veiculo.html` e a rota
   `/ui/veiculos/novo`, se veículos devem entrar só por compra. Elimina ~130
   linhas de template e o wizard.
3. **Deixar como está**, documentado, se houver intenção de retomar.

Enquanto não se decidir, o wizard não é testável por e2e: navegar direto para
`/ui/veiculos/novo` devolve o **fragmento** do modal, sem `<head>` — logo sem
`app.css` e sem Alpine —, então qualquer asserção sobre visibilidade falha por
motivo errado. Foi o que aconteceu na primeira tentativa de cobrir esse wizard.

---

## Referência rápida

| arquivo | papel |
|---|---|
| `static/components.js` | todos os `Alpine.data()`: `modalFoco`, `trocaVeiculo`, `wizard` |
| `static/reference.js` | typeahead de chave estrangeira, unificado |
| `static/columns.js` | preferências de coluna — **alvo da etapa 7** |
| `static/filters.js` | decimais + integração htmx — **alvo da etapa 8** |
| `static/alpine*.min.js` | Alpine 3.15.12 vendorizado (core, persist, focus, mask) |
| `rules/frontend.md` | regras vigentes do frontend |
| `tests/e2e/test_reference_field.py` | trava o contrato de `htmx:load` |
| `tests/e2e/test_wizard_navegacao.py` | visibilidade dos botões por passo |
| `tests/e2e/test_troca_veiculo.py` | transições do bloco de troca |
