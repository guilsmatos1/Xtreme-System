"""Authorization for files served from /static/uploads."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


def test_upload_exige_permissao_do_recurso(
    make_client: Callable[..., TestClient],
) -> None:
    upload_url = ""
    upload_path: Path | None = None

    def seed(session: Session) -> None:
        nonlocal upload_url, upload_path
        admin = usuario.Usuario(
            username="seed", senha_hash="x", papel=usuario.Papel.admin
        )
        session.add(admin)
        session.flush()
        session.info["usuario_id"] = admin.id

        perfil_sem_operacao = perfil.create(
            session,
            perfil.PerfilCreate(nome="Veiculos sem documentos", paginas=["veiculos"]),
            admin.id,
        )
        perfil_com_operacao = perfil.create(
            session,
            perfil.PerfilCreate(
                nome="Veiculos com documentos",
                paginas=["veiculos"],
                restricoes={"veiculos": {"operacoes": ["upload_documento"]}},
            ),
            admin.id,
        )
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="sem-doc",
                senha="senha",
                papel=usuario.Papel.funcionario,
                perfil_id=perfil_sem_operacao.id,
            ),
            admin.id,
        )
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="com-doc",
                senha="senha",
                papel=usuario.Papel.funcionario,
                perfil_id=perfil_com_operacao.id,
            ),
            admin.id,
        )

        inv = investidor.create(session, investidor.InvestidorCreate(nome="Inv"))
        carro = veiculo.create(
            session,
            veiculo.VeiculoCreate(
                tipo=veiculo.TipoVeiculo.carro,
                modelo="Onix",
                cor="Prata",
                ano=2024,
                placa="UPL1234",
                km=1000,
                preco=80000,
                investidor_id=inv.id,
            ),
            admin.id,
        )
        upload_url = f"/static/uploads/veiculos/{carro.id}/documentos/auth-test.pdf"
        upload_path = Path("bases/xtreme_system/api").joinpath(upload_url.lstrip("/"))
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(b"%PDF-auth")
        documento_veiculo.create(
            session,
            documento_veiculo.DocumentoVeiculoCreate(
                veiculo_id=carro.id,
                url=upload_url,
            ),
            admin.id,
        )

    client = make_client(seed=seed)
    try:
        denied_login = client.post(
            "/ui/login",
            data={"username": "sem-doc", "password": "senha"},
            follow_redirects=False,
        )
        assert denied_login.status_code == 303
        assert client.get(upload_url).status_code == 403

        client.cookies.clear()
        allowed_login = client.post(
            "/ui/login",
            data={"username": "com-doc", "password": "senha"},
            follow_redirects=False,
        )
        assert allowed_login.status_code == 303
        allowed = client.get(upload_url)
        assert allowed.status_code == 200
        assert allowed.content == b"%PDF-auth"
    finally:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
