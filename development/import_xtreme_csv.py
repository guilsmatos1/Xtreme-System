"""Importa o estoque de xtreme.csv.

Uso: uv run python development/import_xtreme_csv.py [--dry-run]

Apaga todos os veiculos, recadastra os da planilha, cria o "Cliente Desconhecido"
e registra uma compra por veiculo vinculada a esse cliente.
"""

import csv
import importlib
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.database.core import SessionLocal
from xtreme_system.investidor import core as investidor
from xtreme_system.veiculo import core as veiculo

# Os relacionamentos do SQLAlchemy referenciam classes por nome, entao todos os
# models precisam estar carregados antes da primeira query (mesma necessidade
# que alembic/env.py resolve com imports diretos).
MODELS_PARA_REGISTRAR = (
    "custo_veiculo",
    "documento_contrato_venda",
    "documento_procuracao",
    "documento_veiculo",
    "empresa",
    "fechamento_venda",
    "imagem_comprovante_compra",
    "imagem_comprovante_venda",
    "imagem_documento_cliente",
    "imagem_veiculo",
    "perfil",
    "usuario",
    "venda",
    "whatsapp",
    "rsd",
)

CSV_PATH = Path("xtreme.csv")
DOCUMENTO_DESCONHECIDO = "00000000000"
NOME_CLIENTE_DESCONHECIDO = "Cliente Desconhecido"
INVESTIDOR_FALLBACK = "XTREME"
VALOR_COMPRA_SIMBOLICO = Decimal("0.01")
OBSERVACAO_COMPRA = "Importado de xtreme.csv"

# Linhas do CSV (numeracao 1-based com header na linha 1) a descartar.
# 79: XJ6 N placa ESW0966 a R$39.900 - duplicata da linha 115 (R$42.900), que fica.
LINHAS_DESCARTADAS = {79}

# Placa AUTOPRO se repete em 3 linhas e nao passa em normalizar_placa.
# Decisao do usuario: cadastrar como AUTOPRO1/2/3 (invalidas para a UI).
PLACA_SEM_REGISTRO = "AUTOPRO"

# Preco arbitrado para a linha cujo PRECO no CSV e "A DEFINIR".
PRECO_A_DEFINIR = Decimal("35900")

# Veiculos de 4 rodas, identificados por placa (o resto e moto).
PLACAS_CARRO = frozenset(
    {
        "TDU3C17",  # HB20 COMFORT HATCH PLUS
        "FNE5D63",  # MOBI LIKE
        "FLG1D76",  # ONIX LT 1.4
        "TCM9G85",  # ONIX LT PLUS
        "QXE9C36",  # FORD KA HATCH 1.0
        "ETP2H54",  # IX35
        "ELA6758",  # FORD FOCUS SEDAN
        "GJN2D34",  # ONIX
        "QUS7H31",  # ONIX JOY
        "DWM2A19",  # HILUX SW4 DIAMOND
    }
)


@dataclass(frozen=True)
class LinhaCSV:  # pylint: disable=too-many-instance-attributes
    linha: int
    modelo: str
    cor: str
    ano: int
    placa: str
    km: int
    preco: Decimal
    procuracao: str | None
    tipo: veiculo.TipoVeiculo
    status: veiculo.StatusVeiculo
    investidor_nome: str


def registrar_models() -> None:
    """Carrega todos os models para o registry de mappers do SQLAlchemy."""
    for nome in MODELS_PARA_REGISTRAR:
        importlib.import_module(f"xtreme_system.{nome}.core")


def _chave(nome: str) -> str:
    """Chave de comparacao de nomes: sem acento, sem espaco extra, casefold."""
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.split()).casefold()


def _parse_km(value: str) -> int:
    bruto = value.strip().upper()
    if not bruto or bruto in {"0KM", "OKM"}:
        return 0
    digitos = re.sub(r"\D", "", bruto)
    return int(digitos) if digitos else 0


def _parse_preco(value: str) -> Decimal:
    digitos = re.sub(r"[^\d,]", "", value.replace(".", ""))
    if not digitos:
        return PRECO_A_DEFINIR
    return Decimal(digitos.replace(",", "."))


def _parse_placa(value: str, ocorrencia_autopro: int) -> str:
    bruto = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if bruto == PLACA_SEM_REGISTRO:
        return f"{PLACA_SEM_REGISTRO}{ocorrencia_autopro}"
    return veiculo.normalizar_placa(value)


def _parse_texto(value: str | None) -> str | None:
    texto = (value or "").strip()
    return texto or None


def parse_linhas(path: Path) -> list[LinhaCSV]:
    """Le e normaliza o CSV, descartando duplicatas conhecidas."""
    linhas: list[LinhaCSV] = []
    autopro = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for numero, row in enumerate(csv.DictReader(handle), start=2):
            if numero in LINHAS_DESCARTADAS:
                continue
            bruto = re.sub(r"[^0-9A-Za-z]", "", row["PLACA"]).upper()
            if bruto == PLACA_SEM_REGISTRO:
                autopro += 1
            placa = _parse_placa(row["PLACA"], autopro)
            linhas.append(
                LinhaCSV(
                    linha=numero,
                    modelo=row["MODELO"].strip(),
                    cor=row["COR"].strip(),
                    ano=int(row["ANO"].strip()),
                    placa=placa,
                    km=_parse_km(row["KM"]),
                    preco=_parse_preco(row["PREÇO"]),
                    procuracao=_parse_texto(row["Procuração"]),
                    tipo=(
                        veiculo.TipoVeiculo.carro
                        if placa in PLACAS_CARRO
                        else veiculo.TipoVeiculo.moto
                    ),
                    status=veiculo.StatusVeiculo.disponivel,
                    investidor_nome=row["INVESTIDOR"].strip() or INVESTIDOR_FALLBACK,
                )
            )
    return linhas


def apagar_veiculos(session: Session, actor_id: int | None = None) -> int:
    """Apaga todos os veiculos via ORM (cascata + auditoria)."""
    objetos = session.query(veiculo.Veiculo).all()
    for obj in objetos:
        veiculo.delete(session, obj, actor_id)
    return len(objetos)


def garantir_investidores(
    session: Session, nomes: set[str], actor_id: int | None = None
) -> tuple[dict[str, int], list[str]]:
    """Mapeia nome do CSV -> investidor.id, criando os ausentes."""
    existentes = {
        _chave(obj.nome): obj.id for obj in session.query(investidor.Investidor).all()
    }
    mapa: dict[str, int] = {}
    criados: list[str] = []
    for nome in sorted(nomes):
        chave = _chave(nome)
        if chave not in existentes:
            novo = investidor.create(
                session, investidor.InvestidorCreate(nome=nome), actor_id
            )
            existentes[chave] = novo.id
            criados.append(nome)
        mapa[nome] = existentes[chave]
    return mapa, criados


def garantir_cliente_desconhecido(
    session: Session, actor_id: int | None = None
) -> tuple[cliente.Cliente, bool]:
    """Retorna (cliente, criado_agora)."""
    existente = cliente.get_by_documento(session, DOCUMENTO_DESCONHECIDO)
    if existente is not None:
        return existente, False
    novo = cliente.create(
        session,
        cliente.ClienteCreate(
            nome=NOME_CLIENTE_DESCONHECIDO,
            documento=DOCUMENTO_DESCONHECIDO,
            tipo=cliente.TipoCliente.pessoa_fisica,
        ),
        actor_id,
    )
    return novo, True


def _criar_veiculo(
    session: Session, linha: LinhaCSV, investidor_id: int, actor_id: int | None
) -> veiculo.Veiculo:
    """Insere o Veiculo via ORM (VeiculoCreate rejeitaria as placas AUTOPRO*)."""
    obj = veiculo.Veiculo(
        tipo=linha.tipo,
        modelo=linha.modelo,
        marca=None,
        cor=linha.cor,
        ano=linha.ano,
        placa=linha.placa,
        km=linha.km,
        preco=linha.preco,
        procuracao=linha.procuracao,
        status=linha.status,
        tipo_entrada=veiculo.TipoEntrada.compra,
        investidor_id=investidor_id,
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela="veiculo",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=snapshot(obj),
    )
    return obj


def _criar_compra(
    session: Session,
    veiculo_obj: veiculo.Veiculo,
    cliente_id: int,
    actor_id: int | None,
) -> compra.Compra:
    obj = compra.Compra(
        cliente_id=cliente_id,
        veiculo_id=veiculo_obj.id,
        usuario_id=actor_id,
        data_compra=datetime.now(UTC).date(),
        valor_compra=VALOR_COMPRA_SIMBOLICO,
        debitos=None,
        observacoes=OBSERVACAO_COMPRA,
        status=compra.StatusCompra.pendente,
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela="compra",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=snapshot(obj),
    )
    return obj


def criar_veiculo_e_compra(
    session: Session,
    linha: LinhaCSV,
    investidor_id: int,
    cliente_id: int,
    actor_id: int | None = None,
) -> veiculo.Veiculo:
    """Cria veiculo + compra + lancamento no caixa, nesta ordem."""
    veiculo_obj = _criar_veiculo(session, linha, investidor_id, actor_id)
    _criar_compra(session, veiculo_obj, cliente_id, actor_id)
    caixa.criar_lancamento_veiculo(session, veiculo_obj, actor_id)
    return veiculo_obj


def _relatorio(
    apagados: int,
    linhas: list[LinhaCSV],
    investidores_criados: list[str],
    cliente_obj: cliente.Cliente,
    cliente_criado: bool,
    dry_run: bool,
) -> None:
    carros = sum(1 for item in linhas if item.tipo is veiculo.TipoVeiculo.carro)
    print(f"veiculos apagados: {apagados}")
    print(
        f"veiculos criados:  {len(linhas)} "
        f"({carros} carros, {len(linhas) - carros} motos)"
    )
    print(f"compras criadas:   {len(linhas)}")
    print(f"lancamentos caixa: {len(linhas)}")
    print(
        f"investidores criados: {len(investidores_criados)}"
        + (f" ({', '.join(investidores_criados)})" if investidores_criados else "")
    )
    print(
        f"cliente: id={cliente_obj.id} {cliente_obj.nome} "
        f"({'criado' if cliente_criado else 'reaproveitado'})"
    )
    print("\nAVISOS:")
    print("  - Placas AUTOPRO1/2/3 (W2DS) sao invalidas para o validador de placa;")
    print("    a UI recusara editar esses veiculos ate a placa ser corrigida.")
    print(
        f"  - Placa EED5I00 (GSXR750 SRAD) tinha PRECO 'A DEFINIR'; "
        f"arbitrado R$ {PRECO_A_DEFINIR}."
    )
    print("  - Placa ESW0966 (XJ6 N) aparecia 2x; mantida a de R$42.900 (linha 115).")
    print(
        f"  - Todas as compras usam valor_compra simbolico "
        f"de R$ {VALOR_COMPRA_SIMBOLICO}."
    )
    if dry_run:
        print("\n[dry-run] nada foi persistido.")


def executar(session: Session, dry_run: bool, actor_id: int | None = None) -> None:
    registrar_models()
    linhas = parse_linhas(CSV_PATH)
    apagados = apagar_veiculos(session, actor_id)
    mapa, criados = garantir_investidores(
        session, {item.investidor_nome for item in linhas}, actor_id
    )
    cliente_obj, cliente_criado = garantir_cliente_desconhecido(session, actor_id)
    for linha in linhas:
        criar_veiculo_e_compra(
            session, linha, mapa[linha.investidor_nome], cliente_obj.id, actor_id
        )
    _relatorio(apagados, linhas, criados, cliente_obj, cliente_criado, dry_run)
    if dry_run:
        session.rollback()
    else:
        session.commit()


def main() -> None:
    args = sys.argv[1:]
    if args not in ([], ["--dry-run"]):
        sys.exit("uso: import_xtreme_csv.py [--dry-run]")
    if not CSV_PATH.exists():
        sys.exit(f"arquivo nao encontrado: {CSV_PATH} (rode a partir da raiz do repo)")
    with SessionLocal() as session:
        try:
            executar(session, dry_run=args == ["--dry-run"])
        except Exception:
            session.rollback()
            raise


if __name__ == "__main__":
    main()
