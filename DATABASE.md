# DATABASE.md

Documentação do schema do banco de dados do Xtreme System.

## Visão geral

O banco utiliza SQLAlchemy + Alembic (migrations em `alembic/versions/`). Abaixo estão as tabelas, colunas, enums, índices e relacionamentos atuais.

---

## Enums

| Nome | Valores | Uso |
|------|---------|-----|
| `tipoveiculo` | `moto`, `carro` | `veiculo.tipo` |
| `statusveiculo` | `disponivel`, `vendido`, `reservado` | `veiculo.status` |
| `tipocliente` | `pessoa_fisica`, `pessoa_juridica` | `cliente.tipo` |
| `statusvenda` | `pendente`, `aprovado`, `cancelado`, `concluido` | `venda.status` |
| `papel` | `admin`, `funcionario` | `usuario.papel` |
| `tipolancamento` | `aporte`, `custo`, `receita_venda`, `distribuicao_lucro` | `lancamento_investimento.tipo` |
| `origemlancamento` | `manual`, `veiculo`, `fechamento_venda` | `lancamento_investimento.origem` |

---

## Tabelas

### `investidor`

Cadastro de investidores.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `nome` | `VARCHAR` | Não | - | Único, indexado |

### `veiculo`

Veículos disponíveis para venda.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `tipo` | `tipoveiculo` | Não | - | `moto` ou `carro` |
| `modelo` | `VARCHAR` | Não | - | |
| `cor` | `VARCHAR` | Não | - | |
| `ano` | `INTEGER` | Não | - | |
| `placa` | `VARCHAR` | Não | - | Único, indexado |
| `km` | `INTEGER` | Não | - | |
| `preco` | `NUMERIC(12,2)` | Não | - | |
| `procuracao` | `VARCHAR` | Sim | - | |
| `status` | `statusveiculo` | Não | `disponivel` | `disponivel`, `vendido`, `reservado` |
| `investidor_id` | `INTEGER` | Não | - | FK → `investidor.id` (CASCADE) |

### `cliente`

Clientes do sistema.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `nome` | `VARCHAR` | Não | - | Indexado |
| `documento` | `VARCHAR` | Não | - | Único, indexado |
| `tipo` | `tipocliente` | Não | - | `pessoa_fisica` ou `pessoa_juridica` |
| `email` | `VARCHAR` | Sim | - | |
| `telefone` | `VARCHAR` | Sim | - | |
| `endereco` | `VARCHAR` | Sim | - | |
| `cidade` | `VARCHAR` | Sim | - | |
| `estado` | `VARCHAR` | Sim | - | |
| `cep` | `VARCHAR` | Sim | - | |

### `usuario`

Usuários do sistema para autenticação e controle de acesso.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `username` | `VARCHAR` | Não | - | Único, indexado |
| `senha_hash` | `VARCHAR` | Não | - | Hash da senha |
| `papel` | `papel` | Não | `funcionario` | `admin` ou `funcionario` |
| `ativo` | `BOOLEAN` | Não | `true` | |

### `venda`

Registro de vendas de veículos.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `cliente_id` | `INTEGER` | Não | - | FK → `cliente.id` (CASCADE), indexado |
| `veiculo_id` | `INTEGER` | Não | - | FK → `veiculo.id` (CASCADE), indexado |
| `vendedor_id` | `INTEGER` | Sim | - | FK → `usuario.id` (SET NULL), indexado |
| `data_venda` | `DATE` | Sim | - | |
| `valor_venda` | `NUMERIC(12,2)` | Não | - | |
| `valor_entrada` | `NUMERIC(12,2)` | Sim | - | |
| `debitos` | `NUMERIC(12,2)` | Sim | - | |
| `km` | `INTEGER` | Sim | - | Quilometragem do veículo no momento da venda |
| `forma_pagamento` | `VARCHAR` | Não | - | |
| `parcelas` | `INTEGER` | Não | - | |
| `status` | `statusvenda` | Não | `pendente` | `pendente`, `aprovado`, `cancelado`, `concluido` |
| `observacoes` | `VARCHAR` | Sim | - | |
| `veiculo_troca_id` | `INTEGER` | Sim | - | FK → `veiculo.id`, indexado; presença indica troca |
| `valor_diferenca` | `NUMERIC(12,2)` | Sim | - | Valor da diferença na troca |
| `pagamento_pendente` | `BOOLEAN` | Não | `false` | Indica se faltou parte do pagamento |
| `valor_pendente` | `NUMERIC(12,2)` | Sim | - | Valor que ficou pendente |
| `datas_pagamento` | `VARCHAR` | Sim | - | Datas de pagamento em texto livre |

### `imagem_veiculo`

Imagens associadas a um veículo.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `veiculo_id` | `INTEGER` | Não | - | FK → `veiculo.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL da imagem |

### `imagem_comprovante_venda`

Imagens de comprovantes associados a uma venda.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `venda_id` | `INTEGER` | Não | - | FK → `venda.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL da imagem |

### `documento_contrato_venda`

Contratos de venda gerados em PDF.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `venda_id` | `INTEGER` | Não | - | FK → `venda.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL do PDF do contrato |

### `compra`

Registro de compras de veículos.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `cliente_id` | `INTEGER` | Não | - | FK → `cliente.id` (CASCADE), indexado |
| `veiculo_id` | `INTEGER` | Não | - | FK → `veiculo.id` (CASCADE), indexado |
| `data_compra` | `DATE` | Não | - | |
| `valor_compra` | `NUMERIC(12,2)` | Não | - | |
| `debitos` | `NUMERIC(12,2)` | Sim | - | |
| `observacoes` | `VARCHAR` | Sim | - | |

### `custo_veiculo`

Custos operacionais associados a veículos. Esses registros não alteram saldo de investidor.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `veiculo_id` | `INTEGER` | Não | - | FK → `veiculo.id` (CASCADE), indexado |
| `categoria` | `VARCHAR` | Não | - | Texto livre |
| `descricao` | `VARCHAR` | Sim | - | |
| `valor` | `NUMERIC(12,2)` | Não | - | Validado pela aplicação como `> 0` |
| `data_custo` | `DATE` | Não | - | |
| `criado_em` | `DATETIME` | Não | `now()` | |

### `documento_veiculo`

Documentos associados a um veículo.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `veiculo_id` | `INTEGER` | Não | - | FK → `veiculo.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL do documento |

### `lancamento_investimento`

Lançamentos financeiros de aportes e custos dos investidores.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `investidor_id` | `INTEGER` | Não | - | FK → `investidor.id` (CASCADE), indexado |
| `veiculo_id` | `INTEGER` | Sim | - | FK → `veiculo.id` (CASCADE), indexado, único |
| `fechamento_venda_id` | `INTEGER` | Sim | - | FK → `fechamento_venda.id` (CASCADE), indexado |
| `tipo` | `tipolancamento` | Não | - | `aporte`, `custo`, `receita_venda` ou `distribuicao_lucro` |
| `origem` | `origemlancamento` | Não | `manual` | `manual`, `veiculo` ou `fechamento_venda` |
| `valor` | `NUMERIC(12,2)` | Não | - | |
| `descricao` | `VARCHAR` | Não | - | |
| `criado_em` | `DATETIME` | Não | `now()` | |

### `fechamento_venda`

Fechamento financeiro imutável de uma venda concluída.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `venda_id` | `INTEGER` | Não | - | FK → `venda.id` (CASCADE), único, indexado |
| `usuario_id` | `INTEGER` | Sim | - | FK → `usuario.id`, indexado |
| `data_fechamento` | `DATE` | Não | `current_date` | |
| `receita` | `NUMERIC(12,2)` | Não | - | Snapshot de `venda.valor_venda` |
| `custo_veiculo` | `NUMERIC(12,2)` | Não | - | Snapshot de `veiculo.preco` |
| `custos_operacionais` | `NUMERIC(12,2)` | Não | - | Soma de `custo_veiculo.valor` no fechamento |
| `debitos` | `NUMERIC(12,2)` | Não | - | Snapshot de `venda.debitos`, com nulo como `0` |
| `lucro_liquido` | `NUMERIC(12,2)` | Não | - | Receita menos custo do veículo, custos e débitos |

### `participacao_fechamento_venda`

Rateio manual do lucro positivo de um fechamento.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `fechamento_venda_id` | `INTEGER` | Não | - | FK → `fechamento_venda.id` (CASCADE), indexado |
| `investidor_id` | `INTEGER` | Não | - | FK → `investidor.id`, indexado |
| `percentual` | `NUMERIC(5,2)` | Não | - | Percentual manual do lucro |
| `valor` | `NUMERIC(12,2)` | Não | - | Valor calculado do lucro no fechamento |

### `imagem_documento_cliente`

Imagens de documentos associados a um cliente.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `cliente_id` | `INTEGER` | Não | - | FK → `cliente.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL da imagem |

### `imagem_comprovante_compra`

Imagens de comprovantes de pagamento associados a uma compra.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `compra_id` | `INTEGER` | Não | - | FK → `compra.id` (CASCADE), indexado |
| `url` | `VARCHAR` | Não | - | URL da imagem |

### `whatsapp_config`

Configuração da notificação de vendas via WhatsApp (Evolution API). Linha única (`id` fixo em `1`), editável na tela de Configurações.

| Coluna | Tipo | Nullable | Default | Observações |
|--------|------|----------|---------|-------------|
| `id` | `INTEGER` | Não | - | PK |
| `evolution_api_url` | `VARCHAR` | Não | `''` | URL do servidor Evolution API |
| `evolution_api_key` | `VARCHAR` | Não | `''` | API key da instância |
| `evolution_instance` | `VARCHAR` | Não | `''` | Nome da instância |
| `evolution_group_id` | `VARCHAR` | Não | `''` | ID do grupo do WhatsApp |
| `mensagem_template` | `VARCHAR` | Não | template padrão | Corpo da mensagem enviada na notificação de venda, com placeholders `{cliente}`, `{veiculo}`, `{valor}`, `{forma_pagamento}`, `{parcelas}`, `{vendedor}` |

---

## Relacionamentos

- Um **investidor** pode ter vários **veículos**.
- Um **veículo** pode ter várias **imagens** e **documentos**.
- Um **veículo** pode ter no máximo um **lancamento_investimento** (`veiculo_id` é único).
- Um **cliente** pode ter várias **vendas**.
- Um **cliente** pode ter várias **compras**.
- Um **cliente** pode ter várias **imagens de documentos**.
- Um **veículo** pode estar em várias **vendas** (historicamente) — controle de status via aplicação.
- Um **veículo** pode estar em várias **compras** (historicamente).
- Um **veículo** pode ter vários **custos operacionais**.
- Um **usuário** (vendedor) pode estar em várias **vendas**.
- Uma **venda** pode ter vários **comprovantes**.
- Uma **venda** pode ter vários **contratos** (PDF gerado ao concluir a venda).
- Uma **venda** pode ter no máximo um **fechamento de venda**.
- Um **fechamento de venda** pode ter várias **participações de investidores**.
- Um **fechamento de venda** gera lançamentos automáticos em `lancamento_investimento`.
- Uma **compra** pode ter vários **comprovantes de pagamento**.

---

## Índices

| Tabela | Índice | Coluna(s) | Único |
|--------|--------|-----------|-------|
| `investidor` | `ix_investidor_nome` | `nome` | Sim |
| `veiculo` | `ix_veiculo_placa` | `placa` | Sim |
| `veiculo` | `ix_veiculo_investidor_id` | `investidor_id` | Não |
| `cliente` | `ix_cliente_documento` | `documento` | Sim |
| `cliente` | `ix_cliente_nome` | `nome` | Não |
| `usuario` | `ix_usuario_username` | `username` | Sim |
| `venda` | `ix_venda_cliente_id` | `cliente_id` | Não |
| `venda` | `ix_venda_veiculo_id` | `veiculo_id` | Não |
| `venda` | `ix_venda_vendedor_id` | `vendedor_id` | Não |
| `venda` | `ix_venda_veiculo_troca_id` | `veiculo_troca_id` | Não |
| `imagem_veiculo` | `ix_imagem_veiculo_veiculo_id` | `veiculo_id` | Não |
| `documento_veiculo` | `ix_documento_veiculo_veiculo_id` | `veiculo_id` | Não |
| `imagem_comprovante_venda` | `ix_imagem_comprovante_venda_venda_id` | `venda_id` | Não |
| `documento_contrato_venda` | `ix_documento_contrato_venda_venda_id` | `venda_id` | Não |
| `compra` | `ix_compra_cliente_id` | `cliente_id` | Não |
| `compra` | `ix_compra_veiculo_id` | `veiculo_id` | Não |
| `custo_veiculo` | `ix_custo_veiculo_veiculo_id` | `veiculo_id` | Não |
| `lancamento_investimento` | `ix_lancamento_investimento_investidor_id` | `investidor_id` | Não |
| `lancamento_investimento` | `ix_lancamento_investimento_veiculo_id` | `veiculo_id` | Sim |
| `lancamento_investimento` | `ix_lancamento_investimento_fechamento_venda_id` | `fechamento_venda_id` | Não |
| `fechamento_venda` | `ix_fechamento_venda_venda_id` | `venda_id` | Sim |
| `fechamento_venda` | `ix_fechamento_venda_usuario_id` | `usuario_id` | Não |
| `participacao_fechamento_venda` | `ix_participacao_fechamento_venda_fechamento_venda_id` | `fechamento_venda_id` | Não |
| `participacao_fechamento_venda` | `ix_participacao_fechamento_venda_investidor_id` | `investidor_id` | Não |
| `participacao_fechamento_venda` | `uq_participacao_fechamento_investidor` | `fechamento_venda_id`, `investidor_id` | Sim |
| `imagem_documento_cliente` | `ix_imagem_documento_cliente_cliente_id` | `cliente_id` | Não |
| `imagem_comprovante_compra` | `ix_imagem_comprovante_compra_compra_id` | `compra_id` | Não |
