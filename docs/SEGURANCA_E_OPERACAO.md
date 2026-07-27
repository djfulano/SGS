# Segurança e operação do SGS

## Primeira inicialização

Defina `SGS_BOOTSTRAP_TOKEN` no ambiente antes de abrir um ambiente sem dados ou
usuários. Use um valor longo e aleatório. O token autoriza a restauração inicial,
a importação inicial e a criação do primeiro Master. Remova-o do ambiente depois.

## Serviço de produção

Crie o usuário de sistema `sgs`, ajuste as permissões com
`scripts/fix_permissions.sh` e instale os exemplos em `deploy/systemd/`.
O script inicia em modo de simulação; use `--apply` somente após conferir a saída.

```bash
sudo useradd --system --home /opt/SGS --shell /usr/sbin/nologin sgs
APP_DIR=/opt/SGS APP_USER=sgs sh scripts/fix_permissions.sh
sudo env APP_DIR=/opt/SGS APP_USER=sgs sh scripts/fix_permissions.sh --apply
sudo cp deploy/systemd/sgs*.service deploy/systemd/sgs*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sgs.service sgs-backup.timer sgs-health.timer
```

O timer `sgs-backup.timer` cria o backup diário do sistema. Para um backup
separado de documentos:

```bash
python -m scripts.backup_scheduled --documents-only
```

Validação e diagnóstico:

```bash
python -m scripts.validate_backup backups/sgs_backup_YYYYMMDD_HHMMSS.zip
python -m scripts.system_diagnostics
```

## Rede

A porta 8501 deve ser liberada somente para a sub-rede corporativa ou VPN e
bloqueada na Internet. O acesso HTTP direto não cifra senha nem cookie durante o
transporte; esse risco permanece enquanto não houver HTTPS.

Exemplo com UFW, substituindo a rede:

```bash
sudo ufw deny 8501/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8501 proto tcp
```

## Arquivo SNMPc

O nome oficial é `imports/SNMPc.txt`. O legado `imports/snmpc.txt` continua sendo
lido temporariamente. Renomeie o arquivo legado durante uma janela de manutenção.
