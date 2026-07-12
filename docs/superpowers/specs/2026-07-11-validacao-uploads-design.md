# Design — Validação de uploads de imagens e documentos

**Data:** 2026-07-11
**Status:** Aprovado
**Escopo:** Validar tipo e tamanho de arquivos em todos os uploads server-side.

## Contexto

O sistema tinha 3 endpoints de upload em `bases/xtreme_system/api/routes/ui.py`,
todos sem qualquer validação server-side de tipo ou tamanho — apenas o atributo
HTML `accept` nos inputs, trivialmente contornável por qualquer cliente.

### Endpoints afetados

| Endpoint | Handler | Arquivos recebidos |
|---|---|---|
| `POST /ui/veiculos/{veiculo_id}/imagens` | `ui_veiculo_imagens_upload` (linha 277) | `imagens: list[UploadFile]` |
| `POST /ui/clientes/{cliente_id}/documentos` | `ui_cliente_documentos_upload` (linha 415) | `documentos: list[UploadFile]` |
| `POST /ui/veiculos` | `_criar_veiculo` (linha 613) | `documentos_cliente` (lista) + `documento_veiculo` (único) via `form.getlist` / `form.get` |

### Requisitos

- Extensões aceitas: `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`.
- Limite por arquivo: 5 MB.
- Limite por request: 20 MB.
- Rejeitar o lote inteiro se qualquer arquivo falharValidação — nenhum arquivo
  é salvo.
- Profundidade da validação: extensão + `content-type` do header (não magic
  bytes). `Content-type` vausente passa; presente e divergente da extensão é
  rejeitado.
- UX de erro: modal re-renderizado com mensagem de erro (modais); `_erro_veiculo`
  para o form de criação de veículo.

## Design

### Constantes

Em `bases/xtreme_system/api/routes/ui.py` (próximo às helpers `_salvar_*`):

```python
_EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
_MAX_POR_ARQUIVO = 5 * 1024 * 1024  # 5 MB
_TIPO_POR_EXTENSAO = {
    ".jpg":  {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png":  {"image/png"},
    ".webp": {"image/webp"},
    ".pdf":  {"application/pdf"},
}
```

Em `bases/xtreme_system/api/setup.py` (ao lado do middleware):

```python
_MAX_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB
```

### Helper de validação (`ui.py`)

```python
def _validar_uploads(arquivos: list[UploadFile]) -> str | None:
    """Retorna mensagem de erro do primeiro arquivo inválido, ou None.

    Lote inteiro é rejeitado no primeiro erro — nenhum arquivo é salvo.
    """
    for arq in arquivos:
        if not arq.filename:
            continue
        ext = Path(arq.filename).suffix.lower()
        if ext not in _EXTENSOES_PERMITIDAS:
            exts = ", ".join(sorted(_EXTENSOES_PERMITIDAS))
            return f"Tipo não permitido: {arq.filename} (aceitos: {exts})"
        ct = (arq.content_type or "").lower()
        if ct and ct not in _TIPO_POR_EXTENSAO[ext]:
            return f"Conteúdo não corresponde à extensão: {arq.filename}"
        tam = arq.size
        if tam is None:
            arq.file.seek(0, 2); tam = arq.file.tell(); arq.file.seek(0)
        if tam > _MAX_POR_ARQUIVO:
            return f"{arq.filename} excede 5 MB ({tam // 1024 // 1024} MB)"
    return None
```

A função não levanta exceções; sempre retorna a primeira mensagem de erro ou
`None`. Os handlers decidem o que fazer com a mensagem.

### Middleware de limite de request (`setup.py`)

Middleware `@app.middleware("http")` separado de `_request_context` (que é
responsabilidade única: request_id + log de erro). Mantém-se separado para não
misturar preocupações — o limite de request édefense no início do pipeline.

```python
@app.middleware("http")
async def _limite_request_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and int(cl) > _MAX_REQUEST_BYTES:
        return Response("Request excede 20 MB", status_code=413)
    return await call_next(request)
```

Roda antes de qualquer handler; rejeita uploads massivos sem desserializar o
multipart.

### Integração nos handlers

Cada handler chama `_validar_uploads` **antes de qualquer mutação de DB**. O
lote é validado completo de uma vez — um único arquivo inválido rejeita tudo.

**`ui_veiculo_imagens_upload`** (modais):

```python
erro = _validar_uploads(imagens)
if erro:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    return templates.TemplateResponse(
        request, "_modal_imagens_veiculo.html",
        {"veiculo": item, "erro": erro}, status_code=400,
    )
# ... loop de save existente (inalterado) ...
```

**`ui_cliente_documentos_upload`** (modais):

```python
erro = _validar_uploads(documentos)
if erro:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    return templates.TemplateResponse(
        request, "_modal_documentos_cliente.html",
        {"cliente": item, "erro": erro}, status_code=400,
    )
_salvar_documentos_cliente(session, cliente_id, documentos)
```

**`_criar_veiculo`** (form): valida `documentos_cliente` e `documento_veiculo`
juntos. A chamada acontece **antes** de `veiculo.create()`, para que um
arquivo inválido não crie um veículo órfão.

```python
documentos = [
    a for a in form.getlist("documentos_cliente")
    if hasattr(a, "filename") and hasattr(a, "file")
]
doc_veiculo = cast(UploadFile | None, form.get("documento_veiculo"))
todos = list(documentos) + ([doc_veiculo] if doc_veiculo else [])
erro = _validar_uploads(todos)
if erro:
    return _erro_veiculo(request, session, erro)
# ... restante do handler inalterado: veiculo.create(), seller, save, compra ...
```

### Templates — bloco de erro

Os dois modais adicionam, logo após `modal__body` (antes da listagem):

```jinja
{% if erro %}<div class="alert alert--error" role="alert">{{ erro }}</div>{% endif %}
```

### Templates — alinhamento do `accept`

O `accept` HTML é só conveniência UX (não barreira de segurança). Ajustar para
refletir o whitelist real:

| Template | De | Para |
|---|---|---|
| `_modal_imagens_veiculo.html` (linha 36) | `image/*` | `.jpg,.jpeg,.png,.webp` |
| `_modal_documentos_cliente.html` (linha 32) | `.pdf,.doc,.docx,.jpg,.jpeg,.png` | `.pdf,.jpg,.jpeg,.png,.webp` |
| `_form_veiculo.html` (4 ocorrências) | `image/*,.pdf` | `.jpg,.jpeg,.png,.webp,.pdf` |
| `_midia_veiculo.html` (linha 17) | `image/*` | `.jpg,.jpeg,.png,.webp` |
| `_midia_veiculo.html` (linha 35) | (nenhum) | `.pdf,.jpg,.jpeg,.png,.webp` |

### Bug pre-existente — fora de escopo

`_midia_veiculo.html` tem dois forms que postam para `/ui/veiculos/{id}/imagens`
e `/ui/veiculos/{id}/documentos` com `name="arquivo"`. O segundo route **não
existe** (404), e o primeiro espera `name="imagens"` — esses forms estão
funcionalmente quebrados hoje. Conforme AGENTS.md §3 ("Don't fix unrelated
broken code unless asked"), apenas documentado; não será corrigido nesta tarefa.
A validação server-side não os protege porque o route atual nem processa esses
uploads.

## Error handling

| Caso | Status | Apresentação |
|---|---|---|
| Extensão inválida | 400 | Modal re-renderizado com `alert--error` (modais) ou `_erro_veiculo` (form) |
| content-type divergente da extensão | 400 | idem |
| Arquivo > 5 MB | 400 | idem |
| Request > 20 MB | 413 | Middleware retorna direto, handler não é invocado |

## Fluxo

```
Request (multipart)
  │
  ▼
  _limite_request_size middleware
  │  Content-Length > 20 MB? → 413 (Response direta)
  │
  ▼
  handler de upload
  │  _validar_uploads(arquivos) → mensagem?
  │     sim  → renderiza modal/form com erro, status 400
  │     não  → _salvar_* / inline save
  │
  ▼
  Modal/form de sucesso (inalterado)
```

## Testes

Em `tests/test_ui.py` (que já cobre happy paths de upload):

1. **Unitário `_validar_uploads`:**
   - Extensão inválida (`.gif`, `.txt`, `.doc`) retorna mensagem.
   - Extensão válida (`.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`) retorna `None`.
   - content-type divergente (`.jpg` + `application/pdf`) retorna mensagem.
   - content-type vazio passa.
   - Arquivo > 5 MB retorna mensagem.
2. **`POST /ui/veiculos/{id}/imagens` com `.gif`:** status 400, "Tipo não
   permitido" no corpo, nenhum arquivo salvo no filesystem.
3. **`POST /ui/clientes/{id}/documentos` com `.txt`:** status 400, erro no
   modal.
4. **Regressão:** uploads válidos (.jpg, .png, .webp, .pdf) continuam
   funcionando (testes existentes permanecem verdes).
5. **Middleware:** POST com Content-Length > 20 MB retorna 413.

## Fora de escopo

- Detecção por magic bytes / assinatura de arquivo (decisão: extensão +
  content-type é suficiente para uso interno).
- Novo endpoint JSON de upload (não existe).
- Componente Polylith de uploads (YAGNI — a validação é específica da UI; se
  uploads JSON surgirem, a função `_validar_uploads` serve sem alteração).
- Correção dos forms quebrados em `_midia_veiculo.html` (pre-existente).
