---
name: 0004-apply-harness-improvements
description: Aplica o ranking acumulado de melhorias de harness mantido pela skill 0003. Seleciona melhorias com mais de 3 menções, refina propostas, aplica uma por vez via subagent Codex, revisa, registra em implementations.md e remove do ranking. Use quando pedirem para aplicar melhorias de harness, implementar o ranking, colocar em prática dicas consolidadas ou fechar o ciclo iniciado pela 0003.
---

# Apply Harness Improvements

Fecha o ciclo da skill **0003**: pega o ranking em `improvements-harness.md`, transforma propostas genéricas em ações concretas e aplica melhorias no harness que orienta workers **Codex**. Seja conservador: menor risco primeiro, uma melhoria por vez, revisão antes de prosseguir.

## Escopo

O harness aqui é a infraestrutura que guia a execução dos workers Codex, não o app `xtreme-system`.

Alvos válidos, do menor para o maior risco:

1. `AGENTS.md` — orientação lida pelo Codex. Preferencial.
2. Skills em `.agents/skills/` — texto/comportamento de skills usadas pelo Codex.
3. RTK em `/Users/guilsmatos/.codex/RTK.md` ou referências locais equivalentes — regras de economia/reescrita de comandos.
4. Scripts/orquestração que disparam workers Codex, como `process_issue.py`/prompt injetado — alto risco.
5. Hooks/configurações Codex, quando existirem no repo ou em `$CODEX_HOME` e forem claramente usados pelo fluxo — alto risco.

Inelegível:

- Código de produção do app (`bases/`, `components/`, migrations, tests do app etc.).
- Qualquer melhoria que só ajude outro executor e não altere o que o Codex lê/usa.
- Mudança especulativa sem caminho de verificação.

## Arquivos

- Ranking: `.agents/skills/0003-consolidate-harness-improvements/improvements-harness.md` (localize com `find .agents/skills -name improvements-harness.md` se necessário).
- Registro: `.agents/skills/0004-apply-harness-improvements/implementations.md`.
- Skills: grave sempre em `.agents/skills/...`. Se `.claude/skills` existir como symlink, não duplique nada.

## Done

1. Melhorias com **menções > 3** tiveram a `Solução` refinada no ranking.
2. Melhorias elegíveis foram ordenadas por risco crescente e aplicadas uma por vez.
3. Cada aplicação aprovada foi registrada em `implementations.md`.
4. Melhorias aplicadas foram removidas do ranking, com tabela/numeração/total atualizados.

## Fluxo

### 1. Selecionar

- Leia a tabela `Ranking por menções`.
- Selecione apenas itens com menções **> 3** (3 exatas ficam fora).
- Ordene por menções desc; empate por título.
- Informe ao usuário a lista selecionada antes de editar.

### 2. Refinar Soluções

Para cada item selecionado, reescreva só o campo `Solução` ou adicione `**Proposta refinada:**`, mantendo título e contagem.

A proposta refinada deve dizer:

- arquivo(s) exatos que o Codex consome;
- texto/regra/comportamento a alterar;
- gatilho e limite de aplicação;
- como verificar.

### 3. Classificar Risco

- Baixo: texto aditivo em `AGENTS.md` ou skill; não muda automação.
- Médio: muda comportamento de skill existente ou regra RTK.
- Alto: scripts de orquestração, prompts globais, hooks/config automática.

Aplique baixo antes de médio. Para alto risco, deixe a proposta pronta e peça confirmação antes de editar.

### 4. Aplicar Uma Por Vez

Para cada melhoria elegível:

1. Dispare um subagent síncrono para implementar apenas aquela melhoria.
2. Revise você mesmo o resultado:
   - `git status --short` e `git diff --stat`;
   - só arquivos de harness esperados mudaram;
   - nada do app foi tocado;
   - a mudança corresponde à proposta refinada;
   - Markdown/config/scripts continuam coerentes.
3. Se reprovar, corrija pontualmente ou reenvie ao subagent com feedback específico.
4. Se aprovar, registre em `implementations.md` e remova do ranking antes de passar ao próximo item.

Nunca aplique duas melhorias em paralelo.

#### Prompt Enxuto Para Subagent

```text
Implemente UMA melhoria de harness no repo xtreme-system.

MELHORIA: <título>
PROPOSTA REFINADA:
<colar solução refinada>

ALVO(S): <arquivo(s) exatos>
RISCO: <baixo|médio|alto>

Regras:
- Mude somente os alvos indicados.
- Não toque em código do app: bases/, components/, migrations, tests do app.
- A melhoria precisa afetar o que workers Codex leem/usam.
- Preserve estilo e idioma existentes.
- Não commite.

Entregue: arquivos alterados, resumo curto e como verificar.
```

### 5. Registrar e Limpar Ranking

Após cada melhoria aprovada, acrescente em `implementations.md`:

```markdown
### <Título> — <data>
- **Faixa de risco:** baixo | médio | alto
- **Arquivos alterados:** <caminhos>
- **O que mudou:** <resumo>
- **Como verificar:** <checagem/comando>
- **Como reverter:** <arquivo + trecho, ou git revert do commit>
- **Origem:** improvements-harness.md #<posição> (<menções> menções)
```

Depois remova essa melhoria de `improvements-harness.md`:

- apague a seção do item;
- apague a linha da tabela;
- renumere entradas restantes;
- ajuste total/rodapé e `_Última atualização:_`.

Faça isso incrementalmente para manter consistência se a execução for interrompida.

## Relatório Final

Informe:

- itens selecionados e quantos foram refinados;
- plano por risco: aplicado, adiado por alto risco ou inelegível;
- para cada aplicado: título, arquivos e veredito da revisão;
- quantas melhorias restam no ranking e onde está o registro.

## Guardrails

- Codex é o executor alvo.
- Só harness; nunca código do app.
- Alto risco exige confirmação.
- Uma melhoria por vez, com revisão.
- Não commit/merge sem pedido explícito.
- Idempotência: se já está em `implementations.md`, não reaplique.
