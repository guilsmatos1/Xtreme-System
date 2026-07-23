# Análise de funcionalidades — Xtreme Motors

Análise do sistema como produto: o que o usuário não consegue fazer hoje, faz mal, ou faz de
um jeito que deixa dado ruim entrar. Ordenado por valor entregue ao usuário.

Fluxo de referência percorrido no código: `compra` → `veiculo` (estoque) → `custo_veiculo` →
`venda` → `fechamento_venda` → `lancamento_investimento` (caixa) → `DRE`.

---

## Lançamentos gerados por fechamento podem ser editados e excluídos pela tela de caixa

Domain: caixa / fechamento
Evidence: bases/xtreme_system/api/routes/ui_routes/lancamentos.py:140, lancamentos.py:182, lancamentos.py:205, bases/xtreme_system/api/routes/json.py:165, API.md:355
User value: High
Frequency of use: Weekly
Estimated effort: Low
Schema change required: no

What the user can't do today:
O usuário confia que um fechamento de venda é imutável — é assim que ele é vendido na
documentação e na UI ("Fechada", sem botão de editar). Mas qualquer admin que entre em
Investidores → Lançamentos consegue editar o valor ou apagar a "Receita da venda #N" e a
"Distribuição de lucro da venda #N". O fechamento continua lá, intacto e imutável, e o caixa
do investidor passa a discordar dele. Não existe nenhum aviso, e a única pista de que isso
aconteceu fica na auditoria — que ninguém consulta por acaso.

Evidence in the system:
As três rotas de escrita da tela de caixa (`ui_lancamento_editar` em lancamentos.py:140,
`ui_lancamento_atualizar` em lancamentos.py:182 e `ui_lancamento_excluir` em lancamentos.py:205)
bloqueiam apenas `obj.origem == caixa.OrigemLancamento.veiculo`. Lançamentos com
`origem == fechamento_venda` passam direto. A rota JSON equivalente faz certo — json.py:165
usa `if obj.origem != caixa.OrigemLancamento.manual`. E API.md:355 documenta a regra como se
ela valesse em todo lugar: "lançamentos com origem `fechamento_venda` não podem ser editados
pelos endpoints manuais de caixa". A UI é o furo.

Proposed behavior:
Trocar as três checagens de `!= manual` (mesma condição da rota JSON), e esconder os botões
de editar/excluir nas linhas de lançamento cuja origem não seja `manual`.

Acceptance criteria:
- `GET/POST /ui/investidores/{id}/lancamentos/{lancamento_id}/editar` com lançamento de origem `fechamento_venda` retorna 403.
- `POST /ui/investidores/{id}/lancamentos/{lancamento_id}/excluir` com lançamento de origem `fechamento_venda` retorna 403.
- Em `_linhas_lancamentos.html`, linhas com `origem != manual` não renderizam botão de editar nem de excluir.
- Um teste cobre os três verbos para as origens `veiculo` e `fechamento_venda`.

---

## O formulário de lançamento oferece três opções chamadas "Saque", e uma delas aumenta o saldo

Domain: caixa
Evidence: bases/xtreme_system/api/templates/_form_lancamento.html:16, bases/xtreme_system/api/routes/ui_routes/lancamentos.py:126, components/xtreme_system/caixa/core.py:118
User value: High
Frequency of use: Weekly
Estimated effort: Low
Schema change required: no

What the user can't do today:
Ao lançar um aporte ou uma retirada de investidor, o usuário abre um select com quatro opções:
"Aporte", "Saque", "Saque" e "Saque". As três últimas são indistinguíveis na tela. Se ele
escolher a terceira opção pensando estar registrando uma retirada, o sistema grava um
`receita_venda` — que o cálculo de saldo **soma** em vez de subtrair. O investidor fica com
saldo inflado pelo dobro do valor lançado, e nada na tela indica que algo diferente aconteceu.

Evidence in the system:
A rota passa `"tipos": list(caixa.TipoLancamento)` (lancamentos.py:126), ou seja, os quatro
valores do enum: `aporte`, `custo`, `receita_venda`, `distribuicao_lucro`. O template renderiza
`{{ 'Aporte' if t.value == 'aporte' else 'Saque' }}` (_form_lancamento.html:16), colapsando três
tipos distintos no mesmo rótulo. Em caixa/core.py:118, `_SALDO_EXPR` soma `aporte` e
`receita_venda` e subtrai o resto — então "Saque" nº 3 move o saldo para o lado oposto do que
o rótulo promete. Os tipos `receita_venda` e `distribuicao_lucro` só deveriam nascer de
`criar_lancamento_fechamento` (caixa/core.py:254), nunca de um formulário manual.

Proposed behavior:
Restringir o select aos dois tipos que fazem sentido manualmente (`aporte` e `custo`, rotulados
"Aporte" e "Saque") e rejeitar no servidor qualquer `tipo` fora desse par nas rotas manuais de
criação e atualização.

Acceptance criteria:
- O select de `_form_lancamento.html` renderiza exatamente duas opções: Aporte (`aporte`) e Saque (`custo`).
- `POST /ui/investidores/{id}/lancamentos` com `tipo=receita_venda` ou `tipo=distribuicao_lucro` retorna 400 e não cria registro.
- O fechamento de venda continua criando `receita_venda` e `distribuicao_lucro` normalmente via `criar_lancamento_fechamento`.

---

## Custos lançados depois do fechamento desaparecem do resultado, para sempre

Domain: fechamento / custos
Evidence: components/xtreme_system/fechamento_venda/core.py:350, bases/xtreme_system/api/routes/ui_routes/custos_veiculos.py:38, components/xtreme_system/custo_veiculo/core.py
User value: High
Frequency of use: Weekly
Estimated effort: Medium
Schema change required: no

What the user can't do today:
A nota do funilaria chega três dias depois da venda ser fechada. O usuário lança o custo
normalmente na tela de Custos — o sistema aceita sem reclamar. Só que aquele custo não entra
em lugar nenhum: o `fechamento_venda` já congelou o total, o lucro já foi rateado entre os
investidores e o DRE já contou aquela venda. O custo fica órfão no banco, e o resultado do mês
fica permanentemente maior do que a realidade. O usuário não tem como saber que isso aconteceu.

Evidence in the system:
`_calcular` (fechamento_venda/core.py:350) tira um snapshot com
`session.query(func.sum(CustoVeiculo.valor)).filter_by(veiculo_id=...)` no instante do
fechamento, e o valor é persistido em `fechamento_venda.custos_operacionais`. Do lado do
cadastro de custos, o único hook de validação é `_validar_veiculo_fk`
(custos_veiculos.py:38), que apenas confere se o `veiculo_id` existe — não há checagem de
status do veículo nem de venda já fechada. Como não existe caminho para reabrir um fechamento
(ver item seguinte), o custo tardio é irrecuperável.

Proposed behavior:
Bloquear o cadastro/edição de `custo_veiculo` quando o veículo já tem uma venda fechada,
com mensagem explícita apontando o fechamento, e listar na tela de Custos um aviso por veículo
já fechado. Se o negócio precisar aceitar custos tardios, o caminho é reabrir o fechamento
(item seguinte) e refazê-lo.

Acceptance criteria:
- `POST /ui/custos-veiculos` para um veículo com `fechamento_venda` existente retorna 400 com mensagem citando o número da venda fechada.
- O mesmo bloqueio vale para a edição de um custo existente desse veículo.
- Veículos sem fechamento continuam aceitando custos normalmente.
- Um teste cobre custo antes do fechamento (aceito) e depois (rejeitado).

---

## Um fechamento de venda errado não tem como ser desfeito

Domain: fechamento
Evidence: components/xtreme_system/fechamento_venda/core.py:166-347, bases/xtreme_system/api/routes/json.py:191-237, bases/xtreme_system/api/routes/ui_routes/vendas.py:459-539
User value: High
Frequency of use: Occasional
Estimated effort: Medium
Schema change required: no

What the user can't do today:
O usuário fecha uma venda com o rateio errado — 50/50 quando deveria ser 70/30 — e clica em
confirmar. Acabou. Não existe botão de reabrir, cancelar ou corrigir, nem na UI nem na API.
Os lançamentos de distribuição de lucro já foram para o caixa dos investidores com os valores
errados. A única saída dentro do sistema é excluir a venda inteira (que cascateia o fechamento
e apaga o histórico do DRE junto), ou editar os lançamentos de caixa na mão pelo furo descrito
no item 1 — deixando o fechamento e o caixa em desacordo permanente.

Evidence in the system:
O componente `fechamento_venda` expõe `list_all`, `ids_by_venda_ids`, `get`, `get_by_venda`,
`listar_para_dre`, `preview` e `confirmar` (core.py:166-347). Não há `delete`, `cancelar` nem
`reabrir`. Do lado das rotas, json.py registra apenas `GET .../preview`, `POST
.../fechamento`, `GET /fechamentos-vendas` e `GET /fechamentos-vendas/{id}` (json.py:191-237);
a UI registra o modal de fechar e o modal de detalhe (vendas.py:459-539), este último em modo
somente leitura. O `ondelete="CASCADE"` em `fechamento_venda.venda_id` (core.py:44) confirma
que excluir a venda é hoje o único caminho de saída.

Proposed behavior:
Adicionar `fechamento_venda.reabrir(session, fechamento, *, usuario_id)`: apaga as
participações e os lançamentos de caixa com aquele `fechamento_venda_id`, apaga o fechamento,
tudo auditado na mesma transação. Expor como operação de perfil `reabrir_fechamento` na página
`vendas`, com botão no modal de detalhe e confirmação. A venda volta a ficar elegível e o
usuário refaz o fechamento.

Acceptance criteria:
- `POST /ui/vendas/{id}/fechamento/reabrir` remove o fechamento, suas participações e todos os `lancamento_investimento` com aquele `fechamento_venda_id`.
- Após reabrir, `preview` volta a devolver `elegivel = true` e a venda pode ser fechada de novo.
- A operação grava linhas de auditoria `DELETE` para fechamento, participações e lançamentos, com o `usuario_id` do ator.
- A operação exige a permissão `reabrir_fechamento` e é negada por padrão para não-admin.
- O DRE do período deixa de contar aquele fechamento imediatamente após a reabertura.

---

## Vendas com pagamento pendente não têm tela, total, vencimento nem baixa

Domain: venda / financeiro
Evidence: components/xtreme_system/venda/core.py:58-62, bases/xtreme_system/api/templates/_row_venda.html:29, bases/xtreme_system/api/templates/_row_venda.html:47, components/xtreme_system/fechamento_venda/core.py:371, bases/xtreme_system/api/templates/vendas.html:33-62
User value: High
Frequency of use: Daily
Estimated effort: Medium
Schema change required: no (usa `venda.pagamento_pendente`, `valor_pendente`, `datas_pagamento`)

What the user can't do today:
O usuário não consegue responder "quanto o pátio tem a receber e de quem vence essa semana"
sem varrer a lista de vendas com o olho. A dívida existe como coluna, mas não há filtro para
isolar as vendas pendentes, não há total, e as datas de vencimento estão num campo de texto
livre ("10/01, 10/02, 10/03") que o sistema não sabe ler. Quando o cliente paga, não existe
"dar baixa": o usuário precisa abrir a venda, desmarcar o checkbox e zerar o valor na mão.
E enquanto o pendente não é quitado, a venda fica fora de todo relatório financeiro, porque o
fechamento a recusa.

Evidence in the system:
`Venda` tem `pagamento_pendente`, `valor_pendente` e `datas_pagamento: str | None`
(venda/core.py:58-62) — o último é texto livre, com placeholder `10/01, 10/02, 10/03` no
formulário. A lista mostra a coluna "Dívida" (_row_venda.html:29) e permite ordenar/buscar por
ela, mas vendas.html:33-62 só oferece busca textual e seletor de coluna: nenhum filtro por
status ou por pendência. `_motivo_inelegivel` recusa o fechamento com "Venda possui pagamento
pendente" (fechamento_venda/core.py:371) e o botão de fechar só aparece quando
`not v.pagamento_pendente` (_row_venda.html:47) — então essas vendas nunca chegam ao DRE.

Proposed behavior:
Uma aba/filtro "A receber" na página de Vendas listando `pagamento_pendente = true`, com total
somado no topo, ordenação por valor, e um botão "Dar baixa" que zera `valor_pendente` e
desmarca `pagamento_pendente` em uma ação só (auditada). Deixar `datas_pagamento` como está
nesta primeira versão — estruturar vencimento é um passo seguinte e maior.

Acceptance criteria:
- `GET /ui/vendas?pendente=1` lista apenas vendas com `pagamento_pendente = true` e exibe a soma de `valor_pendente` no cabeçalho.
- `POST /ui/vendas/{id}/baixa` zera `valor_pendente`, marca `pagamento_pendente = false` e grava auditoria com o ator.
- Depois da baixa, o botão de fechar venda aparece na linha (se a venda estiver concluída).
- A ação respeita uma operação de perfil e é negada por padrão para não-admin.

---

## Consignação é tratada como compra no caixa e no cálculo de lucro

Domain: veículo / caixa / fechamento
Evidence: bases/xtreme_system/api/routes/ui_routes/veiculos.py:163, components/xtreme_system/caixa/core.py:161, components/xtreme_system/fechamento_venda/core.py:354, components/xtreme_system/veiculo/core.py:30
User value: High
Frequency of use: Weekly
Estimated effort: Medium
Schema change required: no

What the user can't do today:
Ao cadastrar um veículo em consignação — que a revenda não comprou, apenas expôs — o sistema
debita o preço cheio do caixa do investidor, como se o dinheiro tivesse saído. O saldo do
investidor fica negativo por um veículo que ninguém pagou. E no fechamento, o `preco` desse
veículo é descontado como custo, então o lucro apurado é o lucro de uma compra e revenda, não
a comissão da consignação. O usuário marca "Consignação" no formulário e o campo não muda
absolutamente nada no comportamento financeiro.

Evidence in the system:
`TipoEntrada` tem `compra` e `consignacao` (veiculo/core.py:30), mas uma varredura por
`tipo_entrada` no código não-template encontra apenas leitura para exibição, ordenação, busca e
CSV — nenhum ramo de decisão. O hook `after_create=caixa.criar_lancamento_veiculo`
(veiculos.py:163) é incondicional, e `criar_lancamento_veiculo` (caixa/core.py:161) grava
sempre `tipo=custo, valor=veiculo_obj.preco`. Em `_calcular`
(fechamento_venda/core.py:354), `custo_veiculo = _quantizar(venda_obj.veiculo.preco)`, também
sem olhar `tipo_entrada`.

Proposed behavior:
Não criar (nem sincronizar) lançamento de caixa para veículos com
`tipo_entrada = consignacao`, e usar `custo_veiculo = 0` no fechamento desses veículos — o
lucro da consignação passa a ser receita menos custos operacionais e débitos. Se a regra do
negócio for outra (repasse fixo ao consignante), o campo a introduzir é um valor de repasse; a
decisão é do negócio, mas o comportamento atual não corresponde a nenhuma das duas leituras.

Acceptance criteria:
- Criar veículo com `tipo_entrada = consignacao` não gera `lancamento_investimento`; com `tipo_entrada = compra` continua gerando.
- Alterar `tipo_entrada` de `compra` para `consignacao` remove o lançamento existente, e o caminho inverso o cria.
- `preview` e `confirmar` de um veículo consignado devolvem `custo_veiculo = 0`.
- Testes cobrem os dois tipos de entrada no caixa e no fechamento.

---

## O custo do veículo no DRE pode divergir silenciosamente do valor da compra

Domain: compra / veículo / fechamento
Evidence: bases/xtreme_system/api/routes/ui_routes/compras.py:254, bases/xtreme_system/api/routes/ui_routes/veiculos.py:396-407, components/xtreme_system/compra/core.py:150, components/xtreme_system/fechamento_venda/core.py:354
User value: High
Frequency of use: Weekly
Estimated effort: Medium
Schema change required: no

What the user can't do today:
Quando o usuário corrige o valor de uma compra — errou um dígito, renegociou com o vendedor —
o sistema atualiza a compra e só. O `veiculo.preco`, que é o custo usado no cálculo de lucro e
no caixa do investidor, fica com o valor antigo. Duas telas passam a mostrar números
diferentes para a mesma coisa, e o usuário não consegue explicar qual está certo. O caminho
inverso funciona pela metade: editar o veículo sincroniza o lançamento de caixa e grava
`compra.debitos`, mas nunca `compra.valor_compra`.

Evidence in the system:
No cadastro de compra com veículo novo, o preço nasce da compra:
`"preco": str(form.get("valor_compra") or "").strip()` (compras.py:254). Depois disso, a
atualização de compra usa a fábrica CRUD com `before_update=validate_cliente_veiculo_fks`
(compras.py:396) e `compra.update` (compra/core.py:150) — nenhum hook toca no veículo. Do
outro lado, `_atualizar_veiculo` (veiculos.py:396-407) chama `veiculo.update`, depois
`compra.update(..., CompraUpdate(debitos=debitos))` e
`caixa.sincronizar_lancamento_veiculo` — atualiza os débitos da compra, mas não o
`valor_compra`. O fechamento lê `venda_obj.veiculo.preco` (fechamento_venda/core.py:354), ou
seja, o lado que a edição de compra não atualiza.

Proposed behavior:
Ao atualizar `compra.valor_compra`, propagar para `veiculo.preco` do veículo daquela compra e
chamar `caixa.sincronizar_lancamento_veiculo`, na mesma transação — espelhando o que a edição
de veículo já faz na direção contrária. Vale apenas para veículos ainda não fechados; se
houver fechamento, recusar a edição com mensagem explícita.

Acceptance criteria:
- Alterar `valor_compra` via `POST /ui/compras/{id}` atualiza `veiculo.preco` e o valor do `lancamento_investimento` daquele veículo.
- A alteração é recusada com 409 quando o veículo já tem venda fechada.
- A auditoria registra as três escritas (compra, veículo, lançamento) com o mesmo ator.

---

## O dashboard mostra faturamento, nunca lucro nem estoque parado

Domain: relatórios / dashboard
Evidence: bases/xtreme_system/api/routes/ui_routes/dashboard.py:172-186, components/xtreme_system/veiculo/core.py:66, components/xtreme_system/fechamento_venda/core.py:224
User value: Medium
Frequency of use: Daily
Estimated effort: Medium
Schema change required: no

What the user can't do today:
A primeira tela que o dono abre responde "quanto vendemos" e não responde "quanto ganhamos"
nem "o que está encalhado". O lucro existe, calculado e persistido em cada fechamento, mas
mora atrás de dois cliques na página de DRE, que é admin-only e organizada por competência —
não por "como estamos hoje". O tempo de estoque existe por veículo, mas só como coluna: não há
nenhum indicador de quantos veículos passaram de 60 ou 90 dias no pátio, que é exatamente a
informação que dispara a decisão de baixar preço.

Evidence in the system:
`_ctx_dashboard` (dashboard.py:172-186) devolve `disponiveis`, `valor_estoque`,
`vendas_mes_count`, `vendas_mes_total`, `ticket_medio`, `ranking_vendedores`,
`atividades_recentes` e o gráfico de desempenho — todos derivados de `venda.valor_venda` e
`veiculo.preco`. O módulo `fechamento_venda` nem é importado no arquivo, embora
`dre_totais` (fechamento_venda/core.py:224) já entregue lucro e margem prontos para uma lista
de fechamentos. `Veiculo.tempo_estoque` (veiculo/core.py:66) é usado em `_row_veiculo.html`,
`veiculo_detalhe.html` e no CSV, mas nunca agregado.

Proposed behavior:
Dois KPIs novos no dashboard, sobre o mês já selecionado no seletor existente: "Lucro líquido"
e "Margem", vindos de `dre_totais(listar_para_dre(...))` no período do mês; e um card
"Estoque parado" com a contagem de veículos `disponivel` com `tempo_estoque > 90`, linkando
para a lista de veículos ordenada por tempo de estoque.

Acceptance criteria:
- O dashboard exibe lucro líquido e margem do mês selecionado, calculados a partir dos fechamentos com `data_fechamento` no mês.
- O card de estoque parado mostra a contagem de veículos disponíveis com mais de 90 dias e leva para `/ui/veiculos?sort=tempo_estoque&order=desc`.
- Com nenhum fechamento no período, os KPIs mostram zero em vez de quebrar.

---

## Documento de cliente não é validado nem normalizado, então o mesmo cliente entra duas vezes

Domain: cliente
Evidence: components/xtreme_system/cliente/core.py:27, components/xtreme_system/cliente/core.py:96, bases/xtreme_system/api/routes/ui_routes/common.py, components/xtreme_system/cliente/core.py:130-157
User value: Medium
Frequency of use: Daily
Estimated effort: Low
Schema change required: no (limpeza de dados existentes recomendada antes de aplicar o índice)

What the user can't do today:
Um vendedor cadastra "123.456.789-00" na compra; meses depois outro digita "12345678900" na
venda. Para o sistema são duas pessoas: o índice único não impede, `get_by_documento` não
encontra o existente, e o cliente aparece duplicado nas listas de Compradores e Vendedores,
com o histórico partido ao meio. Também não há checagem de dígito verificador — um CPF digitado
errado entra sem reclamação e vai parar no contrato de venda em PDF.

Evidence in the system:
`Cliente.documento` é `Mapped[str] = mapped_column(unique=True, index=True)`
(cliente/core.py:27) — texto livre, sem validador no `ClienteCreate`/`ClienteUpdate`.
`get_by_documento` (cliente/core.py:96) faz `filter_by(documento=documento)`, comparação
exata. As listas `list_compradores`/`list_vendedores` (cliente/core.py:130-157) agrupam por
`Cliente.id`, então cada grafia vira uma linha. `resolver_cliente`
(ui_routes/common.py) é o ponto único por onde compra e venda criam/encontram cliente.

Proposed behavior:
Normalizar `documento` para apenas dígitos no schema Pydantic (create e update), validar
dígito verificador conforme `tipo` (CPF para `pessoa_fisica`, CNPJ para `pessoa_juridica`), e
formatar só na exibição. `resolver_cliente` passa a buscar pelo documento normalizado, então o
cliente existente é reencontrado em vez de duplicado.

Acceptance criteria:
- Criar cliente com "123.456.789-09" e depois com "12345678909" resulta em conflito (409/400), não em dois registros.
- Documento com dígito verificador inválido é rejeitado com 400 e mensagem específica.
- `resolver_cliente` encontra o cliente existente independentemente da pontuação digitada.
- A exibição em listas, formulários e no contrato PDF continua mostrando o documento formatado.

---

## A lista de vendas não filtra por período nem por status

Domain: venda
Evidence: bases/xtreme_system/api/templates/vendas.html:33-62, components/xtreme_system/venda/core.py:216, bases/xtreme_system/api/routes/ui_routes/veiculos.py:99-106
User value: Medium
Frequency of use: Daily
Estimated effort: Low
Schema change required: no

What the user can't do today:
Para responder "o que vendemos este mês" ou "quais vendas ainda estão pendentes", o usuário
digita no campo de busca e torce. Buscar por "concluido" funciona por acidente — o termo cai
no `ilike` sobre o status — mas não existe filtro por intervalo de datas de jeito nenhum, e a
lista cresce indefinidamente porque devolve todas as vendas já registradas. Em uma página de
uso diário, isso é a fricção mais visível do sistema.

Evidence in the system:
vendas.html:33-62 monta a toolbar com um `input[name=q]` e um `select[name=search_column]`, e
nada mais. `venda.search` (venda/core.py:216) casa o padrão contra nome do cliente, documento,
modelo, placa, status e observações — sem nenhum parâmetro de intervalo. A página de veículos
já preparou o terreno para filtros estruturados: `_ctx_lista_veiculos` devolve
`filtro_tipos`, `filtro_status` e `filtro_tipo_entradas` (veiculos.py:99-106), mas uma busca
por esses nomes nos templates não retorna nada — eles são montados e nunca renderizados.

Proposed behavior:
Adicionar à toolbar de Vendas um select de status (todos + os quatro valores de `StatusVenda`)
e dois campos de data (`data_de`, `data_ate`, aplicados sobre `venda.data_venda`), combináveis
com a busca textual existente e propagados para o link de exportar CSV. Fechar o loop na
página de Veículos usando os três `filtro_*` que já são calculados.

Acceptance criteria:
- `GET /ui/vendas?status=concluido&data_de=2026-01-01&data_ate=2026-01-31` devolve apenas vendas concluídas com `data_venda` no intervalo.
- Os filtros combinam com `q` e `search_column` e sobrevivem à ordenação por coluna.
- `GET /ui/vendas/exportar` respeita os mesmos filtros ativos.
- Datas inválidas são ignoradas em vez de quebrar a página.

---

## Descartados

- **Pré-preenchimento e soma ao vivo do rateio no modal de fechamento** (`_modal_fechamento_venda.html`): o formulário lista todos os investidores com percentual vazio e só valida a soma de 100% no servidor — fricção real, mas de frequência baixa perto dos itens acima.
- **Custos operacionais não debitam o caixa do investidor**: `DATABASE.md:191` declara isso explicitamente ("Esses registros não alteram saldo de investidor"), então é decisão de negócio, não lacuna. Vale registrar que isso faz o saldo do caixa e o lucro do DRE discordarem pelo total de custos operacionais.
- **`compra.status` (pendente/finalizado/cancelado) não tem efeito nenhum**: nenhum código ramifica nesse campo, e o veículo entra no estoque igual em qualquer status. Parece decorativo por opção — inventar um workflow de aprovação de compra seria criar requisito.
- **`venda.parcelas` sem tabela de parcelas**: campo descritivo por decisão do negócio; não propor controle de parcelamento a partir dele.
- **Notificação de WhatsApp só no cadastro da venda, sem status de entrega**: `whatsapp.notificar_venda` é best-effort e uma falha só vira `logger.warning` (whatsapp/core.py:125). Valor baixo enquanto a integração é um aviso de grupo.
- **Paginação nas listagens** (`crud.list_all` em todas as páginas): é escopo de performance, coberto por `0001-analyze-codebase`.
