# Setup de Deploy Automático com GitHub Actions

Este documento descreve como configurar o deploy automático via GitHub Actions para a VPS.

## 1. Configurar Secrets do GitHub

Acesse: `https://github.com/[seu-usuario]/[seu-repo]/settings/secrets/actions`

Adicione os seguintes secrets:

| Secret | Valor | Descrição |
|--------|-------|-----------|
| `SSH_HOST` | `145.223.31.111` | IP da VPS |
| `SSH_USERNAME` | `deploy` | Usuário SSH |
| `SSH_PASSWORD` | sua-senha | Senha SSH do usuário `deploy` |
| `SSH_PORT` | `22` | Porta SSH (padrão: 22) |
| `DEPLOY_PATH` | `/home/deploy/xtreme-system` | Diretório de deploy na VPS |
| `SERVICE_NAME` | `xtreme-system` | Nome do serviço systemd |

### Como adicionar um secret:
1. Clique em "New repository secret"
2. Preencha o **Name** (ex: `SSH_HOST`)
3. Preencha o **Value** (ex: `145.223.31.111`)
4. Clique em "Add secret"

## 2. Preparar a VPS

Antes de fazer o primeiro deploy, certifique-se de que a VPS está configurada:

### 2.1 Clonar o repositório
```bash
sudo -u deploy git clone https://github.com/[seu-usuario]/[seu-repo].git /home/deploy/xtreme-system
cd /home/deploy/xtreme-system
```

### 2.2 Instalar dependências
```bash
# Como usuário deploy
cd /home/deploy/xtreme-system
uv sync
```

### 2.3 Configurar arquivo `.env`
Na VPS, em `/home/deploy/xtreme-system/.env`:
```bash
# Database
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/xtreme

# Auth
AUTH_SECRET_KEY=your-secret-key-here

# Ambiente
ENVIRONMENT=production
```

### 2.4 Rodar migrations iniciais
```bash
cd /home/deploy/xtreme-system
uv run alembic upgrade head
```

### 2.5 Criar serviço systemd

Crie o arquivo `/etc/systemd/system/xtreme-system.service`:

```ini
[Unit]
Description=Xtreme System API
After=network.target postgresql.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/xtreme-system
Environment="PATH=/home/deploy/.local/share/uv/python/cpython-3.12.1/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/deploy/.local/bin/uv run uvicorn xtreme_system.api.core:app --host 0.0.0.0 --port 8000 --proxy-headers
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Depois:
```bash
sudo systemctl daemon-reload
sudo systemctl enable xtreme-system
sudo systemctl start xtreme-system
```

### 2.6 Configurar sudo para reiniciar o serviço

O workflow roda `sudo systemctl restart`, então adicione permissão sem senha:

```bash
sudo visudo
```

Adicione esta linha ao final:
```
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart xtreme-system
```

Salve com `Ctrl+X` e confirme.

## 3. Como funciona o Deploy Automático

### Fluxo
1. **Push para `master`** → Dispara CI (lint + testes)
2. **CI passa** → Dispara workflow de deploy
3. **Deploy**:
   - Conecta via SSH à VPS
   - Faz `git pull` da branch `master`
   - Instala dependências com `uv sync`
   - Roda migrations com `alembic upgrade head`
   - Reinicia o serviço com `systemctl restart xtreme-system`

### Monitorar Deploy
1. Acesse `https://github.com/[seu-usuario]/[seu-repo]/actions`
2. Clique no workflow "Deploy to VPS"
3. Clique na execução mais recente para ver logs detalhados

### Rollback
Se algo der errado, você pode fazer rollback manual na VPS:
```bash
cd /home/deploy/xtreme-system
git reset --hard [commit-anterior]
sudo systemctl restart xtreme-system
```

## 4. Troubleshooting

### Erro: "Permission denied (publickey,password)"
- Verifique se `SSH_USERNAME` e `SSH_PASSWORD` estão corretos
- Certifique-se de que o usuário pode fazer login via SSH

### Erro: "sudo: command not found"
- O workflow usa `sudo` para reiniciar o serviço
- Configure a permissão de sudo conforme a seção 2.6

### Erro: "uv: command not found"
- Certifique-se de que `uv` está instalado no PATH do usuário `deploy`
- Teste com: `sudo -u deploy uv --version`

### Erro: "Database connection failed"
- Verifique se PostgreSQL está rodando: `sudo systemctl status postgresql`
- Verifique credenciais em `.env`: `DATABASE_URL`
- Teste conexão: `sudo -u deploy psql -c "SELECT 1" xtreme`

### Erro: "Alembic migrations failed"
- Verifique se o banco tem permissões: `sudo -u postgres psql -d xtreme -c "GRANT ALL ON SCHEMA public TO deploy;"`
- Rode manualmente para debug: `cd /home/deploy/xtreme-system && uv run alembic upgrade head`

## 5. Ambiente de Produção

### Nginx (proxy reverso)
```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### SSL/TLS (Certbot)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com
```

### Monitoramento
- Logs da API: `sudo journalctl -u xtreme-system -f`
- Erros: `sudo journalctl -u xtreme-system -n 100`

## 6. Checklist Pré-Deploy

- [ ] `.env` configurado na VPS
- [ ] PostgreSQL rodando e acessível
- [ ] Diretório de deploy criado
- [ ] Git configurado para pull sem prompt de senha
- [ ] Serviço systemd criado e habilitado
- [ ] Sudo configurado para reiniciar sem senha
- [ ] Secrets do GitHub adicionados
- [ ] SSH funcionando: `ssh -p 22 deploy@145.223.31.111`
- [ ] Primeiro deploy testado manualmente antes de usar CI/CD
