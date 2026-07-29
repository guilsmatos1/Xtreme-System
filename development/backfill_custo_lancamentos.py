"""Recalcula os lançamentos de custo dos veículos a partir do valor da compra.

Uso: uv run python development/backfill_custo_lancamentos.py [--dry-run]

O lançamento de custo do veículo passou a espelhar `Compra.valor_compra` em vez
de `Veiculo.preco` (que hoje é o preço anunciado). Lançamentos criados antes
dessa mudança seguem com o valor antigo — este script os corrige.

Veículos sem compra (consignação) ficam com custo zero.
"""

import sys
from decimal import Decimal

from sqlalchemy.orm import Session

from xtreme_system.caixa import core as caixa
from xtreme_system.compra import core as compra
from xtreme_system.database.core import SessionLocal
from xtreme_system.veiculo import core as veiculo


def _valor_esperado(session: Session, veiculo_id: int) -> Decimal:
    compra_atual = compra.get_latest_by_veiculo(session, veiculo_id)
    if compra_atual is None:
        return Decimal("0")
    return compra_atual.valor_compra


def backfill(session: Session, *, dry_run: bool) -> int:
    lancamentos = (
        session.query(caixa.LancamentoInvestimento)
        .filter(
            caixa.LancamentoInvestimento.origem == caixa.OrigemLancamento.veiculo,
            caixa.LancamentoInvestimento.veiculo_id.is_not(None),
        )
        .all()
    )
    alterados = 0
    for lancamento in lancamentos:
        assert lancamento.veiculo_id is not None  # noqa: S101
        esperado = _valor_esperado(session, lancamento.veiculo_id)
        if lancamento.valor == esperado:
            continue
        alterados += 1
        print(
            f"veiculo={lancamento.veiculo_id} "
            f"lancamento={lancamento.id} "
            f"{lancamento.valor} -> {esperado}"
        )
        if dry_run:
            continue
        veiculo_obj = veiculo.get(session, lancamento.veiculo_id)
        if veiculo_obj is not None:
            caixa.sincronizar_lancamento_veiculo(session, veiculo_obj)
    return alterados


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    with SessionLocal() as session:
        alterados = backfill(session, dry_run=dry_run)
        if dry_run:
            session.rollback()
            print(f"\n[dry-run] {alterados} lançamento(s) seriam corrigidos.")
        else:
            session.commit()
            print(f"\n{alterados} lançamento(s) corrigidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
