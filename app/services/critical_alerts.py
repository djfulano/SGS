from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.config import CONFIG_DIR
from app.importers.topos_importer import caminho_sites_excel
from app.services.finance_service import AGREEMENTS_FILE
from app.services.finance_service import PAYMENTS_FILE
from app.services.finance_service import normalizar_codigo_microsiga
from app.services.finance_service import preparar_acordos_exibicao
from app.services.finance_service import preparar_pagamentos_exibicao
from app.services.site_registry_service import load_site_registry
from app.storage import read_json
from app.storage import write_json_atomic


ALERT_CONFIG_FILE = CONFIG_DIR / "finance" / "alerts_config.json"
DEFAULT_ALERT_DAYS = 15
OPEN_AGREEMENT_STATUSES = {
    "em negociação",
    "aprovado",
    "em pagamento",
    "inadimplente",
}

CRITICAL_SITE_ALERT_COLUMNS = [
    "Nome",
    "Nome SNMPc",
    "Código Microsiga",
    "Vencimento",
    "Dias",
    "Situação",
    "Origem da data",
    "Parcelas abertas",
    "Valor",
]

AGREEMENT_ALERT_COLUMNS = [
    "Site",
    "Nome SNMPc",
    "Código Microsiga",
    "Favorecido",
    "ID SGS",
    "Vencimento",
    "Dias",
    "Situação",
    "Status",
    "Valor",
]


def load_alert_config(path=None):
    config = read_json(path or ALERT_CONFIG_FILE, {})
    try:
        dias = int(config.get("alert_days", DEFAULT_ALERT_DAYS))
    except (TypeError, ValueError):
        dias = DEFAULT_ALERT_DAYS
    return {"alert_days": max(1, min(90, dias))}


def save_alert_config(config, path=None):
    try:
        dias = int((config or {}).get("alert_days", DEFAULT_ALERT_DAYS))
    except (TypeError, ValueError):
        dias = DEFAULT_ALERT_DAYS
    resultado = {"alert_days": max(1, min(90, dias))}
    write_json_atomic(path or ALERT_CONFIG_FILE, resultado)
    return resultado


def _assinatura_arquivo(caminho):
    caminho = Path(caminho)
    try:
        estado = caminho.stat()
        return str(caminho), estado.st_size, estado.st_mtime_ns
    except OSError:
        return str(caminho), 0, 0


def assinatura_fontes_alertas(hoje=None, caminhos=None):
    hoje = hoje or date.today()
    fontes = caminhos or (
        PAYMENTS_FILE,
        AGREEMENTS_FILE,
        caminho_sites_excel(),
        ALERT_CONFIG_FILE,
    )
    return (
        hoje.isoformat(),
        tuple(_assinatura_arquivo(caminho) for caminho in fontes),
    )


def _texto(valor):
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _sim(valor):
    return _texto(valor).casefold() in {"sim", "s", "true", "1"}


def _numero(valor):
    numero = pd.to_numeric(valor, errors="coerce")
    return 0.0 if pd.isna(numero) else float(numero)


def _data(valor):
    data = pd.to_datetime(valor, errors="coerce")
    return None if pd.isna(data) else data.date()


def _situacao_dias(dias):
    if dias < 0:
        return f"Atrasado há {abs(dias)} dias"
    if dias == 0:
        return "Vence hoje"
    return f"Vence em {dias} dias"


def proximo_vencimento_mensal(dia, hoje=None):
    hoje = hoje or date.today()
    try:
        dia = int(dia)
    except (TypeError, ValueError):
        return None
    if not 1 <= dia <= 28:
        return None
    if hoje.day <= dia:
        return date(hoje.year, hoje.month, dia)
    if hoje.month == 12:
        return date(hoje.year + 1, 1, dia)
    return date(hoje.year, hoje.month + 1, dia)


def _sites_criticos(cadastro):
    if cadastro is None or cadastro.empty:
        return []
    return [
        linha
        for linha in cadastro.to_dict(orient="records")
        if _sim(linha.get("SITE CRÍTICO"))
        and _texto(linha.get("Status")).casefold() == "ativo"
    ]


def _pagamentos_regulares_abertos(pagamentos):
    if pagamentos is None or pagamentos.empty:
        return pd.DataFrame()
    dados = pagamentos.copy()
    status = dados.get(
        "Status Atual",
        pd.Series(index=dados.index, dtype=str),
    ).astype(str).str.casefold()
    tipo = dados.get(
        "Tipo de despesa",
        pd.Series(index=dados.index, dtype=str),
    ).astype(str).str.upper()
    return dados[
        ~status.isin({"pago", "cancelado"})
        & ~tipo.eq("ACORDO/PARCELAMENTO")
    ].copy()


def _montar_alertas_sites_criticos_preparados(
    cadastro,
    pagamentos,
    hoje,
    antecedencia,
):
    abertos = _pagamentos_regulares_abertos(pagamentos)
    alertas = []
    diagnosticos = []

    if not abertos.empty:
        abertos["_microsiga"] = abertos.get(
            "Microsiga",
            pd.Series(index=abertos.index, dtype=str),
        ).map(normalizar_codigo_microsiga)
        abertos["_vencimento"] = pd.to_datetime(
            abertos.get("Data de vencimento"),
            errors="coerce",
        )

    for site in _sites_criticos(cadastro):
        vencimento_padrao = proximo_vencimento_mensal(
            site.get("DIA VENCIMENTO"),
            hoje,
        )

        if vencimento_padrao is None:
            diagnosticos.append({
                "Tipo": "Site crítico sem vencimento padrão",
                "Nome": _texto(site.get("NOME")),
                "Nome SNMPc": _texto(site.get("SMNPC")),
                "Código Microsiga": normalizar_codigo_microsiga(
                    site.get("CÓDIGO MICROSIGA")
                ),
            })
            continue

        microsiga = normalizar_codigo_microsiga(site.get("CÓDIGO MICROSIGA"))
        parcelas = (
            abertos[abertos["_microsiga"].eq(microsiga)].copy()
            if microsiga and not abertos.empty
            else pd.DataFrame()
        )
        parcelas_validas = (
            parcelas[parcelas["_vencimento"].notna()].sort_values("_vencimento")
            if not parcelas.empty
            else parcelas
        )
        origem = "Dia mensal cadastrado"
        valor = 0.0
        if not parcelas_validas.empty:
            primeira = parcelas_validas.iloc[0]
            vencimento = primeira["_vencimento"].date()
            origem = "Parcela financeira aberta"
            valor = _numero(primeira.get("Subtotal"))
        else:
            vencimento = vencimento_padrao

        dias = (vencimento - hoje).days
        if dias > antecedencia:
            continue
        alertas.append({
            "Nome": _texto(site.get("NOME")),
            "Nome SNMPc": _texto(site.get("SMNPC")),
            "Código Microsiga": microsiga,
            "Vencimento": vencimento.isoformat(),
            "Dias": dias,
            "Situação": _situacao_dias(dias),
            "Origem da data": origem,
            "Parcelas abertas": len(parcelas),
            "Valor": valor,
        })

    resultado = pd.DataFrame(alertas, columns=CRITICAL_SITE_ALERT_COLUMNS)
    if not resultado.empty:
        resultado = resultado.sort_values(
            ["Dias", "Nome", "Nome SNMPc"],
            kind="stable",
        ).reset_index(drop=True)
    return resultado, pd.DataFrame(diagnosticos)


def montar_alertas_sites_criticos(
    cadastro_sites=None,
    pagamentos=None,
    hoje=None,
    antecedencia=None,
):
    hoje = hoje or date.today()
    antecedencia = int(
        antecedencia
        if antecedencia is not None
        else load_alert_config()["alert_days"]
    )
    cadastro = load_site_registry() if cadastro_sites is None else cadastro_sites.copy()
    pagamentos = preparar_pagamentos_exibicao(
        pagamentos,
        hoje=hoje,
        cadastro_sites=cadastro,
    )
    return _montar_alertas_sites_criticos_preparados(
        cadastro,
        pagamentos,
        hoje,
        antecedencia,
    )


def _montar_alertas_acordos_preparados(
    acordos,
    pagamentos,
    hoje,
    antecedencia,
):
    if acordos.empty:
        return pd.DataFrame(columns=AGREEMENT_ALERT_COLUMNS), pd.DataFrame()

    fechados = set()
    if not pagamentos.empty:
        fechados = set(
            pagamentos.loc[
                pagamentos["Status Atual"].isin(["Pago", "Cancelado"]),
                "ID SGS",
            ].astype(str)
        )

    alertas = []
    diagnosticos = []
    for acordo in acordos.to_dict(orient="records"):
        status = _texto(acordo.get("Status"))
        if status.casefold() not in OPEN_AGREEMENT_STATUSES:
            continue
        pagamento_origem = _texto(acordo.get("ID Pagamento"))
        if pagamento_origem and pagamento_origem in fechados:
            continue
        vencimento = _data(acordo.get("Data de vencimento"))
        if vencimento is None:
            diagnosticos.append({
                "Tipo": "Acordo sem data de vencimento",
                "Site": _texto(acordo.get("Nome Site")),
                "Favorecido": _texto(acordo.get("Favorecido") or acordo.get("Nome")),
                "ID SGS": _texto(acordo.get("ID SGS")),
            })
            continue
        dias = (vencimento - hoje).days
        if dias > antecedencia:
            continue
        alertas.append({
            "Site": _texto(acordo.get("Nome Site")),
            "Nome SNMPc": _texto(acordo.get("Nome SNMPc")),
            "Código Microsiga": normalizar_codigo_microsiga(acordo.get("Microsiga")),
            "Favorecido": _texto(acordo.get("Favorecido") or acordo.get("Nome")),
            "ID SGS": _texto(acordo.get("ID SGS")),
            "Vencimento": vencimento.isoformat(),
            "Dias": dias,
            "Situação": _situacao_dias(dias),
            "Status": status,
            "Valor": _numero(acordo.get("Valor Acordo")),
        })

    resultado = pd.DataFrame(alertas, columns=AGREEMENT_ALERT_COLUMNS)
    if not resultado.empty:
        resultado = resultado.sort_values(
            ["Dias", "Site", "Favorecido"],
            kind="stable",
        ).reset_index(drop=True)
    return resultado, pd.DataFrame(diagnosticos)


def montar_alertas_acordos(
    acordos=None,
    pagamentos=None,
    hoje=None,
    antecedencia=None,
):
    hoje = hoje or date.today()
    antecedencia = int(
        antecedencia
        if antecedencia is not None
        else load_alert_config()["alert_days"]
    )
    cadastro = load_site_registry()
    acordos = preparar_acordos_exibicao(
        acordos,
        cadastro_sites=cadastro,
    )
    pagamentos = preparar_pagamentos_exibicao(
        pagamentos,
        hoje=hoje,
        cadastro_sites=cadastro,
    )
    return _montar_alertas_acordos_preparados(
        acordos,
        pagamentos,
        hoje,
        antecedencia,
    )


def status_alertas_criticos(
    cadastro_sites=None,
    pagamentos=None,
    acordos=None,
    hoje=None,
    antecedencia=None,
):
    hoje = hoje or date.today()
    antecedencia = int(
        antecedencia
        if antecedencia is not None
        else load_alert_config()["alert_days"]
    )
    cadastro = load_site_registry() if cadastro_sites is None else cadastro_sites.copy()
    pagamentos_preparados = preparar_pagamentos_exibicao(
        pagamentos,
        hoje=hoje,
        cadastro_sites=cadastro,
    )
    acordos_preparados = preparar_acordos_exibicao(
        acordos,
        cadastro_sites=cadastro,
    )
    sites, diagnosticos_sites = _montar_alertas_sites_criticos_preparados(
        cadastro,
        pagamentos_preparados,
        hoje,
        antecedencia,
    )
    alertas_acordos, diagnosticos_acordos = _montar_alertas_acordos_preparados(
        acordos_preparados,
        pagamentos_preparados,
        hoje,
        antecedencia,
    )
    return {
        "sites": sites,
        "acordos": alertas_acordos,
        "diagnosticos_sites": diagnosticos_sites,
        "diagnosticos_acordos": diagnosticos_acordos,
        "total": len(sites) + len(alertas_acordos),
        "atrasados": int((sites.get("Dias", pd.Series(dtype=int)) < 0).sum())
        + int((alertas_acordos.get("Dias", pd.Series(dtype=int)) < 0).sum()),
    }
