# API - Xtreme Motors

## Overview

The Xtreme Motors API is built with FastAPI and provides JSON endpoints for managing investors, vehicles, clients, purchases, sales, and financial tracking. The API uses token-based authentication (JWT) and includes both a JSON API layer and a separate server-rendered UI layer (HTMX).

**Base URL**: `http://localhost:8000` (development)

## Health Check

Health check para Docker/k8s — sem autenticação.

**Endpoint**: `GET /health`

Response (200):

```json
{
  "status": "ok",
  "database": "ok"
}
```

Response (503) — banco indisponível:

```json
{
  "status": "degradado",
  "database": "indisponivel"
}
```

**Status Codes**:

- `200`: Aplicação e banco disponíveis
- `503`: Banco indisponível

---

## Rate Limiting

Limites em memória por IP:

- `POST /login` e `POST /ui/login`: 5 tentativas/minuto
- Demais rotas: 100 requests/minuto (exceto `/health`, `/docs`, `/redoc`, `/openapi.json` e arquivos estáticos)

Ao exceder o limite, retorna `429` com header `Retry-After` (segundos). Corpo `{"detail": "..."}` para rotas JSON, HTML para rotas `/ui/`.

---

## Authentication

### Login

**Endpoint**: `POST /login`

Request:

```json
{
  "username": "string",
  "password": "string"
}
```

Response:

```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Status Codes**:

- `200`: Login successful
- `401`: Invalid username or password

---

## User Management

**Requires**: Admin role

### Create User

**Endpoint**: `POST /usuarios`

Request:

```json
{
  "username": "string",
  "senha": "string",
  "papel": "admin|funcionario",
  "perfil_id": 1
}
```

Response: User object (201 Created, inclui `perfil_id`)

**Status Codes**:

- `201`: User created
- `400`: Username already exists
- `401`: Unauthorized
- `403`: Requires admin role

### List Users

**Endpoint**: `GET /usuarios`

Response: Array of user objects (inclui `perfil_id`)

**Status Codes**:

- `200`: Success
- `401`: Unauthorized
- `403`: Requires admin role

### Delete User

**Endpoint**: `DELETE /usuarios/{user_id}`

Response: No content (204)

**Status Codes**:

- `204`: User deleted
- `400`: Cannot delete own account
- `401`: Unauthorized
- `403`: Requires admin role
- `404`: User not found

### Change Password

**Endpoint**: `POST /usuarios/{user_id}/senha`

Request (form data):

```
nova_senha=string
```

Response: No content (204)

**Status Codes**:

- `204`: Password changed
- `401`: Unauthorized
- `403`: Requires admin role
- `404`: User not found

---

## CRUD Resources

The following resources are managed through a generic CRUD interface. Each resource supports standard HTTP operations.

### Available Resources

- **Investidores** - Investors/Fundholders
- **Veículos** - Vehicles (investment vehicles)
- **Lançamentos de Caixa** - Financial transactions
- **Clientes** - Clients/Customers
- **Compras** - Purchases
- **Vendas** - Sales

### CRUD Operations

For each resource, replace `{resource}` with one of:

- `investidores`
- `veiculos`
- `lancamentos-caixa`
- `clientes`
- `compras`
- `vendas`

#### List Resources

**Endpoint**: `GET /{resource}`

Response: Array of resource objects

**Permissions**: Requires authentication (any role)

#### Get Single Resource

**Endpoint**: `GET /{resource}/{item_id}`

Response: Single resource object

**Permissions**: Requires authentication (any role)

**Status Codes**:

- `200`: Success
- `404`: Resource not found

#### Create Resource

**Endpoint**: `POST /{resource}`

Request: Resource creation schema (JSON)

Response: Created resource object (201 Created)

**Permissions**: Requires admin role

**Status Codes**:

- `201`: Created
- `400`: Invalid data or constraint violation
- `401`: Unauthorized
- `403`: Requires admin role
- `409`: Conflict (e.g., duplicate entry)

#### Update Resource

**Endpoint**: `PATCH /{resource}/{item_id}`

Request: Resource update schema (JSON, partial fields)

Response: Updated resource object

**Permissions**: Requires admin role

**Status Codes**:

- `200`: Success
- `400`: Invalid data
- `401`: Unauthorized
- `403`: Requires admin role
- `404`: Resource not found
- `409`: Conflict

#### Delete Resource

**Endpoint**: `DELETE /{resource}/{item_id}`

Response: No content (204)

**Permissions**: Requires admin role

**Status Codes**:

- `204`: Deleted
- `401`: Unauthorized
- `403`: Requires admin role
- `404`: Resource not found
- `409`: Conflict (resource has dependencies)

---

## Resource-Specific Notes

### Veículos (Vehicles)

**Validation**:

- `placa` (license plate) must be unique
- `investidor_id` must reference an existing investor

**Side Effects**:

- Creating a vehicle triggers automatic financial transaction creation
- Updating a vehicle syncs related financial transactions
- Cannot delete if related financial transactions exist

### Lançamentos de Caixa (Financial Transactions)

**Validation**:

- `investidor_id` must reference an existing investor

**Constraints**:

- Vehicle-originated transactions can only be modified via the vehicle management interface

### Clientes (Clients)

**Operations**: Full CRUD

### Vendas (Sales)

**Validation**:

- `cliente_id` (if provided) must reference an existing client
- `veiculo_id` (if provided) must reference an existing vehicle

### Fechamento de Vendas

Fechamentos são registros financeiros imutáveis de vendas concluídas e sem
pagamento pendente.

#### Preview

**Endpoint**: `GET /vendas/{venda_id}/fechamento/preview`

**Permissions**: Requires authentication (any role)

Response:

```json
{
  "elegivel": true,
  "motivo": null,
  "ja_fechada": false,
  "receita": "60000.00",
  "custo_veiculo": "40000.00",
  "custos_operacionais": "1500.00",
  "debitos": "500.00",
  "lucro_liquido": "18000.00",
  "investidores": []
}
```

#### Confirmar fechamento

**Endpoint**: `POST /vendas/{venda_id}/fechamento`

**Permissions**: Requires admin role

Request:

```json
{
  "participacoes": [
    {"investidor_id": 1, "percentual": "60.00"},
    {"investidor_id": 2, "percentual": "40.00"}
  ]
}
```

Rules:

- `lucro_liquido = venda.valor_venda - veiculo.preco - custos_operacionais - debitos`
- `debitos` nulo conta como `0`
- venda precisa estar com `status = concluido` e `pagamento_pendente = false`
- uma venda pode ter apenas um fechamento
- se o lucro for positivo, as participações devem somar `100%`
- se o lucro for zero ou negativo, o fechamento cria somente a receita da venda

Side effects:

- cria `receita_venda` para o investidor principal do veículo
- cria `distribuicao_lucro` para cada participação quando há lucro positivo
- lançamentos com origem `fechamento_venda` não podem ser editados pelos endpoints manuais de caixa

#### Consulta

**Endpoints**:

- `GET /fechamentos-vendas`
- `GET /fechamentos-vendas/{id}`

### Compras (Purchases)

**Validation**:

- `cliente_id` (if provided) must reference an existing client
- `veiculo_id` (if provided) must reference an existing vehicle
- `status` defaults to `pendente`

### Auditoria

**Endpoint**: `GET /auditoria`

**Permissions**: Requires admin role

---

## Response Format

All successful responses return either:

- **Single object**: Resource representation
- **Array**: List of resource representations
- **No content**: 204 status with empty body

Error responses:

```json
{
  "detail": "Error message"
}
```

---

## Status Codes Reference


| Code | Meaning                                                |
| ---- | ------------------------------------------------------ |
| 200  | OK - Request successful                                |
| 201  | Created - Resource created                             |
| 204  | No Content - Success with no response body             |
| 400  | Bad Request - Invalid input or constraint violation    |
| 401  | Unauthorized - Missing or invalid authentication       |
| 403  | Forbidden - Insufficient permissions                   |
| 404  | Not Found - Resource does not exist                    |
| 409  | Conflict - Data conflict (duplicate, dependency error) |
| 429  | Too Many Requests - Rate limit exceeded                |


---

## Authorization

**Roles**:

- `admin` - Full access to JSON write endpoints and admin-only queries
- `funcionario` (employee) - Read-only access to JSON endpoints; access to the UI depends on the assigned `perfil`

**Header**:

```
Authorization: Bearer {access_token}
```

---

## UI Layer

In addition to the JSON API, the application provides a server-rendered HTML UI with HTMX for dynamic interactions. The UI is accessible at the root path (`/`) and authenticated via HTTP-only cookies.

**Note**: The UI reuses the same JWT in an HTTP-only cookie and applies page access rules based on the user's `perfil`. Beyond pages, a `perfil` can also restrict specific fields (hidden in the UI, denylist — visible by default) and write operations (allowlist — denied by default for non-admins) on a per-page basis via `Perfil.restricoes`. Applied across all 6 pages (`veiculos`, `investidores`, `clientes`, `compras`, `custos-veiculos`, `vendas`), including page-specific operations like `excluir_comprovante`, `excluir_documento`, and `fechar` (venda closing, which also hides profit/investor-payout fields). In `veiculos`, the restricted field catalog includes `preco`, `investidor`, `revisao`, and `debitos`.
