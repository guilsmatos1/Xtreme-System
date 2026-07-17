# Análise de LLM-Adherence — xtreme-system

Codebase Polylith (FastAPI/HTMX) bem estratificado: `route_factories.py` e
`crud_ui/routes.py`, apesar de extensos em linhas, já são decompostos em
funções `register_*_route` de responsabilidade única — não representam risco
real de monólito. A separação de validação descrita no CLAUDE.md (invariantes
de negócio em `core.py`, checagem de FK em `workflows.py`, 400/409 nas rotas)
é respeitada de forma consistente. Os imports diferidos em `perfil.core` para
evitar ciclo com `usuario.core` são intencionais e comentados — não são leaks.

Foram identificadas 4 oportunidades de alta confiança, priorizadas por risco
de edição por LLM:

1. **Encapsulation leak** — `auditoria.core._snapshot` (nome privado) é
   importado diretamente por 4 outros componentes.
2. **Duplicação exata** — `_resolver_cliente` está copiado byte-a-byte entre
   `vendas.py` e `compras.py`.
3. **Concerns misturados + risco de atomicidade** — `_criar_venda` e
   `_criar_compra` escrevem arquivo em disco antes do commit real da
   transação (que só ocorre em `get_session`, fora do handler), permitindo
   arquivo órfão se o commit falhar depois do handler retornar.
4. **Contrato ausente** — `ordenar_investidores` recebe 4 parâmetros
   `dict[int, ...]` posicionais de mesmo formato, sem agregação tipada.

Itens considerados e descartados por serem estilísticos ou já bem
resolvidos: tamanho de `crud_ui/routes.py`/`route_factories.py`, classe de
rate limiter em `setup.py`, imports diferidos repetidos de `is_admin` em
`perfil.core`.

Arquivos com oportunidades:
- [Oportunidade 1](oportunidade-1.md) — `auditoria.core._snapshot` exposto como API pública informal
- [Oportunidade 2](oportunidade-2.md) — `_resolver_cliente` duplicado em vendas.py/compras.py
- [Oportunidade 3](oportunidade-3.md) — persistência de arquivo antes do commit real em `_criar_venda`/`_criar_compra`
- [Oportunidade 4](oportunidade-4.md) — `ordenar_investidores` com dicts posicionais sem contrato
