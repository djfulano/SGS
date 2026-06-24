from datetime import date
from datetime import datetime


def _data_log(registro):
    detalhes = registro.get("detalhes") or {}

    for valor in [
        detalhes.get("data_importacao"),
        registro.get("data_hora")
    ]:
        if not valor:
            continue

        texto = str(valor).strip()

        try:
            return datetime.fromisoformat(
                texto
            ).date()
        except ValueError:
            pass

        try:
            return datetime.strptime(
                texto[:10],
                "%Y-%m-%d"
            ).date()
        except ValueError:
            pass

    return None


def _data_exibicao(valor):
    if not valor:
        return "sem registro"

    return valor.strftime("%d/%m/%Y")


def status_importacao_mensal(agora=None, logs=None):
    hoje = agora or date.today()

    if isinstance(hoje, datetime):
        hoje = hoje.date()

    ciclo = hoje.strftime("%Y-%m")
    inicio_ciclo = date(
        hoje.year,
        hoje.month,
        1
    )
    status = {
        "ciclo": ciclo,
        "pendencias": [],
        "ultima_importacao_snmpc": None,
        "ultima_importacao_clientes": None,
        "snmpc_ok": False,
        "clientes_ok": False,
        "atrasado": False
    }

    for registro in logs or []:
        if registro.get("evento") != "aplicar_importacao":
            continue

        if registro.get("status") != "sucesso":
            continue

        detalhes = registro.get("detalhes") or {}
        data_registro = _data_log(
            registro
        )

        if not data_registro:
            continue

        if detalhes.get("snmpc_enviado"):
            if (
                not status["ultima_importacao_snmpc"]
                or data_registro > status["ultima_importacao_snmpc"]
            ):
                status["ultima_importacao_snmpc"] = data_registro

            if data_registro >= inicio_ciclo:
                status["snmpc_ok"] = True

        if detalhes.get("clientes_enviado"):
            if (
                not status["ultima_importacao_clientes"]
                or data_registro > status["ultima_importacao_clientes"]
            ):
                status["ultima_importacao_clientes"] = data_registro

            if data_registro >= inicio_ciclo:
                status["clientes_ok"] = True

    if not status["snmpc_ok"]:
        status["pendencias"].append("SNMPc")

    if not status["clientes_ok"]:
        status["pendencias"].append("Base de clientes")

    status["atrasado"] = bool(status["pendencias"])
    status["ultima_importacao_snmpc_texto"] = _data_exibicao(
        status["ultima_importacao_snmpc"]
    )
    status["ultima_importacao_clientes_texto"] = _data_exibicao(
        status["ultima_importacao_clientes"]
    )

    return status
