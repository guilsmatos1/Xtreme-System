# Polylith CLI no projeto Xtreme Motors

O `polylith-cli` ajuda a inspecionar e manter o workspace Polylith do projeto.

## Comandos mais úteis

### `uv run poly info`
Mostra o resumo do workspace:
- quantidade de `projects`, `components`, `bases` e `development`
- quais bricks existem
- quais estão montados no projeto `inventory_api`

### `uv run poly check`
Valida a organização do workspace.
Use para detectar bricks não montados, dependências faltando ou drift de configuração.

### `uv run poly deps --brick <brick>`
Mostra as dependências de um brick específico.
Use antes de mexer em um componente para entender impacto e acoplamento.

### `uv run poly diff`
Mostra quais bricks mudaram em relação ao último git tag.
Útil antes de abrir PR ou revisar o que precisa de teste.

### `uv run poly test diff`
Mostra quais projetos e bricks foram afetados por mudanças em testes.

### `uv run poly sync`
Sincroniza o `pyproject.toml` com os bricks do workspace.
Use ao criar ou remover componentes/bases.

### `uv run poly create ...`
Cria novos bricks ou projetos seguindo o padrão Polylith.

## Fluxo prático

1. Antes de editar um brick: `uv run poly deps --brick <brick>`
2. Depois das mudanças: `uv run poly check`
3. Antes do PR: `uv run poly diff`
4. Ao adicionar/remover bricks: `uv run poly sync`

## Observação do repositório

No estado atual, `uv run poly check` apontou bricks que existem no workspace, mas não estão montados em `inventory_api`.
Isso pode ser esperado se esses bricks ainda não forem usados pelo app.
