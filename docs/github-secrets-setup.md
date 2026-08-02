# Configurar Secrets do GitHub para Deploy Automático

## Passo 1: Acessar as configurações de Secrets

1. Vá para seu repositório no GitHub
2. Clique em **Settings** (aba no topo do repositório)
3. No menu lateral esquerdo, clique em **Secrets and variables** → **Actions**

Você deve ver algo assim:
```
Settings
├── General
├── Branches
├── Collaborators
├── Secrets and variables ← CLIQUE AQUI
│   └── Actions ← CLIQUE AQUI
├── Environments
└── ...
```

## Passo 2: Adicionar cada Secret

Clique em **New repository secret** e adicione cada um dos secrets abaixo:

### Secret 1: SSH_HOST
| Campo | Valor |
|-------|-------|
| **Name** | `SSH_HOST` |
| **Value** | `145.223.31.111` |

Depois clique em **Add secret**

---

### Secret 2: SSH_USERNAME
| Campo | Valor |
|-------|-------|
| **Name** | `SSH_USERNAME` |
| **Value** | `deploy` |

---

### Secret 3: SSH_PASSWORD
| Campo | Valor |
|-------|-------|
| **Name** | `SSH_PASSWORD` |
| **Value** | `sua-senha-do-usuario-deploy` |

⚠️ **Importante**: Esta é a senha SSH do usuário `deploy` na VPS

---

### Secret 4: SSH_PORT
| Campo | Valor |
|-------|-------|
| **Name** | `SSH_PORT` |
| **Value** | `22` |

---

### Secret 5: DEPLOY_PATH
| Campo | Valor |
|-------|-------|
| **Name** | `DEPLOY_PATH` |
| **Value** | `/home/deploy/xtreme-system` |

---

### Secret 6: SERVICE_NAME
| Campo | Valor |
|-------|-------|
| **Name** | `SERVICE_NAME` |
| **Value** | `xtreme-system` |

---

## Passo 3: Verificar Secrets

Após adicionar todos, você deve ver uma lista como esta:

```
Actions secrets
├── SSH_HOST ••••••••
├── SSH_USERNAME ••••••••
├── SSH_PASSWORD ••••••••
├── SSH_PORT ••••••••
├── DEPLOY_PATH ••••••••
└── SERVICE_NAME ••••••••
```

(Os valores ficam ocultos por segurança, mostrando apenas `••••••••`)

## Passo 4: Teste o Deploy

Agora o setup está completo! Para testar:

1. Faça um pequeno commit e push para `master`:
   ```bash
   git add .
   git commit -m "chore: add deploy workflow"
   git push origin master
   ```

2. Vá para **Actions** no seu repositório
3. Você verá dois workflows:
   - **CI** - rodando testes (deve passar)
   - **Deploy to VPS** - conectando à VPS

## Troubleshooting

### Erro: "Permission denied (publickey,password)"
- Verifique se `SSH_PASSWORD` está correto
- Teste a senha manualmente: `ssh deploy@145.223.31.111`

### Erro: "Could not resolve hostname"
- Verifique se `SSH_HOST` está correto (165.223.31.111? 145.223.31.111?)

### Workflow não dispara
- Certifique-se de fazer push para a branch `master`
- Verifique se o CI passou (pre-requisito do deploy)

### Secrets com valor errado
- Clique em um secret existente
- Clique em **Update secret**
- Digite o novo valor e confirme

## Alternativa: SSH com Chave Privada

Se preferir usar chave SSH em vez de senha, você pode:

1. Remover `SSH_PASSWORD` dos secrets
2. Adicionar `SSH_PRIVATE_KEY` com o conteúdo da sua chave
3. Modificar o workflow para usar a chave:

```yaml
- name: Deploy via SSH
  uses: appleboy/ssh-action@master
  with:
    host: ${{ secrets.SSH_HOST }}
    username: ${{ secrets.SSH_USERNAME }}
    key: ${{ secrets.SSH_PRIVATE_KEY }}  # ← Usar chave em vez de senha
    port: ${{ secrets.SSH_PORT }}
    # ... resto do script
```

Para gerar uma chave:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/vps_deploy
# Copie o conteúdo de ~/.ssh/vps_deploy (SEM extensão .pub)
```

Depois copie a chave pública para a VPS:
```bash
ssh-copy-id -i ~/.ssh/vps_deploy.pub deploy@145.223.31.111
```
