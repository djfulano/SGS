import json
from datetime import datetime

from app.config import AUTH_LOG_FILE
from app.config import SYSTEM_LOG_FILE


def agora_iso():

    return datetime.now().astimezone().isoformat(timespec="seconds")


def registrar_log(caminho, evento, usuario=None, status="info", detalhes=None):

    try:

        caminho.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        registro = {
            "data_hora": agora_iso(),
            "evento": evento,
            "usuario": usuario or "",
            "status": status,
            "detalhes": detalhes or {}
        }

        with caminho.open("a", encoding="utf-8") as arquivo:

            arquivo.write(
                json.dumps(
                    registro,
                    ensure_ascii=False
                )
            )
            arquivo.write("\n")

    except Exception:

        return


def registrar_log_usuario(evento, usuario=None, status="info", detalhes=None):

    registrar_log(
        AUTH_LOG_FILE,
        evento,
        usuario=usuario,
        status=status,
        detalhes=detalhes
    )


def registrar_log_sistema(evento, usuario=None, status="info", detalhes=None):

    registrar_log(
        SYSTEM_LOG_FILE,
        evento,
        usuario=usuario,
        status=status,
        detalhes=detalhes
    )


def carregar_log(caminho, limite=1000):

    if not caminho.exists():

        return []

    registros = []

    try:

        linhas = caminho.read_text(
            encoding="utf-8"
        ).splitlines()

    except Exception:

        return registros

    for linha in linhas[-limite:]:

        if not linha.strip():

            continue

        try:

            registros.append(
                json.loads(linha)
            )

        except json.JSONDecodeError:

            registros.append({
                "data_hora": "",
                "evento": "linha_invalida",
                "usuario": "",
                "status": "erro",
                "detalhes": {
                    "linha": linha
                }
            })

    return registros


def carregar_logs_usuario(limite=1000):

    return carregar_log(
        AUTH_LOG_FILE,
        limite=limite
    )


def carregar_logs_sistema(limite=1000):

    return carregar_log(
        SYSTEM_LOG_FILE,
        limite=limite
    )
