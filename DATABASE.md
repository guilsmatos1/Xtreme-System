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
| `tipolancamento` | `aporte`, `custo` | `lancamento_investimento.tipo` |
| `origemlancamento` | `manual`, `veiculo` | `lancamento_investimento.origem` |

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
| `tipo` | `tipolancamento` | Não | - | `aporte` ou `custo` |
| `origem` | `origemlancamento` | Não | `manual` | `manual` ou `veiculo` |
| `valor` | `NUMERIC(12,2)` | Não | - | |
| `descricao` | `VARCHAR` | Não | - | |
| `criado_em` | `DATETIME` | Não | `now()` | |

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
- Um **usuário** (vendedor) pode estar em várias **vendas**.
- Uma **venda** pode ter vários **comprovantes**.
- Uma **venda** pode ter vários **contratos** (PDF gerado ao concluir a venda).
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
| `imagem_veiculo` | `ix_imagem_veiculo_veiculo_id` | `veiculo_id` | Não |
| `documento_veiculo` | `ix_documento_veiculo_veiculo_id` | `veiculo_id` | Não |
| `imagem_comprovante_venda` | `ix_imagem_comprovante_venda_venda_id` | `venda_id` | Não |
| `documento_contrato_venda` | `ix_documento_contrato_venda_venda_id` | `venda_id` | Não |
| `compra` | `ix_compra_cliente_id` | `cliente_id` | Não |
| `compra` | `ix_compra_veiculo_id` | `veiculo_id` | Não |
| `lancamento_investimento` | `ix_lancamento_investimento_investidor_id` | `investidor_id` | Não |
| `lancamento_investimento` | `ix_lancamento_investimento_veiculo_id` | `veiculo_id` | Sim |
| `imagem_documento_cliente` | `ix_imagem_documento_cliente_cliente_id` | `cliente_id` | Não |
| `imagem_comprovante_compra` | `ix_imagem_comprovante_compra_compra_id` | `compra_id` | Não |
