# Validação de Uploads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate file type and size on all image/document uploads server-side; accept only `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`; max 5 MB per file, 20 MB per request.

**Architecture:** A pure helper `_validar_uploads` in `ui.py` checks extension + content-type + per-file size and returns the first error message or `None`. A new middleware in `setup.py` rejects requests with `Content-Length > 20 MB` (413). The 3 upload handlers call `_validar_uploads` before any DB mutation and re-render the modal/form with an error alert on failure. Templates get a consistent `accept` attribute matching the whitelist.

**Tech Stack:** Python 3.12+, FastAPI, Starlette middleware, Jinja2, pytest with TestClient.

## Global Constraints

- Whitelist of extensions (exact set): `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`.
- Per-file limit: 5 MB (5 * 1024 * 1024 bytes).
- Per-request limit: 20 MB (20 * 1024 * 1024 bytes), enforced via `Content-Length` header in middleware.
- content-type validation: when present, must match the allowed types for the given extension; when absent, the file passes this check (extension alone is sufficient).
- Batch behavior: if any file in a request fails validation, reject the entire batch — no partial saves.
- Error presentation: modals re-render with `ui.alert(erro)` block at the top; the vehicle creation form uses the existing `_erro_veiculo` helper. Status code 400 for validation failures, 413 for the request-size middleware.
- No new dependencies. No new Polylith component — validation lives in the API layer (`bases`).
- Lint: `make lint` (ruff check, ruff format --check, xenon, vulture, mypy) must pass.
- Tests: `make test` must pass; the new tests must run with existing fixtures (no new fixture required).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `bases/xtreme_system/api/routes/ui.py` | Modify | Add constants, `_validar_uploads` helper, wire validation into 3 handlers |
| `bases/xtreme_system/api/setup.py` | Modify | Add `_MAX_REQUEST_BYTES` constant and `_limite_request_size` middleware |
| `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html` | Modify | Add `erro` alert block; align `accept` attribute |
| `bases/xtreme_system/api/templates/_modal_documentos_cliente.html` | Modify | Add `erro` alert block; align `accept` attribute |
| `bases/xtreme_system/api/templates/_form_veiculo.html` | Modify | Align 4 `accept` attributes |
| `bases/xtreme_system/api/templates/_midia_veiculo.html` | Modify | Align 2 `accept` attributes |
| `tests/test_ui.py` | Modify | Add unit tests for `_validar_uploads`, integration tests for rejected uploads and the 413 middleware |

---

## Task 1: Helper `_validar_uploads` + constants

**Files:**
- Modify: `bases/xtreme_system/api/routes/ui.py` (near the existing `_uploads_dir` / `_salvar_*` helpers, after line 246)
- Test: `tests/test_ui.py` (new tests at the end of the file)

**Interfaces:**
- Consumes: `UploadFile` (already imported at `ui.py:11`), `Path` (already imported at `ui.py:6`).
- Produces:

```python
_EXTENSOES_PERMITIDAS: set[str]   # {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
_MAX_POR_ARQUIVO: int             # 5 * 1024 * 1024
def _validar_uploads(arquivos: list[UploadFile]) -> str | None: ...
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui.py` (after the last existing test, before the `_admin_headers` helper if placed at end — place at the very end of the file):

```python
from xtreme_system.api.routes.ui import _validar_uploads


class _FakeUpload:
    """Minimal UploadFile-like stub for unit tests (no network, no spooled file)."""

    def __init__(self, filename: str, content_type: str | None, size: int | None):
        self.filename = filename
        self.content_type = content_type
        self._size = size
        self.file = _FakeFile(size or 0)

    @property
    def size(self) -> int | None:
        return self._size


class _FakeFile:
    def __init__(self, size: int):
        self._size = size
        self._pos = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 2:
            self._pos = self._size + offset
        else:
            self._pos = offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, _n: int = -1) -> bytes:
        return b""


def test_validar_uploads_extensao_invalida() -> None:
    arq = _FakeUpload("malicioso.gif", "image/gif", 100)
    msg = _validar_uploads([arq])
    assert msg is not None
    assert "Tipo não permitido" in msg
    assert ".gif" in msg


def test_validar_uploads_extensao_valida_passa() -> None:
    for nome, ct in [
        ("foto.jpg", "image/jpeg"),
        ("foto.JPEG", "image/jpeg"),
        ("diagrama.png", "image/png"),
        ("arte.webp", "image/webp"),
        ("contrato.pdf", "application/pdf"),
    ]:
        arq = _FakeUpload(nome, ct, 1000)
        assert _validar_uploads([arq]) is None, f"{nome} deveria passar"


def test_validar_uploads_content_type_divergente() -> None:
    arq = _FakeUpload("foto.jpg", "application/pdf", 1000)
    msg = _validar_uploads([arq])
    assert msg is not None
    assert "Conteúdo não corresponde" in msg


def test_validar_uploads_content_type_ausente_passa() -> None:
    arq = _FakeUpload("foto.jpg", None, 1000)
    assert _validar_uploads([arq]) is None


def test_validar_uploads_arquivo_maior_que_5mb() -> None:
    arq = _FakeUpload("grande.jpg", "image/jpeg", 5 * 1024 * 1024 + 1)
    msg = _validar_uploads([arq])
    assert msg is not None
    assert "excede 5 MB" in msg


def test_validar_uploads_lote_rejeitado_se_um_falha() -> None:
    bons = _FakeUpload("ok.jpg", "image/jpeg", 1000)
    mau = _FakeUpload("mau.exe", "application/octet-stream", 1000)
    msg = _validar_uploads([bons, mau])
    assert msg is not None
    assert "Tipo não permitido" in msg


def test_validar_uploads_sem_filename_ignorado() -> None:
    arq = _FakeUpload("", None, None)
    assert _validar_uploads([arq]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "validar_uploads" -v`
Expected: FAIL with `ImportError: cannot import name '_validar_uploads' from 'xtreme_system.api.routes.ui'`

- [ ] **Step 3: Write the implementation**

Add to `bases/xtreme_system/api/routes/ui.py`, immediately after the `_uploads_cliente_dir` function (currently around line 246, before `_uploaded_file_path` at line 249):

```python
_EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
_MAX_POR_ARQUIVO = 5 * 1024 * 1024
_TIPO_POR_EXTENSAO = {
    ".jpg":  {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png":  {"image/png"},
    ".webp": {"image/webp"},
    ".pdf":  {"application/pdf"},
}


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
            arq.file.seek(0, 2)
            tam = arq.file.tell()
            arq.file.seek(0)
        if tam > _MAX_POR_ARQUIVO:
            return f"{arq.filename} excede 5 MB ({tam // 1024 // 1024} MB)"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "validar_uploads" -v`
Expected: PASS — all 7 `validar_uploads` tests green.

- [ ] **Step 5: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/routes/ui.py tests/test_ui.py
git commit -m "feat: add _validar_uploads helper for file type/size validation"
```

---

## Task 2: Middleware `_limite_request_size` (20 MB por request)

**Files:**
- Modify: `bases/xtreme_system/api/setup.py` (add constant near the top and middleware after `_request_context`)
- Test: `tests/test_ui.py` (new test)

**Interfaces:**
- Consumes: `Request`, `Response` (both already imported in `setup.py`).
- Produces: a middleware registered on `app` that returns `Response(..., status_code=413)` when `Content-Length` exceeds 20 MB, otherwise delegates to `call_next`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`:

```python
def test_post_com_content_length_maior_que_20mb_retorna_413(
    client: TestClient,
) -> None:
    _login_admin(client)
    # Content-Length de 21 MB: 21 * 1024 * 1024 bytes
    resp = client.post(
        "/ui/veiculos/1/imagens",
        content=b"",
        headers={"Content-Length": str(21 * 1024 * 1024)},
    )
    assert resp.status_code == 413
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "content_length_maior" -v`
Expected: FAIL — the upload handler is invoked (likely 200 or 422), not 413.

- [ ] **Step 3: Write the implementation**

In `bases/xtreme_system/api/setup.py`, add the constant near the top (after the imports, before `configure_logging()`) and the middleware just after the existing `_request_context` middleware (after line 58, before `_ui_dir = Path(__file__).parent`).

Add the constant:

```python
_MAX_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB
```

Add the middleware (after `_request_context`, before the `_ui_dir` line):

```python
@app.middleware("http")
async def _limite_request_size(request: Request, call_next: Callable[[Request], Any]):
    cl = request.headers.get("content-length")
    if cl and int(cl) > _MAX_REQUEST_BYTES:
        return Response("Request excede 20 MB", status_code=413)
    return await call_next(request)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "content_length_maior" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/setup.py tests/test_ui.py
git commit -m "feat: reject requests with Content-Length > 20 MB (413)"
```

---

## Task 3: Wire validation into `ui_veiculo_imagens_upload`

**Files:**
- Modify: `bases/xtreme_system/api/routes/ui.py` — handler `ui_veiculo_imagens_upload` (lines 277-303)
- Modify: `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html` — add `erro` block
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: `_validar_uploads` from Task 1, `_found` and `veiculo.get` (existing), `templates.TemplateResponse` (existing).
- Produces: upload endpoint that returns 400 with an error alert on invalid input, before touching the filesystem.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`:

```python
def test_upload_imagem_veiculo_extensao_invalida_rejeitada(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("malicioso.gif", b"dados", "image/gif")},
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert ".gif" in resp.text
    # filesystem não deve conter o arquivo rejeitado
    assert "malicioso.gif" not in resp.text.replace("Tipo não permitido", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "extensao_invalida_rejeitada" -v`
Expected: FAIL — the handler currently saves the file and returns 200.

- [ ] **Step 3: Write the implementation**

In `bases/xtreme_system/api/routes/ui.py`, inside `ui_veiculo_imagens_upload` (line 277), insert the validation block **after** `_found(veiculo.get(session, veiculo_id), "Veículo")` and **before** `upload_dir = _uploads_dir(veiculo_id)`:

```python
    erro = _validar_uploads(imagens)
    if erro:
        item = _found(veiculo.get(session, veiculo_id), "Veículo")
        return templates.TemplateResponse(
            request,
            "_modal_imagens_veiculo.html",
            {"veiculo": item, "erro": erro},
            status_code=400,
        )
```

In `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html`, add the error block inside `modal__body`, at the very top of that div (between the `<div class="modal__body">` opening and the `{% if veiculo.imagens %}` block, i.e. after line 8):

```jinja
      {% if erro %}{{ ui.alert(erro) }}{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "extensao_invalida_rejeitada or upload_imagem_veiculo" -v`
Expected: PASS — both the rejection test and the existing happy-path `test_upload_imagem_veiculo_salva_url_estatica_acessivel` pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/routes/ui.py bases/xtreme_system/api/templates/_modal_imagens_veiculo.html tests/test_ui.py
git commit -m "feat: reject invalid files on vehicle image upload (400 + modal error)"
```

---

## Task 4: Wire validation into `ui_cliente_documentos_upload`

**Files:**
- Modify: `bases/xtreme_system/api/routes/ui.py` — handler `ui_cliente_documentos_upload` (lines 415-425)
- Modify: `bases/xtreme_system/api/templates/_modal_documentos_cliente.html` — add `erro` block
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: `_validar_uploads` from Task 1, `_found` and `cliente.get` (existing), `templates.TemplateResponse` (existing).
- Produces: client-documents upload endpoint that returns 400 with an error alert on invalid input, before any save.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`. This test reuses the pattern from the existing `test_ui_cria_veiculo_com_debitos_documento_e_modal_vendedor` (around line 134) which already creates a client with id fetch. Use a simpler approach: create the client via JSON API, then POST a `.txt` doc:

```python
def test_upload_documento_cliente_extensao_invalida_rejeitada(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_id = client.post("/clientes", json={"nome": "X", "documento": "11122233344", "tipo": "pessoa_fisica"}, headers=headers).json()["id"]

    resp = client.post(
        f"/ui/clientes/{cliente_id}/documentos",
        files=[("documentos", ("notas.txt", b"texto", "text/plain"))],
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert ".txt" in resp.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "documento_cliente_extensao_invalida" -v`
Expected: FAIL — the handler currently saves the file and returns 200.

- [ ] **Step 3: Write the implementation**

In `bases/xtreme_system/api/routes/ui.py`, inside `ui_cliente_documentos_upload` (line 415), insert validation **after** `_found(cliente.get(session, cliente_id), "Cliente")` and **before** `_salvar_documentos_cliente(session, cliente_id, documentos)`:

```python
    erro = _validar_uploads(documentos)
    if erro:
        item = _found(cliente.get(session, cliente_id), "Cliente")
        return templates.TemplateResponse(
            request,
            "_modal_documentos_cliente.html",
            {"cliente": item, "erro": erro},
            status_code=400,
        )
```

In `bases/xtreme_system/api/templates/_modal_documentos_cliente.html`, add the error block inside `modal__body`, at the very top (between the `<div class="modal__body">` opening and the `{% if cliente.documentos %}` block, i.e. after line 8):

```jinja
      {% if erro %}{{ ui.alert(erro) }}{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "documento_cliente" -v`
Expected: PASS — both the rejection test and the existing happy-path doc-upload test (inside the `_cria_veiculo` test that checks `/documentos/`) pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/routes/ui.py bases/xtreme_system/api/templates/_modal_documentos_cliente.html tests/test_ui.py
git commit -m "feat: reject invalid files on client document upload (400 + modal error)"
```

---

## Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc)

**Files:**
- Modify: `bases/xtreme_system/api/routes/ui.py` — handler `_criar_veiculo` (lines 613-670). The validation runs over `documentos_cliente` + `documento_veiculo`.
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: `_validar_uploads` from Task 1, `form.getlist` and `form.get` (existing), `_erro_veiculo` (existing helper at line 526).
- Produces: `_criar_veiculo` returns the form error page (status 400) **before** `veiculo.create()` when any uploaded file is invalid — so no orphaned veiculo record is left behind.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`. The vehicle-creation form requires many fields; the existing `test_ui_cria_veiculo_com_debitos_documento_e_modal_vendedor` (line 134) shows the shape. Build a minimal valid form with an invalid file and assert the vehicle was NOT created:

```python
def test_criar_veiculo_com_documento_invalido_nao_cria_veiculo(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    inv_id = client.get("/investidores", headers=headers).json()[0]["id"]

    form = {
        "tipo": "carro",
        "modelo": "Rejeitado",
        "cor": "Preto",
        "ano": "2020",
        "placa": "REJ0001",
        "km": "0",
        "preco": "50000",
        "tipo_entrada": "compra",
        "revisao": "on",
        "investidor_id": str(inv_id),
        "cliente_vendedor_id": "",
        "cli_nome": "Vend Rej",
        "cli_documento": "99988877766",
        "cli_tipo": "pessoa_fisica",
    }
    resp = client.post(
        "/ui/veiculos",
        data=form,
        files=[
            ("documentos_cliente", ("ruim.exe", b"x", "application/octet-stream")),
        ],
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    # veículo não deve ter sido criado
    veiculos = client.get("/veiculos", headers=headers).json()
    assert not any(v["placa"] == "REJ0001" for v in veiculos)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "documento_invalido_nao_cria" -v`
Expected: FAIL — the handler currently saves the file and creates the veiculo (status 200).

- [ ] **Step 3: Write the implementation**

In `bases/xtreme_system/api/routes/ui.py`, inside `_criar_veiculo` (line 613), the existing code around lines 643-653 collects `documentos` and `doc_veiculo` and then saves. Insert the validation **right after** the `seller`/`novo_cliente_data`/`debitos` resolution is done and **before** `obj = veiculo.create(session, data)` (around line 639), so a validation failure never creates a veiculo:

Locate these lines (around 643-653) which already build `documentos` and pull `documento_veiculo`:

```python
    documentos = [
        arquivo
        for arquivo in form.getlist("documentos_cliente")
        if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
    ]
    _salvar_documentos_cliente(session, seller.id, cast(list[UploadFile], documentos))
    _salvar_documento_veiculo(
        session,
        obj.id,
        cast(UploadFile | None, form.get("documento_veiculo")),
    )
```

Replace the block **starting at `documentos = [`** with the following (validation inserted before save, and save moved after `veiculo.create`):

```python
    documentos = [
        arquivo
        for arquivo in form.getlist("documentos_cliente")
        if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
    ]
    doc_veiculo = cast(UploadFile | None, form.get("documento_veiculo"))
    todos = list(documentos) + ([doc_veiculo] if doc_veiculo else [])
    erro = _validar_uploads(todos)
    if erro:
        return _erro_veiculo(request, session, erro)

    obj = veiculo.create(session, data)
    if novo_cliente_data is not None:
        seller = cliente.create(session, novo_cliente_data)
    assert seller is not None  # noqa: S101 -- invariante interna: erro is None garante seller definido
    _salvar_documentos_cliente(session, seller.id, documentos)
    _salvar_documento_veiculo(session, obj.id, doc_veiculo)
```

Note: the previous code did `obj = veiculo.create(session, data)` immediately after `debitos` was resolved, with `assert seller is not None` following `novo_cliente_data`. The reorder keeps the same final state: validation runs first, then `veiculo.create`, then `cliente.create` if needed, then the document saves using `obj.id` and `seller.id` (both now defined). Move the `obj = veiculo.create(session, data)` and `seller = cliente.create(...)` lines from their old position (right after the `debitos` block) into this new block.

Concretely, the diff against the existing `_criar_veiculo` (lines ~639-653) is:

Remove these lines from their current position (right before `documentos = [`):
```python
    obj = veiculo.create(session, data)
    if novo_cliente_data is not None:
        seller = cliente.create(session, novo_cliente_data)
    assert seller is not None  # noqa: S101 -- invariante interna: erro is None garante seller definido
```

And replace the existing save block with the version in the code block above.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -k "documento_invalido_nao_cria or cria_veiculo_com_debitos" -v`
Expected: PASS — the rejection test returns 400 and does NOT create the veiculo; the existing happy-path vehicle-creation test still passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/routes/ui.py tests/test_ui.py
git commit -m "feat: reject invalid files on vehicle creation before creating record"
```

---

## Task 6: Align `accept` attributes in templates

**Files:**
- Modify: `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html` (line 36)
- Modify: `bases/xtreme_system/api/templates/_modal_documentos_cliente.html` (line 32)
- Modify: `bases/xtreme_system/api/templates/_form_veiculo.html` (lines 85, 90, 151, 204)
- Modify: `bases/xtreme_system/api/templates/_midia_veiculo.html` (lines 17, 35)

**Interfaces:**
- Consumes: nothing new.
- Produces: `accept` attributes in all file inputs that match the server-side whitelist: `.jpg,.jpeg,.png,.webp,.pdf` (or the images-only subset for image-only inputs).

- [ ] **Step 1: Apply the edits**

In `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html` (line 36), change:

```html
      <input class="input" type="file" name="imagens" accept="image/*" multiple required>
```
to:

```html
      <input class="input" type="file" name="imagens" accept=".jpg,.jpeg,.png,.webp" multiple required>
```

In `bases/xtreme_system/api/templates/_modal_documentos_cliente.html` (line 32), change:

```html
      <input class="input" type="file" name="documentos" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" multiple required>
```
to:

```html
      <input class="input" type="file" name="documentos" accept=".pdf,.jpg,.jpeg,.png,.webp" multiple required>
```

In `bases/xtreme_system/api/templates/_form_veiculo.html`, change each of the 4 occurrences of `accept="image/*,.pdf"` to `accept=".jpg,.jpeg,.png,.webp,.pdf"`. The 4 lines are:
- Line 85: `<input class="input" name="documento_veiculo" type="file" accept="image/*,.pdf">`
- Line 90: `<input class="input" name="documentos_cliente" type="file" accept="image/*,.pdf" multiple>`
- Line 151: `<input class="input" name="documento_veiculo" type="file" accept="image/*,.pdf">`
- Line 204: `<input class="input" name="documentos_cliente" type="file" accept="image/*,.pdf" multiple>`

In `bases/xtreme_system/api/templates/_midia_veiculo.html`:
- Line 17, change `accept="image/*"` to `accept=".jpg,.jpeg,.png,.webp"`.
- Line 35, change `<input class="input" type="file" name="arquivo" multiple>` to `<input class="input" type="file" name="arquivo" accept=".pdf,.jpg,.jpeg,.png,.webp" multiple>`.

- [ ] **Step 2: Verify no test regressed**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && uv run pytest tests/test_ui.py -v`
Expected: PASS — all existing tests still green (the existing happy-path tests use `.jpg`/`.pdf` which are still in the whitelist).

- [ ] **Step 3: Commit**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add bases/xtreme_system/api/templates/_modal_imagens_veiculo.html bases/xtreme_system/api/templates/_modal_documentos_cliente.html bases/xtreme_system/api/templates/_form_veiculo.html bases/xtreme_system/api/templates/_midia_veiculo.html
git commit -m "refactor: align file input accept attributes with upload whitelist"
```

---

## Task 7: Full lint + test run

**Files:**
- No file changes — verification only.

- [ ] **Step 1: Run the full lint suite**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && make lint`
Expected: PASS — ruff check, ruff format --check, xenon, vulture, mypy all clean. (The `Callable` and `Any` imports used by the new middleware are already present in `setup.py`.)

- [ ] **Step 2: Run the full test suite**

Run: `cd /Users/guilsmatos/orca/projects/xtreme-system && make test`
Expected: All tests pass, including the 7 new `validar_uploads` unit tests, the `content_length_maior` middleware test, the `extensao_invalida_rejeitada` test, and the `documento_cliente_extensao_invalida` test, plus the `documento_invalido_nao_cria` test. Existing happy-path tests (vehicle image upload, client document upload, vehicle creation with documents) remain green.

- [ ] **Step 3: (If lint or tests fail) fix and re-run**

If mypy complains about the middleware signature or unused imports, address inline. If ruff complains about formatting or sorting, run `make format` and re-check. Re-run `make lint` and `make test` until both are clean.

- [ ] **Step 4: Commit (only if changes were made in Step 3)**

```bash
cd /Users/guilsmatos/orca/projects/xtreme-system
git add -A
git commit -m "chore: fix lint/test issues from upload validation"
```

---

## Self-Review Notes

**Spec coverage:**
- Section "Constantes" (ui.py + setup.py) → Task 1 + Task 2.
- Section "Helper de validação" → Task 1.
- Section "Middleware de limite de request" → Task 2.
- Section "Integração nos handlers" (3 handlers) → Tasks 3, 4, 5.
- Section "Templates — bloco de erro" (modais) → Tasks 3, 4 (alert added alongside validation).
- Section "Templates — alinhamento do `accept`" (6 templates, 8 inputs) → Task 6.
- Section "Error handling" (400 for type/size, 413 for request size) → Tasks 1-5.
- Section "Testes" (unit + integration + regression + middleware) → Tasks 1-5.
- Bug pre-existente (`_midia_veiculo.html` forms) — explicitly out of scope per spec; aligned `accept` only (Task 6), did not add missing routes.

**Type consistency:**
- `_validar_uploads(arquivos: list[UploadFile]) -> str | None` — identical signature in Task 1 (definition) and Tasks 3, 4, 5 (callers).
- `_MAX_REQUEST_BYTES`, `_MAX_POR_ARQUIVO`, `_EXTENSOES_PERMITIDAS`, `_TIPO_POR_EXTENSAO` — names match across Task 1 (ui.py) and Task 2 (setup.py uses `_MAX_REQUEST_BYTES`).
- `_limite_request_size` — name matches in Task 2 definition and is not referenced elsewhere (middleware is registered via decorator; no cross-task dependency).
- All test helpers (`_login_admin`, `_admin_headers`) are pre-existing in `tests/test_ui.py` and are reused by the new tests.
- `_FakeUpload` / `_FakeFile` stubs are defined in the Task 1 test step and not referenced outside the unit tests — no cross-task type name to track.

**Scope check:** single subsystem (upload validation), single implementation plan. No decomposition needed.
