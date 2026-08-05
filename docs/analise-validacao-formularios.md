# Análise: validação Pydantic × máscara Alpine × bloqueio de required

Data: 2026-08-04

> **Atualização (2026-08-04):** todos os itens 1-9 do resumo priorizado foram implementados e verificados (item 4 foi revisado durante a implementação — ver seção "Status da implementação" ao final), exceto a parte de `x-mask` em campos monetários (item 5), que foi deliberadamente descartada por ter sido testada e reprovada antes.

## 1. Validação Pydantic — 59 de 173 campos (34%)

Contagem sobre todos os schemas `*Create` / `*Update` (campo conta como validado se tem `Field(...)` constraint ou `field_validator`):

| Componente | Schema | Campos | Validados |
|---|---|---|---|
| cliente | ClienteCreate/Update | 11 | **10** ✅ |
| venda | VendaCreate/Update | 17 | 7 |
| veiculo | VeiculoCreate/Update | 18 | 5 |
| compra | CompraCreate | 9 | 2 |
| consignacao | ConsignacaoCreate | 10 | 2 |
| custo_veiculo | CustoVeiculoCreate | 5 | 2 |
| caixa | LancamentoInvestimentoCreate | 4 | 1 |
| **usuario** | UsuarioCreate/Update | 5 | **0** ❌ |
| **perfil** | PerfilCreate/Update | 3 | **0** ❌ |
| **investidor** | InvestidorCreate/Update | 1 | **0** ❌ |
| **empresa** | EmpresaConfigUpdate | 9 | **0** ❌ |

`cliente` é o único componente com cobertura real (`components/xtreme_system/cliente/core.py:202-247` — normalização de nome, documento, email, telefone, estado, CEP + `model_validator` cruzando documento×tipo). `usuario`, `perfil`, `investidor` e `empresa` não têm nenhuma constraint no schema — em `usuario` a força de senha é checada fora, na função `create` (`usuarios.py:155`), não no schema.

## 2. Máscara Alpine — 0 campos

**Nenhum campo usa máscara.** O plugin está carregado mas nunca é invocado:

- `bases/xtreme_system/api/templates/base.html:19` — carrega `alpine-mask.min.js`
- `x-mask` não aparece em nenhum template. A única ocorrência no projeto é um **comentário** em `components.js:83` referindo-se a um comportamento que não existe mais.

O que existe hoje no lugar de máscara é apenas cosmético ou dica de teclado:

| Campo | Recurso | Problema |
|---|---|---|
| `placa` (`_form_veiculo.html:32,156`) | `style="text-transform:uppercase"` | CSS só; o valor enviado continua minúsculo — salvo por `normalizar_placa()` no servidor |
| `proprietario_uf` (`_form_veiculo.html:81`) | `text-transform` + `maxlength="2"` | **sem contrapartida no servidor** — grava `"sp"` no banco |
| `preco`, `debitos`, `valor_compra`, `valor_venda` | `inputmode="decimal"` | só muda o teclado do celular; não formata nem restringe |
| `cli_documento`, `cli_telefone`, `cli_cep` | nada | usuário digita livre |

### Consequência: `preco` de veículo quebra com formato brasileiro

`bases/xtreme_system/api/routes/ui_routes/veiculos.py:411-418` joga o form direto no `model_validate` sem normalizar vírgula. Verificado em execução:

```
150000.00   -> 150000.00
150000,00   -> ValidationError
150.000,00  -> ValidationError
```

Note a inconsistência **dentro do mesmo handler**: `debitos` é normalizado em `veiculos.py:441` (`.replace(",", ".")`), `preco` não. O mesmo vale para:

- `valor_compra` — `compras.py:113-118` normaliza só `debitos`
- `valor_venda`, `valor_entrada`, `veic_troca_preco` — `venda_write.py:41-64` converte `""` → `None`, mas nunca `,` → `.`
- `consignacoes.py:117,121` é o **único** que normaliza o valor principal

## 3. Bloqueio de required vazio — incorreto

O bloqueio existe **só no cliente**. O servidor não rejeita string vazia.

**Camada HTML** (`required`): 18 ocorrências em `_form_veiculo.html`, 24 em `_form_venda.html`, 12 em `_form_compra.html`, 11 em `_form_consignacao.html`, 3 em `_form_cliente.html`.

**Camada wizard** (`components.js:417-449`): o `validStep()` está bem construído — pula `disabled`, pula ocultos via `offsetParent`, e valida o hidden companion dos autocompletes (`data-reference-url`). ~~Essa parte está correta.~~

> **Correção (2026-08-04, ver "Bug de escopo do `$el`" ao final):** essa conclusão estava errada. A *lógica* de `validStep()` está correta, mas ela nunca rodava de fato: o `querySelector` partia de `this.$el`, que nas expressões `x-on` dos filhos é o botão do clique, não a `<form>`. Não achando o passo, a função retornava `true` e o wizard avançava com todos os campos vazios. A análise acima foi feita lendo o código; só a execução no browser expôs a divergência.

**Camada Pydantic**: aqui está a falha. Campos `str` sem `min_length` aceitam `""`. Verificado em execução:

```python
VeiculoCreate.model_validate({'tipo':'carro','modelo':'','cor':'','ano':0,
                             'placa':'ABC1234','investidor_id':1})
# ACEITO: modelo='' cor='' ano=0
```

Ou seja: um POST via curl/HTMX que ignore o `required` do HTML grava veículo com modelo vazio, cor vazia e ano zero. `ClienteCreate` é a exceção — rejeita corretamente, porque `_trim_texto_obrigatorio` (`cliente/core.py:204`) converte vazio em erro.

### Divergências required HTML × obrigatório no schema

| Campo | HTML | Pydantic |
|---|---|---|
| `preco` (`_form_veiculo.html:89,182`) | `required` | `Decimal \| None = None` — opcional |
| `modelo`, `cor` (veículo) | `required` | `str` sem `min_length` — aceita `""` |
| `ano` (veículo) | `required` | `int` sem `ge`/`le` — aceita `0` e `-5` |
| `cli_nome`, `cli_documento` (`_form_veiculo.html:221,225`) | `required` | resolvidos por `ClienteCreate` ✅ |

O caso do `preco` é o mais grave: o `CheckConstraint("preco > 0")` (`veiculo/core.py:91`) protege contra valor negativo, mas `NULL` passa pelo check no Postgres — então um veículo sem preço entra no banco se o `required` do HTML for contornado.

### Ponto adicional: `campos_form_visiveis` × campos obrigatórios

`registrars.py:454` e `veiculos.py:413` filtram o form por permissão **antes** do `model_validate`. No update isso é seguro (schema totalmente opcional). Na criação via wizard, se um perfil não tiver permissão de ver `placa`/`modelo`/`ano`, o campo nem é renderizado (`_form_veiculo.html:154,161,169`) e o `VeiculoCreate` falhará com erro de campo faltando — o usuário vê um erro que não consegue corrigir.

## Resumo priorizado

| # | Item | Local | Gravidade | Status |
|---|---|---|---|---|
| 1 | `preco` de veículo não aceita formato BR | `veiculos.py:411-418` | Alta — quebra fluxo comum | ✅ Resolvido |
| 2 | `valor_compra` / `valor_venda` idem | `compras.py:113`, `venda_write.py:41` | Alta | ✅ Resolvido |
| 3 | Strings obrigatórias aceitam `""` no servidor | `veiculo/core.py:128-133` e demais | Alta | ✅ Resolvido (veiculo) |
| 4 | `preco` required no HTML mas opcional no schema | `veiculo/core.py:138` | Média | ⚠️ Revisado — mantido opcional (ver nota) |
| 5 | Plugin de máscara carregado e nunca usado | `base.html:19` | Média — 2KB inúteis + inconsistência de UX | ✅ Resolvido (parcial — ver nota) |
| 6 | `proprietario_uf` uppercase só em CSS | `_form_veiculo.html:81` | Média — suja o banco | ✅ Resolvido |
| 7 | `ano` sem faixa válida | `veiculo/core.py:132` | Média | ✅ Resolvido |
| 8 | `usuario`/`perfil`/`investidor`/`empresa` sem validação | respectivos `core.py` | Média | ✅ Resolvido |
| 9 | Wizard pode exibir erro incorrigível por permissão | `_form_veiculo.html:154+` | Baixa | ✅ Resolvido |

**O que uma correção envolveria**, em ordem de custo-benefício: (a) um helper compartilhado `parse_decimal_br()` chamado nos handlers ou como `field_validator(mode="before")` nos campos `Decimal` — resolve 1 e 2 de uma vez; (b) um `Annotated[str, Field(min_length=1)]` ou validator de trim reaproveitando o padrão já pronto em `cliente/core.py` — resolve 3; (c) decidir se `preco` é obrigatório e alinhar schema, HTML e coluna do banco — resolve 4; (d) aplicar `x-mask` nos campos de documento/telefone/CEP/placa/moeda ou remover o plugin — resolve 5 e 6.

## Status da implementação (2026-08-04)

Itens 1-3 (gravidade Alta) foram implementados e verificados: suíte completa `501 passed, 2 skipped` (excluindo e2e e `test_rsd.py`, que já falhava antes desta mudança e é não-relacionado), `ruff check` limpo nos arquivos tocados.

**1-2. Parser de decimal BR** — `parse_decimal_br()` novo em `components/xtreme_system/crud/core.py:14-31` (aceita `"1.234,56"` BR e `"1234.56"` US, converte para o formato que `Decimal()` entende). Aplicado como `field_validator(mode="before")` em:
- `veiculo/core.py` — `VeiculoCreate.preco` / `VeiculoUpdate.preco`
- `compra/core.py` — `valor_compra`, `debitos`
- `venda/core.py` — `valor_venda`, `valor_entrada`, `debitos`, `valor_diferenca`, `valor_pendente`
- `consignacao/core.py` — `valor_venda`, `comissao_percentual`

As normalizações manuais antigas em `compras.py`, `consignacoes.py` e `veiculos.py` (só `.replace(",", ".")`, que quebrava com separador de milhar — `"150.000,00"` virava `"150.000.00"` e disparava `InvalidOperation`) foram removidas/substituídas pelo helper compartilhado.

**3. Strings obrigatórias vazias** — `modelo` e `cor` de `Veiculo` agora usam `_trim_texto_obrigatorio()` (`veiculo/core.py`), que faz trim e rejeita vazio/espaço-em-branco, no mesmo padrão de `cliente/core.py:204`. Aplicado em `VeiculoCreate` e `VeiculoUpdate`.

**Gap fechado depois:** `venda.forma_pagamento` agora usa `crud.trim_texto_obrigatorio()` (`venda/core.py`), rejeitando vazio/espaço-em-branco em `VendaCreate`/`VendaUpdate`.

### Itens 4-9 (2026-08-04, segunda rodada)

**4. `preco` obrigatório — revisado, não implementado como planejado.** A primeira tentativa tornou `VeiculoCreate.preco` obrigatório (`Decimal = Field(gt=0)`), mas isso quebrou dois testes (`test_ui_compra_de_veiculo_novo_separa_preco_anunciado_do_custo`, `test_ui_compras_rollback_em_integrityerror_de_veiculo`): o fluxo de **compra** cria o veículo propositalmente **sem** `preco` — o preço anunciado é decidido depois, separado do custo de aquisição (`compra.valor_compra`). A divergência HTML `required` × schema opcional é intencional nesse caso específico (o `required` do HTML só se aplica ao form de edição direta do veículo, não ao form de compra). Revertido para `Decimal | None = Field(default=None, gt=0)`, sem outra mudança. **Achado durante a implementação:** `vehicle_resolution.py:resolver_veiculo_inline()` é chamado por `compras.py` com `preco=None` **hardcoded**, então mesmo que o form de compra enviasse `vei_preco`, ele seria descartado — isso não foi alterado nesta rodada por estar fora do escopo original (é um bug diferente do que o item 4 descrevia), mas vale investigar se o campo `vei_preco` no template (`_form_compra.html`) deveria alimentar o veículo criado.

**5. `x-mask` — só parcialmente aplicado.** Descoberta durante a implementação: `docs/migracao-alpine.md` (removido do working tree em `e3a21ab`, ainda no histórico em `2ab4aa9`) documenta que aplicar `x-mask`/`$money` em campos monetários foi **testado e reprovado** — o plugin trata a entrada como maquininha de cartão (dígitos entram pela direita, 2 últimos sempre viram centavos): digitar `"140000"` salvava R$140,00. Por isso a máscara monetária **não foi implementada** (mantido `filters.js`/`formatDecimalInput`, já validado). Implementado só para campos onde o servidor normaliza por dígitos de qualquer forma (`documento`, `telefone`, `CEP`, `placa`) — nesses casos a máscara é puramente visual, sem risco de ambiguidade: `Alpine.magic` novo em `components.js` (`$maskDocumento`, `$maskTelefone`, `$maskPlaca`) + `x-mask="99999-999"` estático para CEP, aplicado em `_form_cliente.html`, `_form_veiculo.html`, `_form_venda.html`, `_form_compra.html`, `_form_consignacao.html` e `configuracoes.html`.

**6. `proprietario_uf`** — `_normalizar_uf()` em `veiculo/core.py`, trim + uppercase, aplicado via `field_validator(mode="before")` em `VeiculoCreate`/`VeiculoUpdate`.

**7. `ano`** — `_validar_faixa_ano()` em `veiculo/core.py`, rejeita fora de `[1950, ano_atual + 1]`.

**8. `usuario`/`perfil`/`investidor`/`empresa`** — novos helpers `crud.trim_texto_obrigatorio()`/`crud.trim_texto()` em `crud/core.py`, aplicados a: `usuario.username` (obrigatório), `perfil.nome` (obrigatório), `investidor.nome` (obrigatório), e trim + uppercase de `uf` em `empresa.EmpresaConfigUpdate` (campos de config da empresa continuam opcionais por design — só trim, sem rejeitar vazio).

**9. Wizard × erro incorrigível por permissão** — `perfil.campos_ocultados(user, pagina)` novo em `perfil/core.py`, usado em `registrars.py` (`_criar`/`_atualizar`) para detectar quando um erro `"missing"` do Pydantic corresponde a um campo ocultado pelo perfil do usuário, e nesse caso `validation_error_detail()` retorna uma mensagem específica orientando a procurar um administrador, em vez do genérico "informe um valor válido".

Verificação: suíte completa `501 passed, 2 skipped` (mesma exclusão de e2e/`test_rsd.py`), `ruff check` limpo, JS validado com `node --check`.

## Bug de escopo do `$el` no Alpine (2026-08-04, terceira rodada)

Sintoma relatado: "a validação dos campos dos modais não está funcionando".

**Causa raiz** — `components.js`, `Alpine.data("wizard")`:

```js
var passo = this.$el.querySelector('.wizard-step[data-step="' + n + '"]');
if (!passo) return true;   // sempre caía aqui
```

Nas expressões `x-on` dos filhos, o `$el` do Alpine é **o elemento do evento** —
o botão "Próximo" —, não a `<form>` que tem o `x-data="wizard(N)"`. Logo
`button.querySelector('.wizard-step[...]')` retornava `null`, `validStep()`
retornava `true` por falta de passo, e o wizard avançava com todos os campos
obrigatórios vazios. `init()` não sofria do problema (roda no contexto da raiz),
por isso `total` estava correto e só a validação falhava — o que fazia o bug
parecer "a validação não existe" em vez de "a validação está desligada".

Reproduzido em Chromium (venda, passo 1 vazio): `EL DENTRO DO CLICK:
BUTTON/venda-wizard-next`, `step 1 -> 2` com `cli_nome`/`cli_documento`/
`cli_telefone` vazios. Chamando `validStep(1)` com `$el` = form, ela retorna
`false` corretamente.

Essa é a mesma armadilha já documentada e resolvida em `modalFoco`
(`this.root = this.$el` no `init`) — o `wizard` e o `trocaVeiculo` não tinham
recebido o mesmo tratamento.

**Correção**: guardar a raiz no `init` (`this.raiz = this.$el`) e usá-la nos
`querySelector`, em dois componentes:

- `wizard` — `init()` e `validStep()`. Afetava os 4 wizards (venda, compra,
  consignação, veículo).
- `trocaVeiculo` — `hiddenId()`, `busca()`, `preencherPlaca()` e `aplicar()`.
  Mesmo defeito latente: `aoBuscar`/`aoResolverReferencia` vêm do `@input` do
  campo de busca e `cadastrarNovo` do `@click` do botão, então o hidden
  `#veiculo-troca-search` não era limpo ao redigitar e a placa digitada na
  busca não era adiantada para o bloco de cadastro inline. (`aplicar()` já
  funcionava por ser chamada de `$watch`, cujo escopo é o do `init`.)

Modais **não-wizard** (formulários de edição) sempre validaram certo, pelo
`required` nativo do browser: verificado que o POST do htmx é bloqueado ao
esvaziar um campo obrigatório.

**Regressão**: `tests/e2e/test_wizard_validacao.py` — venda e compra não avançam
com campos obrigatórios vazios, e avançam quando completos. Confirmado que os
dois testes falham sem a correção.

**Efeito colateral nos testes**: com `validStep()` de fato ativo,
`test_wizard_htmx_cria_veiculo` e `_criar_compra_via_wizard`
(`tests/e2e/test_ui_browser.py`) passaram a travar no passo 2 — nunca
selecionavam `vei_tipo`, que é `required`. Adicionado `select_option("carro")`
nos dois pontos.

## Bug do middleware `close-modal` fechando modais de anexo (2026-08-05)

Sintoma: nos modais de anexos (comprovantes de compra, documentos de veículo),
enviar um arquivo fazia a lista de anexos "sumir" — o modal fechava sozinho
logo após o upload, mesmo a resposta do servidor vindo correta.

**Causa raiz** — `bases/xtreme_system/api/setup.py:184-204`, middleware
`_htmx_write_feedback`: toda resposta HTML 2xx de um POST/PUT/PATCH/DELETE sob
`/ui/` que não define seu próprio header `HX-Trigger` recebe automaticamente
`HX-Trigger: {"htmx:toast": ..., "htmx:close-modal": {}}`. O cliente
(`components.js:593`, `fecharModalAposHtmx`) reage a `htmx:close-modal`
fazendo `#modal.innerHTML = ""` (com `setTimeout(0)` para não colidir com o
swap em andamento).

As rotas de anexo (`attachment_routes.py`, usadas por comprovantes de compra e
documentos de veículo) devolvem o modal **atualizado** após upload/exclusão —
a intenção (`action_oob=True`, ver `_modal_comprovantes_compra.html` e
`_action_compra_comprovantes.html`) é *manter* o modal aberto com a lista
recarregada, não fechá-lo. Como essas rotas não definiam `HX-Trigger` próprio,
o middleware genérico assumia o comportamento padrão (fechar) e o
`setTimeout(0)` disparava a limpeza de `#modal` bem depois do htmx já ter
renderizado a lista atualizada — apagando silenciosamente o conteúdo correto
sem erro no console.

Reproduzido isolando cada etapa via `MutationObserver`/monkey-patch de
`Node.prototype.removeChild` em Chromium: o stack trace da remoção apontava
exatamente para `components.js:595` (`document.getElementById("modal").innerHTML = ""`),
chamada por `fecharModalAposHtmx`, disparada pelo listener
`x-on:htmx:close-modal` (`base.html:35`).

**Correção**: `upload_endpoint`/`delete_endpoint` em `attachment_routes.py`
agora fixam `response.headers["HX-Trigger"] = "{}"` antes de devolver a
resposta — mesmo padrão já usado em `vendas.py:618`
(`_processar_contrato_venda`) para o caso análogo de "este POST atualiza o
modal em vez de concluí-lo".

**Regressão**: `test_modal_compra_comprovantes_upload_e_exclusao` e
`test_modal_veiculo_documentos_upload_e_exclusao`
(`tests/e2e/test_ui_browser.py`) — ambos falhavam antes da correção
(contagem de botões "Excluir" ficava em 0 após upload) e passam depois.

## Limpeza de testes/feature órfã (2026-08-05)

Além do bug acima, mais 3 falhas em `test_ui_browser.py` não eram bugs de
aplicação:

- `test_modal_veiculos_vinculados_cliente_sem_historico` e
  `test_modal_auditoria_detalhe_mostra_registro` esperavam o valor cru
  digitado (`"55566677788"`) num campo com `x-mask:dynamic="$maskDocumento"`
  — corrigido para esperar o valor mascarado (`"555.666.777-88"`), que é o
  comportamento correto do recurso de máscara.
- `test_modal_venda_fechamento_confirma_rateio` preenchia
  `input[name="percentual"]` (`type="number"`) com `"100,00"` (vírgula) —
  Playwright/Chromium rejeita caracteres não numéricos em `type="number"`;
  corrigido para `"100.00"`.
- `test_modal_cliente_vendedor_sem_compra_mostra_vazio` testava um botão que
  não existe mais em `_row_veiculo.html`: a rota `/ui/veiculos/{id}/cliente-vendedor`,
  `_modal_cliente_vendedor.html` e `veiculos_cliente_vendedor.py` ficaram
  órfãos depois que `veiculo_detalhe.html:126` passou a mostrar a mesma
  informação inline na página de detalhe. Removidos rota, template, o registro
  em `ui.py` e o teste (confirmado: nenhuma outra referência no código).
