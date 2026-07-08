"""Importa estoque.csv para o banco: uv run python development/import_estoque.py"""

import csv
import re
from decimal import Decimal, InvalidOperation

from xtreme_system.database.core import SessionLocal
from xtreme_system.investidor.core import Investidor
from xtreme_system.meio_captacao.core import MeioCaptacao
from xtreme_system.veiculo.core import (
    StatusVeiculo,
    TipoVeiculo,
    Veiculo,
    VeiculoCreate,
)

CARROS = {"HB20", "MOBI", "ONIX", "FORD KA", "FORD FOCUS", "IX35"}


def detect_tipo(modelo: str) -> TipoVeiculo:
    upper = modelo.upper()
    for kw in CARROS:
        if kw in upper:
            return TipoVeiculo.carro
    return TipoVeiculo.moto


def parse_km(raw: str) -> int:
    raw = raw.strip().upper().replace(".", "")
    if raw in ("", "0KM", "OKM"):
        return 0
    return int(raw)


def parse_preco(raw: str) -> Decimal | None:
    raw = raw.strip().upper().replace(".", "").replace(" ", "")
    raw = raw.removeprefix("R$")
    if not raw or raw == "ADEFINIR":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_status(raw: str) -> StatusVeiculo:
    raw = raw.strip().upper()
    if "VENDIDO" in raw:
        return StatusVeiculo.vendido
    return StatusVeiculo.disponivel


def normalize_investidor(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "XTREME"
    return re.split(r"\s*\+\s*", raw)[0].strip()


def normalize_meio(raw: str) -> str:
    raw = raw.strip()
    return raw if raw else "XTREME"


def get_or_create_investidor(session, nome: str) -> Investidor:
    existing = session.query(Investidor).filter_by(nome=nome).first()
    if existing:
        return existing
    obj = Investidor(nome=nome)
    session.add(obj)
    session.flush()
    return obj


def get_or_create_meio(session, nome: str) -> MeioCaptacao:
    existing = session.query(MeioCaptacao).filter_by(nome=nome).first()
    if existing:
        return existing
    obj = MeioCaptacao(nome=nome)
    session.add(obj)
    session.flush()
    return obj


def main() -> None:
    created = 0
    skipped = 0
    seen_placas: dict[str, int] = {}

    with SessionLocal() as session:
        with open("estoque.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                modelo = row["MODELO"].strip()
                preco = parse_preco(row["PREÇO"])
                if preco is None:
                    skipped += 1
                    continue

                placa = row["PLACA"].strip()
                if placa in seen_placas:
                    seen_placas[placa] += 1
                    placa = f"{placa}-{seen_placas[placa]}"
                else:
                    seen_placas[placa] = 0

                if session.query(Veiculo).filter_by(placa=placa).first():
                    skipped += 1
                    continue

                investidor = get_or_create_investidor(
                    session, normalize_investidor(row["INVESTIDOR"])
                )
                meio = get_or_create_meio(
                    session, normalize_meio(row["MEIO DE CAPTAÇÃO DA VENDA"])
                )

                data = VeiculoCreate(
                    tipo=detect_tipo(modelo),
                    modelo=modelo,
                    cor=row["COR"].strip(),
                    ano=int(row["ANO"].strip()),
                    placa=placa,
                    km=parse_km(row["KM"]),
                    preco=preco,
                    procuracao=row["Procuração"].strip() or None,
                    status=parse_status(row["STATUS"]),
                    investidor_id=investidor.id,
                    meio_captacao_id=meio.id,
                )
                session.add(Veiculo(**data.model_dump()))
                created += 1

        session.commit()
        print(f"{created} veículos importados, {skipped} pulados")


if __name__ == "__main__":
    main()
