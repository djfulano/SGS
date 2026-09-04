# Instalação do SGS no Debian

Este guia descreve a instalação direta do SGS no Debian, sem Docker, usando
um ambiente virtual Python e serviços `systemd`.

Os comandos consideram:

- aplicação em `/opt/SGS`;
- usuário de serviço `sgs`;
- porta TCP `8501`;
- repositório `https://github.com/djfulano/SGS.git`;
- Python 3.12, versão usada na validação oficial do projeto.

## 1. Preparar o servidor

Atualize o sistema e instale as dependências básicas:

```bash
sudo apt update
sudo apt install -y \
  git curl build-essential \
  python3 python3-venv python3-pip
```

Confirme a versão disponível:

```bash
python3 --version
```

O ambiente oficial do SGS utiliza Python 3.12. Se o Debian instalado fornecer
outra versão, instale o Python 3.12 pelos repositórios disponíveis para essa
versão do Debian antes de criar o ambiente virtual.

## 2. Criar o usuário de serviço

```bash
sudo useradd --system \
  --home /opt/SGS \
  --shell /usr/sbin/nologin \
  sgs 2>/dev/null || true
```

O usuário `sgs` executará a aplicação e será proprietário dos arquivos
operacionais. Não execute o serviço como `root`.

## 3. Obter o código

```bash
sudo mkdir -p /opt/SGS
sudo chown "$USER":"$USER" /opt/SGS
git clone https://github.com/djfulano/SGS.git /opt/SGS
sudo chown -R sgs:sgs /opt/SGS
```

Se o diretório já contiver uma instalação, não execute novamente o `git clone`.
Use o procedimento de atualização descrito no final deste documento.

## 4. Criar o ambiente Python

```bash
sudo -u sgs python3 -m venv /opt/SGS/venv
sudo -u sgs /opt/SGS/venv/bin/python -m pip install --upgrade pip
sudo -u sgs /opt/SGS/venv/bin/pip install -r /opt/SGS/requirements.txt
```

Confirme que a aplicação compila:

```bash
cd /opt/SGS
sudo -u sgs /opt/SGS/venv/bin/python -m compileall -q app main.py
```

## 5. Preparar os dados persistentes

```bash
sudo mkdir -p \
  /opt/SGS/imports/archive \
  /opt/SGS/config \
  /opt/SGS/contracts \
  /opt/SGS/cache \
  /opt/SGS/backups

sudo touch /opt/SGS/rede.db
sudo chown -R sgs:sgs /opt/SGS
```

Os dados que devem ser preservados entre atualizações são:

- `imports/`;
- `config/`;
- `contracts/`;
- `cache/`;
- `backups/`;
- `rede.db`.

## 6. Configurar o ambiente

Em uma instalação nova, gere um token temporário de inicialização:

```bash
openssl rand -hex 32
```

Crie `/opt/SGS/.env`:

```bash
sudo nano /opt/SGS/.env
```

Conteúdo sugerido:

```ini
TZ=America/Sao_Paulo
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
STREAMLIT_SERVER_ENABLE_CORS=true
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true

SNMPC_DATA_DIR=/opt/SGS
SNMPC_FILE=/opt/SGS/imports/SNMPc.txt
SNMPC_IMPORTS_DIR=/opt/SGS/imports
SNMPC_CONFIG_DIR=/opt/SGS/config
SNMPC_CACHE_DIR=/opt/SGS/cache
SNMPC_BACKUP_DIR=/opt/SGS/backups
SNMPC_CONTRACTS_DIR=/opt/SGS/contracts
DATABASE_URL=sqlite:////opt/SGS/rede.db

SGS_BOOTSTRAP_TOKEN=SUBSTITUA_PELO_TOKEN_GERADO

MAPTILER_API_KEY=
MAPTILER_TOKEN=
```

As credenciais do MapTiler são opcionais para iniciar o SGS, mas são
necessárias para os recursos que dependem de mapas e geocodificação.

Proteja o arquivo:

```bash
sudo chown sgs:sgs /opt/SGS/.env
sudo chmod 600 /opt/SGS/.env
```

O `SGS_BOOTSTRAP_TOKEN` autoriza a criação do primeiro usuário Master,
restauração inicial e primeira importação. Remova essa variável depois da
configuração inicial e reinicie o serviço.

## 7. Ajustar as permissões

O script começa em modo de simulação. Confira as operações propostas:

```bash
cd /opt/SGS
sudo env APP_DIR=/opt/SGS APP_USER=sgs sh scripts/fix_permissions.sh
```

Depois aplique:

```bash
sudo env APP_DIR=/opt/SGS APP_USER=sgs \
  sh scripts/fix_permissions.sh --apply
```

Todo o repositório deve continuar pertencendo ao usuário `sgs`. Isso evita
erros como `insufficient permission for adding an object to .git/objects`:

```bash
sudo chown -R sgs:sgs /opt/SGS
```

## 8. Instalar os serviços systemd

O repositório contém o serviço da aplicação e timers para backup e diagnóstico:

```bash
sudo cp /opt/SGS/deploy/systemd/sgs*.service /etc/systemd/system/
sudo cp /opt/SGS/deploy/systemd/sgs*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now \
  sgs.service \
  sgs-backup.timer \
  sgs-health.timer
```

Confira os serviços:

```bash
sudo systemctl status sgs.service
sudo systemctl list-timers 'sgs-*'
```

## 9. Validar a instalação

```bash
curl --fail http://127.0.0.1:8501/_stcore/health
sudo journalctl -u sgs.service -n 100 --no-pager
cd /opt/SGS
sudo -u sgs /opt/SGS/venv/bin/python -m scripts.system_diagnostics
```

O health check deve retornar:

```text
ok
```

Acesse a aplicação em:

```text
http://IP_DO_SERVIDOR:8501
```

Depois de criar o primeiro Master, remova `SGS_BOOTSTRAP_TOKEN` do `.env`:

```bash
sudo nano /opt/SGS/.env
sudo systemctl restart sgs.service
```

## 10. Restringir o acesso de rede

A porta `8501` deve ficar disponível somente para a rede corporativa ou VPN.
Substitua a rede do exemplo pela rede utilizada pela empresa:

```bash
sudo apt install -y ufw
sudo ufw deny 8501/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8501 proto tcp
sudo ufw enable
```

O acesso HTTP direto não cifra senhas e cookies. Quando houver acesso fora de
uma rede confiável, utilize HTTPS por meio de um proxy reverso.

## 11. Migrar uma instalação existente

Antes de copiar dados de outro servidor, pare a aplicação:

```bash
sudo systemctl stop sgs.service
```

Copie para `/opt/SGS` os diretórios persistentes e o banco `rede.db`. Não
substitua o código da aplicação por arquivos de uma instalação antiga.

Depois da cópia:

```bash
sudo chown -R sgs:sgs \
  /opt/SGS/imports \
  /opt/SGS/config \
  /opt/SGS/contracts \
  /opt/SGS/cache \
  /opt/SGS/backups \
  /opt/SGS/rede.db

cd /opt/SGS
sudo env APP_DIR=/opt/SGS APP_USER=sgs \
  sh scripts/fix_permissions.sh --apply
sudo systemctl start sgs.service
```

Valide alguns sites, documentos, usuários, perfis e dados financeiros antes de
liberar o novo servidor.

## 12. Atualizar o SGS

Crie um backup antes da atualização:

```bash
cd /opt/SGS
sudo -u sgs /opt/SGS/venv/bin/python -m scripts.backup_scheduled
```

Atualize o código e as dependências:

```bash
sudo systemctl stop sgs.service
cd /opt/SGS
sudo -u sgs git pull origin main
sudo -u sgs /opt/SGS/venv/bin/pip install -r requirements.txt
sudo -u sgs /opt/SGS/venv/bin/python -m compileall -q app main.py
sudo systemctl start sgs.service
```

Confira a versão e a saúde:

```bash
cat /opt/SGS/VERSION
curl --fail http://127.0.0.1:8501/_stcore/health
sudo systemctl status sgs.service
```

## 13. Diagnóstico de problemas

Logs da aplicação:

```bash
sudo journalctl -u sgs.service -f
```

Reinstalação das dependências:

```bash
sudo -u sgs /opt/SGS/venv/bin/pip install -r /opt/SGS/requirements.txt
```

Correção da propriedade dos arquivos:

```bash
sudo chown -R sgs:sgs /opt/SGS
```

Reinício completo:

```bash
sudo systemctl daemon-reload
sudo systemctl restart sgs.service
```

Validação de um backup:

```bash
cd /opt/SGS
sudo -u sgs /opt/SGS/venv/bin/python \
  -m scripts.validate_backup backups/sgs_backup_YYYYMMDD_HHMMSS.zip
```
