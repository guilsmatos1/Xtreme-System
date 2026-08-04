from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importa a Base e todos os models para popular a metadata (autogenerate).
from xtreme_system.auditoria import core as _auditoria  # noqa: F401
from xtreme_system.caixa import core as _caixa  # noqa: F401
from xtreme_system.cliente import core as _cliente  # noqa: F401
from xtreme_system.compra import core as _compra  # noqa: F401
from xtreme_system.consignacao import core as _consignacao  # noqa: F401
from xtreme_system.custo_veiculo import core as _custo_veiculo  # noqa: F401
from xtreme_system.database import rate_limit as _rate_limit  # noqa: F401
from xtreme_system.database.core import Base, get_settings
from xtreme_system.documento_contrato_venda import (
    core as _documento_contrato_venda,  # noqa: F401
)
from xtreme_system.documento_procuracao import (
    core as _documento_procuracao,  # noqa: F401
)
from xtreme_system.documento_veiculo import core as _documento_veiculo  # noqa: F401
from xtreme_system.empresa import core as _empresa  # noqa: F401
from xtreme_system.fechamento_venda import core as _fechamento_venda  # noqa: F401
from xtreme_system.imagem_comprovante_compra import (
    core as _imagem_comprovante_compra,  # noqa: F401
)
from xtreme_system.imagem_comprovante_venda import (
    core as _imagem_comprovante_venda,  # noqa: F401
)
from xtreme_system.imagem_contrato_consignacao import (
    core as _imagem_contrato_consignacao,  # noqa: F401
)
from xtreme_system.imagem_documento_cliente import (
    core as _imagem_documento_cliente,  # noqa: F401
)
from xtreme_system.imagem_veiculo import core as _imagem_veiculo  # noqa: F401
from xtreme_system.investidor import core as _investidor  # noqa: F401
from xtreme_system.perfil import core as _perfil  # noqa: F401
from xtreme_system.rsd import core as _rsd  # noqa: F401
from xtreme_system.usuario import core as _usuario  # noqa: F401
from xtreme_system.veiculo import core as _veiculo  # noqa: F401
from xtreme_system.venda import core as _venda  # noqa: F401
from xtreme_system.whatsapp import core as _whatsapp  # noqa: F401

target_metadata = Base.metadata
# ConfigParser (usado por Config.set_main_option) trata "%" como início de
# interpolação; URLs com querystring percent-encoded (ex.: "options=-c%20...")
# quebram sem escapar.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
