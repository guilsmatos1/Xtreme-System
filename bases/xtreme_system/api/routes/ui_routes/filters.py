"""Query-filter types shared by UI report and audit routes."""

from datetime import date
from typing import Annotated, Any, Self, cast

from pydantic import BaseModel, BeforeValidator, Field, model_validator

JANELA_MAX_DIAS = 732
ERRO_PERIODO_INVERTIDO = "data_de não pode ser maior que data_ate"
ERRO_PERIODO_LONGO = f"período não pode exceder {JANELA_MAX_DIAS} dias"


def _vazio_para_none(value: Any) -> Any:
    """Formulário HTMX manda `?campo=` vazio; trata como ausente."""
    return value or None


DataFiltro = Annotated[date | None, BeforeValidator(_vazio_para_none)]
IdFiltro = Annotated[
    Annotated[int, Field(gt=0)] | None, BeforeValidator(_vazio_para_none)
]
TextoFiltro = Annotated[
    Annotated[str, Field(max_length=100)] | None, BeforeValidator(_vazio_para_none)
]


class PeriodoFiltro(BaseModel):
    """Base para filtros com intervalo de datas."""

    data_de: DataFiltro = None
    data_ate: DataFiltro = None

    @staticmethod
    def _periodo_padrao() -> tuple[date, date]:
        raise NotImplementedError

    @model_validator(mode="after")
    def _validar_periodo(self) -> Self:
        inicio, fim = self._periodo_padrao()
        if self.data_de is None:
            self.data_de = inicio
        if self.data_ate is None:
            self.data_ate = fim
        if self.data_de > self.data_ate:
            raise ValueError(ERRO_PERIODO_INVERTIDO)
        if (self.data_ate - self.data_de).days > JANELA_MAX_DIAS:
            raise ValueError(ERRO_PERIODO_LONGO)
        return self

    @property
    def periodo(self) -> tuple[date, date]:
        return cast("date", self.data_de), cast("date", self.data_ate)
