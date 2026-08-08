#!/bin/bash
set -e

# Script para setup inicial de deploy na VPS
# Uso: sudo scripts/setup-deploy.sh

DEPLOY_USER="deploy"
DEPLOY_PATH="/home/deploy/xtreme-system"
SERVICE_NAME="xtreme-system"
REPO_URL="${1:-https://github.com/seu-usuario/seu-repo.git}"

echo "================================"
echo "Setup de Deploy - Xtreme System"
echo "================================"
echo ""
echo "Configuração:"
echo "  Usuário: $DEPLOY_USER"
echo "  Caminho: $DEPLOY_PATH"
echo "  Serviço: $SERVICE_NAME"
echo "  Repositório: $REPO_URL"
echo ""

# Verificar se é root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Este script deve ser executado como root (use sudo)"
   exit 1
fi

# 1. Criar usuário deploy se não existir
if ! id "$DEPLOY_USER" &>/dev/null; then
    echo "👤 Criando usuário $DEPLOY_USER..."
    useradd -m -s /bin/bash "$DEPLOY_USER"
else
    echo "✅ Usuário $DEPLOY_USER já existe"
fi

# 2. Criar diretório de deploy
if [ ! -d "$DEPLOY_PATH" ]; then
    echo "📁 Criando diretório $DEPLOY_PATH..."
    mkdir -p "$DEPLOY_PATH"
    chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_PATH"
else
    echo "✅ Diretório $DEPLOY_PATH já existe"
fi

# 3. Clonar repositório se não existir
if [ ! -d "$DEPLOY_PATH/.git" ]; then
    echo "🔄 Clonando repositório..."
    sudo -u "$DEPLOY_USER" git clone "$REPO_URL" "$DEPLOY_PATH"
else
    echo "✅ Repositório já clonado"
fi

# 4. Instalar uv se não estiver presente
if ! sudo -u "$DEPLOY_USER" command -v uv &> /dev/null; then
    echo "📦 Instalando uv..."
    sudo -u "$DEPLOY_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
else
    echo "✅ uv já está instalado"
fi

# 5. Instalar dependências Python
echo "📦 Instalando dependências Python..."
cd "$DEPLOY_PATH"
sudo -u "$DEPLOY_USER" /home/"$DEPLOY_USER"/.local/bin/uv sync

# 6. Criar arquivo .env se não existir
if [ ! -f "$DEPLOY_PATH/.env" ]; then
    echo "⚙️ Criando arquivo .env..."
    auth_secret_value="$(openssl rand -hex 32)"
    rsd_encryption_key_value="$(openssl rand -hex 32)"
    cat > "$DEPLOY_PATH/.env" << EOF
# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme

# Auth
AUTH_SECRET_KEY=$auth_secret_value

# RSD (gere um valor diferente da AUTH_SECRET_KEY)
RSD_ENCRYPTION_KEY=$rsd_encryption_key_value
RSD_ALLOWED_HOSTS=lojas.rsdsistema.com.br

# Environment
ENVIRONMENT=production
EOF
    chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_PATH/.env"
    chmod 600 "$DEPLOY_PATH/.env"
    echo "⚠️  Edite $DEPLOY_PATH/.env com suas configurações reais"
else
    echo "✅ Arquivo .env já existe"
fi

# 7. Rodar migrations
echo "🗄️ Rodando migrações Alembic..."
cd "$DEPLOY_PATH"
sudo -u "$DEPLOY_USER" /home/"$DEPLOY_USER"/.local/bin/uv run alembic upgrade head

# 8. Criar arquivo de serviço systemd
echo "🔧 Criando serviço systemd..."
UVS_BIN="/home/$DEPLOY_USER/.local/bin/uv"
cat > /etc/systemd/system/"$SERVICE_NAME".service << EOF
[Unit]
Description=Xtreme System API
After=network.target postgresql.service

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$DEPLOY_PATH
Environment="PATH=/home/$DEPLOY_USER/.local/share/uv/python/cpython-3.12.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$UVS_BIN run uvicorn xtreme_system.api.core:app --host 0.0.0.0 --port 8000 --proxy-headers
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 9. Recarregar systemd e habilitar serviço
echo "🔄 Ativando serviço systemd..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# 10. Configurar sudo para restart sem senha
echo "🔐 Configurando sudoers..."
if ! grep -q "NOPASSWD: /bin/systemctl restart $SERVICE_NAME" /etc/sudoers; then
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart $SERVICE_NAME" | tee -a /etc/sudoers > /dev/null
else
    echo "✅ Sudoers já configurado"
fi

echo ""
echo "================================"
echo "✅ Setup concluído!"
echo "================================"
echo ""
echo "Próximas etapas:"
echo "1. Edite o arquivo .env com suas configurações reais:"
echo "   sudo nano $DEPLOY_PATH/.env"
echo ""
echo "2. Verifique o status do serviço:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "3. Veja os logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "4. Configure os secrets do GitHub em:"
echo "   https://github.com/seu-usuario/seu-repo/settings/secrets/actions"
echo ""
echo "5. Faça um push para master para testar o deploy automático!"
echo ""
