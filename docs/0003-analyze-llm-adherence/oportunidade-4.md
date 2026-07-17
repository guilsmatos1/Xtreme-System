## Opportunity 4: `ordenar_investidores` com quatro dicts posicionais de mesma forma

File: bases/xtreme_system/api/routes/ui_routes/investidores.py (linhas 30-66)

Problem:
`ordenar_investidores` recebe `saldos`, `num_veiculos`, `valor_veiculos` e
`total_aportado` — quatro `dict[int, ...]` indexados por `investidor.id`,
todos com a mesma forma estrutural (métrica por investidor), passados
posicionalmente. Não há um tipo que agregue "as métricas de um
investidor"; o único chamador (`_ctx_investidores`, linha 78) já monta esses
quatro dicts separadamente a partir de `caixa.saldos` e
`caixa.agregados_investidores`, e os repassa na mesma ordem posicional.

LLM Risk:
Ao adicionar uma nova métrica ordenável (ex.: "última movimentação"), a
extensão natural é acrescentar mais um parâmetro `dict[int, ...]` na mesma
posição relativa — um agente tem 4 dicts de tipo idêntico (`dict[int, X]`)
para posicionar corretamente por nome de parâmetro, sem que o type checker
acuse erro se a ordem for trocada (todos aceitam a mesma forma genérica de
dict). Um erro de ordem (ex.: passar `valor_veiculos` no lugar de
`total_aportado`) não quebra a assinatura, apenas produz ordenação errada
silenciosa na UI.

Action:
Agregar as quatro métricas num único `dataclass` (ou `TypedDict`) mantido
por `investidor_id`, e ordenar por atributo nomeado em vez de dict externo
combinado com `sort` string. Não é necessário refatorar `caixa.saldos`/
`caixa.agregados_investidores` — a agregação pode acontecer em
`_ctx_investidores`, antes da chamada.

Suggested Interface:
```python
@dataclass
class MetricasInvestidor:
    saldo: Decimal
    num_veiculos: int
    valor_veiculos: Decimal
    total_aportado: Decimal

def ordenar_investidores(
    investidores: list[investidor.Investidor],
    metricas: dict[int, MetricasInvestidor],
    sort: str,
    order: str,
) -> list[investidor.Investidor]:
    ...
    key=lambda item: getattr(metricas.get(item.id, MetricasInvestidor(...)), sort)
```

Tests:
Teste unitário de `ordenar_investidores` cobrindo cada valor de `sort`
("nome", "saldo", "num_veiculos", "valor_veiculos", "total_investido") com
`order="asc"`/`"desc"`, incluindo o caso de investidor ausente de
`metricas` (fallback para zero).

Success Metric:
Adicionar uma nova métrica ordenável passa a exigir apenas um novo campo em
`MetricasInvestidor` e um novo `if sort == "..."`, sem tocar na assinatura
posicional de `ordenar_investidores` nem no call site em
`_ctx_investidores`.
