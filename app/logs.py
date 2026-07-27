import json
import os
import sys
from datetime import datetime
from pathlib import Path

from app.config import AUTH_LOG_FILE
from app.config import SYSTEM_LOG_FILE
from app.storage import file_lock


LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def agora_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _rotacionar_log(caminho):
    caminho = Path(caminho)

    if not caminho.exists() or caminho.stat().st_size < LOG_MAX_BYTES:
        return

    mais_antigo = caminho.with_name(f"{caminho.name}.{LOG_BACKUP_COUNT}")
    mais_antigo.unlink(missing_ok=True)

    for indice in range(LOG_BACKUP_COUNT - 1, 0, -1):
        origem = caminho.with_name(f"{caminho.name}.{indice}")
        destino = caminho.with_name(f"{caminho.name}.{indice + 1}")
        if origem.exists():
            os.replace(origem, destino)

    os.replace(caminho, caminho.with_name(f"{caminho.name}.1"))


def registrar_log(caminho, evento, usuario=None, status="info", detalhes=None):
    caminho = Path(caminho)

    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        registro = {
            "data_hora": agora_iso(),
            "evento": evento,
            "usuario": usuario or "",
            "status": status,
            "detalhes": detalhes or {},
        }
        linha = json.dumps(registro, ensure_ascii=False) + "\n"

        with file_lock(caminho):
            _rotacionar_log(caminho)
            with caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.chmod(caminho, 0o600)
    except Exception as erro:
        print(
            f"SGS: falha ao gravar log {caminho}: {erro}",
            file=sys.stderr,
            flush=True,
        )


def registrar_log_usuario(evento, usuario=None, status="info", detalhes=None):
    registrar_log(
        AUTH_LOG_FILE,
        evento,
        usuario=usuario,
        status=status,
        detalhes=detalhes,
    )


def registrar_log_sistema(evento, usuario=None, status="info", detalhes=None):
    registrar_log(
        SYSTEM_LOG_FILE,
        evento,
        usuario=usuario,
        status=status,
        detalhes=detalhes,
    )


def carregar_log(caminho, limite=1000):
    caminho = Path(caminho)

    if not caminho.exists():
        return []

    registros = []
    try:
        with file_lock(caminho):
            linhas = caminho.read_text(encoding="utf-8").splitlines()
    except Exception as erro:
        print(
            f"SGS: falha ao ler log {caminho}: {erro}",
            file=sys.stderr,
            flush=True,
        )
        return registros

    for linha in linhas[-limite:]:
        if not linha.strip():
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            registros.append({
                "data_hora": "",
                "evento": "linha_invalida",
                "usuario": "",
                "status": "erro",
                "detalhes": {"linha": linha},
            })

    return registros


def carregar_logs_usuario(limite=1000):
    return carregar_log(AUTH_LOG_FILE, limite=limite)


def carregar_logs_sistema(limite=1000):
    return carregar_log(SYSTEM_LOG_FILE, limite=limite)
