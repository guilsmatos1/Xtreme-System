---
name: analyze-llm-adherence
description: Analyze Python codebases for real modularization opportunities that improve maintainability, reduce coupling, clarify contracts, and help LLMs make small safe edits. Use when asked to review Python architecture, find refactoring opportunities, split large files/functions/classes, detect weak module boundaries, identify duplicated logic, circular imports, global dependencies, private API access, untyped dict/Any contracts, mixed CLI/API/UI/domain logic, or propose modularization work for safer AI-assisted maintenance.
---
# Analyze LLM Adherence

Analyze Python projects for modularity problems that make future edits large, fragile, ambiguous, or risky for LLMs. Prefer opportunities that let a future agent change one small module and one focused test instead of understanding the whole system.

## Core Standard

Judge modularity by boundaries and contracts, not file count.

Mimic modularity:

```python
from services.user_service import UserService
from repositories.user_repository import UserRepository
from config import DATABASE_URL
```

Real modularity:

```python
class UserRepositoryProtocol(Protocol):
    def get_by_email(self, email: str) -> User | None: ...
```

Ask: "Can an LLM safely make a small localized change here without editing unrelated behavior?"

## Workflow

1. Inspect structure first: `rg --files -g '*.py'`, then identify large or central modules.
2. Measure hotspots with simple commands where useful:
  - line counts: `wc -l`
  - large definitions: `rg '^def |^class '`
  - private access: `rg '\\._[A-Za-z]'`
  - generic contracts: `rg 'dict\\[|: dict|Any|Mapping\\[str, Any\\]'`
  - globals/env/config: `rg 'os\\.getenv|^[A-Z0-9_]+\\s*=|global '`
  - boundary mixing: `rg 'typer|click|argparse|streamlit|FastAPI|Flask|Django|requests|sqlalchemy|sqlite|jinja|render'`
  - generic modules: `rg --files | rg '(^|/)(utils|helpers|common|misc|tools)\\.py$'`
3. Read candidate modules before judging. Do not rely on line count alone.
4. Distinguish real opportunities from cosmetic splitting.
5. Prioritize by LLM risk: context overload, mixed responsibilities, implicit contracts, duplicated logic, hidden dependencies, hard-to-test units.
6. Recommend the smallest useful extraction with a public interface and focused tests.

## What To Detect

### Large Files And Monoliths

Flag files with many unrelated responsibilities: CLI/UI, file loading, calculation, persistence, rendering, logging, and orchestration in one place. Suggest domain modules or adapters only when responsibilities are separable.

### Large Functions

Flag functions over roughly 40-60 lines when they contain multiple stages, deep branching, many temporaries, many parameters, or comments such as "validate", "calculate", "save", "render". Recommend extracting named units that match business steps.

### God Classes

Flag classes with many public methods or mixed concerns: validation, persistence, API calls, formatting, cache, auth, rendering. Recommend smaller services, validators, repositories, formatters, or protocols.

### Encapsulation Leaks

Flag external access to `_private` attributes/methods or module internals. Recommend a public method or explicit repository/service API.

### Missing Contracts

Flag important functions taking raw `dict`, `Any`, loosely typed payloads, magic keys, or untyped return structures. Recommend `dataclass`, `TypedDict`, `Protocol`, Pydantic model, or explicit return object.

### Global Dependencies

Flag environment reads, global DB clients, mutable singletons, global caches, or config imported deep in domain code. Recommend dependency injection or a thin configuration boundary.

### Boundary Mixing

Flag business rules mixed with Streamlit, Typer, FastAPI, Flask, Django, templates, SQL, pandas IO, network calls, or email. Recommend thin adapters around testable domain functions/services.

### Generic Utility Dumps

Flag large `utils.py`, `helpers.py`, `common.py`, `misc.py`, or `tools.py` files with low cohesion. Recommend domain-specific modules.

### Missing Tests Around Extracted Units

Flag critical modules without focused tests. Recommend tests for happy path, invalid input, edge behavior, expected errors, and output contract.

### Circular Imports

Flag cyclic imports or mutual service imports. Recommend extracting contracts, shared value objects, events, or `Protocol` interfaces to invert dependencies.

## Opportunity Quality Bar

Report only modularization that is likely to reduce real maintenance risk.

Good:

```text
Extract report flattening to reporting/view_models.py because dashboard and CLI both need stable rows, and tests can cover status/count rules without Streamlit.
```

Weak:

```text
Move three adjacent helper functions to a new file because the file is 220 lines.
```

Avoid proposing abstractions for single-use code unless they isolate a risky boundary or unlock tests.

## Output

Ao final da análise, salve os resultados em `docs/0003-analyze-llm-adherence.md` usando o formato abaixo.

## Output Format

Use this format for each finding:

```text
## Oportunidade N: <short title>

Arquivo: path/to/file.py

Problema:
<what responsibility/boundary/contract problem exists>

Risco para LLM:
<why AI edits become broad, ambiguous, or fragile>

Ação:
<smallest useful extraction/reorganization>

Interface sugerida:
<function/class/protocol signature or public API>

Nova estrutura:
<optional tree, only if structure matters>

Testes:
<test files/cases>

Métrica de sucesso:
<observable improvement>
```

If no strong opportunities exist, say so and list only low-confidence candidates separately.

## Checklist

Use this checklist while analyzing:

```text
[ ] Arquivos Python grandes demais?
[ ] Funções com múltiplas responsabilidades?
[ ] Classes que fazem coisas demais?
[ ] utils.py/helpers.py/common.py grandes ou sem coesão?
[ ] Muitos dicts sem contrato claro?
[ ] Uso excessivo de Any?
[ ] Imports circulares?
[ ] Acesso externo a atributos/métodos _privados?
[ ] Regra de negócio misturada com FastAPI/Flask/Django/CLI/UI?
[ ] Banco/persistência misturados com cálculo de domínio?
[ ] Dependências globais difíceis de testar?
[ ] Módulos importantes sem testes?
[ ] Funções difíceis de mockar?
[ ] Nomes genéricos demais?
[ ] Duplicação de lógica entre módulos?
[ ] Contratos públicos claros?
```

## Recommended Tone

Be specific and surgical. Tie every recommendation to a file, risk, interface, and test. Prefer fewer high-confidence opportunities over many speculative ones.
