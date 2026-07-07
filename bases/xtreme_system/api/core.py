"""API FastAPI: CRUD de investidores, meios de captação e veículos."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from xtreme_system.database.core import get_session
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.veiculo import core as veiculo

app = FastAPI(title="Xtreme Estoque")

SessionDep = Annotated[Session, Depends(get_session)]


def _found[T](obj: T | None, nome: str) -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nome} não encontrado")
    return obj


# ---- Investidores ----


@app.get("/investidores", response_model=list[investidor.InvestidorRead])
def listar_investidores(session: SessionDep) -> list[investidor.Investidor]:
    return investidor.list_all(session)


@app.get("/investidores/{item_id}", response_model=investidor.InvestidorRead)
def obter_investidor(item_id: int, session: SessionDep) -> investidor.Investidor:
    return _found(investidor.get(session, item_id), "Investidor")


@app.post("/investidores", response_model=investidor.InvestidorRead, status_code=201)
def criar_investidor(
    data: investidor.InvestidorCreate, session: SessionDep
) -> investidor.Investidor:
    return investidor.create(session, data)


@app.patch("/investidores/{item_id}", response_model=investidor.InvestidorRead)
def atualizar_investidor(
    item_id: int, data: investidor.InvestidorUpdate, session: SessionDep
) -> investidor.Investidor:
    obj = _found(investidor.get(session, item_id), "Investidor")
    return investidor.update(session, obj, data)


@app.delete("/investidores/{item_id}", status_code=204)
def remover_investidor(item_id: int, session: SessionDep) -> None:
    investidor.delete(session, _found(investidor.get(session, item_id), "Investidor"))


# ---- Meios de captação ----


@app.get("/meios-captacao", response_model=list[meio_captacao.MeioCaptacaoRead])
def listar_meios(session: SessionDep) -> list[meio_captacao.MeioCaptacao]:
    return meio_captacao.list_all(session)


@app.get("/meios-captacao/{item_id}", response_model=meio_captacao.MeioCaptacaoRead)
def obter_meio(item_id: int, session: SessionDep) -> meio_captacao.MeioCaptacao:
    return _found(meio_captacao.get(session, item_id), "Meio de captação")


@app.post(
    "/meios-captacao", response_model=meio_captacao.MeioCaptacaoRead, status_code=201
)
def criar_meio(
    data: meio_captacao.MeioCaptacaoCreate, session: SessionDep
) -> meio_captacao.MeioCaptacao:
    return meio_captacao.create(session, data)


@app.patch("/meios-captacao/{item_id}", response_model=meio_captacao.MeioCaptacaoRead)
def atualizar_meio(
    item_id: int, data: meio_captacao.MeioCaptacaoUpdate, session: SessionDep
) -> meio_captacao.MeioCaptacao:
    obj = _found(meio_captacao.get(session, item_id), "Meio de captação")
    return meio_captacao.update(session, obj, data)


@app.delete("/meios-captacao/{item_id}", status_code=204)
def remover_meio(item_id: int, session: SessionDep) -> None:
    meio_captacao.delete(
        session, _found(meio_captacao.get(session, item_id), "Meio de captação")
    )


# ---- Veículos ----


def _validar_fks(session: Session, inv_id: int, meio_id: int) -> None:
    if investidor.get(session, inv_id) is None:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")
    if meio_captacao.get(session, meio_id) is None:
        raise HTTPException(status_code=400, detail="meio_captacao_id inexistente")


@app.get("/veiculos", response_model=list[veiculo.VeiculoRead])
def listar_veiculos(session: SessionDep) -> list[veiculo.Veiculo]:
    return veiculo.list_all(session)


@app.get("/veiculos/{item_id}", response_model=veiculo.VeiculoRead)
def obter_veiculo(item_id: int, session: SessionDep) -> veiculo.Veiculo:
    return _found(veiculo.get(session, item_id), "Veículo")


@app.post("/veiculos", response_model=veiculo.VeiculoRead, status_code=201)
def criar_veiculo(data: veiculo.VeiculoCreate, session: SessionDep) -> veiculo.Veiculo:
    _validar_fks(session, data.investidor_id, data.meio_captacao_id)
    return veiculo.create(session, data)


@app.patch("/veiculos/{item_id}", response_model=veiculo.VeiculoRead)
def atualizar_veiculo(
    item_id: int, data: veiculo.VeiculoUpdate, session: SessionDep
) -> veiculo.Veiculo:
    obj = _found(veiculo.get(session, item_id), "Veículo")
    if (
        data.investidor_id is not None
        and investidor.get(session, data.investidor_id) is None
    ):
        raise HTTPException(status_code=400, detail="investidor_id inexistente")
    if (
        data.meio_captacao_id is not None
        and meio_captacao.get(session, data.meio_captacao_id) is None
    ):
        raise HTTPException(status_code=400, detail="meio_captacao_id inexistente")
    return veiculo.update(session, obj, data)


@app.delete("/veiculos/{item_id}", status_code=204)
def remover_veiculo(item_id: int, session: SessionDep) -> None:
    veiculo.delete(session, _found(veiculo.get(session, item_id), "Veículo"))
