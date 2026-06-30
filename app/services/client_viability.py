from datetime import datetime

from app.config import CLIENT_VIABILITY_FILE
from app.storage import read_json
from app.storage import write_json_atomic


def carregar_clientes_viabilidade(path=None):
    dados = read_json(
        path or CLIENT_VIABILITY_FILE,
        {}
    )
    return dados if isinstance(dados, dict) else {}


def salvar_clientes_viabilidade(dados, path=None):
    write_json_atomic(
        path or CLIENT_VIABILITY_FILE,
        dados or {}
    )


def dados_cliente_viabilidade(assinatura, path=None):
    assinatura = str(assinatura or "").strip()
    return carregar_clientes_viabilidade(path).get(assinatura, {})


def salvar_dados_cliente_viabilidade(
    assinatura,
    latitude=0,
    longitude=0,
    altitude=0,
    altura=0,
    usuario="",
    path=None
):
    assinatura = str(assinatura or "").strip()

    if not assinatura:
        raise ValueError("Assinatura não informada.")

    dados = carregar_clientes_viabilidade(path)
    dados[assinatura] = {
        "latitude": float(latitude or 0),
        "longitude": float(longitude or 0),
        "altitude": float(altitude or 0),
        "altura": float(altura or 0),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": usuario or ""
    }
    salvar_clientes_viabilidade(
        dados,
        path=path
    )

    return dados[assinatura]
