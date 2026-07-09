from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.config import CONFIG_DIR
from app.logs import registrar_log_sistema
from app.storage import read_json
from app.storage import write_json_atomic

FINANCE_DIR = CONFIG_DIR / "finance"
PAYMENTS_FILE = FINANCE_DIR / "payments.json"
AGREEMENTS_FILE = FINANCE_DIR / "agreements.json"

PAYMENT_STATUSES = [
    "Pendente",
    "Exportado",
    "Pago",
    "Vencido",
    "Cancelado",
]

AGREEMENT_STATUSES = [
    "Em negociação",
    "Aprovado",
    "Em pagamento",
    "Quitado",
    "Inadimplente",
    "Cancelado",
]

PAYMENT_COLUMNS = [
    "ID SGS",
    "Status",
    "Ano",
    "Prioridade",
    "CNPJ/CPF",
    "Tipo",
    "PIX",
    "Banco",
    "Cód",
    "Agência",
    "C/Corrente",
    "Multa",
    "Juros",
    "Competência",
    "Data de vencimento",
    "Dia vencimento",
    "Nome",
    "Fornecedor",
    "Microsiga",
    "Produto",
    "C.C",
    "RC NOVA",
    "OC NOVA",
    "OC Primário",
    "OC Secundário",
    "Energia",
    "Outros",
    "Locação",
    "Subtotal",
    "Descrição",
    "Código Aquiles",
    "Nome SNMPc",
    "Nome Site",
    "Site localizado",
    "Observação interna",
    "Importado em",
    "Atualizado em",
]

AGREEMENT_COLUMNS = [
    "ID SGS",
    "Status",
    "Obs",
    "Competência",
    "Acordo",
    "Nome",
    "Resp",
    "Aprovado Sindico",
    "PAGO",
    "Microsiga",
    "Valor Acordo",
    "Descrição",
    "Multa + Juros",
    "Código Aquiles",
    "Nome SNMPc",
    "Nome Site",
    "Site localizado",
    "Observação interna",
    "Importado em",
    "Atualizado em",
]

PAYMENT_HEADER_ALIASES = {
    "Mês": "Competência",
    "Mes": "Competência",
    "Vencto": "Dia vencimento",
    "OC NOVA ": "OC NOVA",
}

AGREEMENT_HEADER_ALIASES = {
    "Mês": "Competência",
    "Mes": "Competência",
    "Acordo2": "Valor Acordo",
}

PAYMENT_NUMERIC_COLUMNS = [
    "Multa",
    "Juros",
    "Energia",
    "Outros",
    "Locação",
    "Subtotal",
]

AGREEMENT_NUMERIC_COLUMNS = [
    "Valor Acordo",
    "Multa + Juros",
]

FINANCE_AUDIT_COLUMNS = {
    "Importado em",
    "Atualizado em",
}


def ano_corrente():
    return date.today().year


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and math.isnan(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def normalizar_codigo_microsiga(valor):
    texto = _texto(valor)

    if texto.endswith(".0"):
        texto = texto[:-2]

    digitos = "".join(
        caractere
        for caractere in texto
        if caractere.isdigit()
    )

    if not digitos:
        return texto

    if len(digitos) <= 6:
        return digitos.zfill(6)

    return digitos


def _numero(valor):
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if pd.isna(valor):
            return 0.0
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return 0.0
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    numero = pd.to_numeric(texto, errors="coerce")
    if pd.isna(numero):
        return 0.0
    return float(numero)


def _excel_date(valor):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        texto = _texto(valor)
        data = pd.to_datetime(texto, errors="coerce", dayfirst=True)
        if pd.isna(data):
            return texto
        return data.date().isoformat()
    if numero <= 0:
        return ""
    return (date(1899, 12, 30) + timedelta(days=int(numero))).isoformat()


def _competencia(valor):
    return _excel_date(valor)


def _data_vencimento(competencia, dia):
    competencia_data = pd.to_datetime(competencia, errors="coerce")
    dia_numero = int(_numero(dia))
    if pd.isna(competencia_data) or dia_numero <= 0:
        return ""
    ultimo_dia = (competencia_data + pd.offsets.MonthEnd(0)).day
    dia_numero = min(dia_numero, int(ultimo_dia))
    return date(int(competencia_data.year), int(competencia_data.month), dia_numero).isoformat()


def _ano_valido(valor, minimo=None):
    minimo = minimo or ano_corrente()
    ano = int(_numero(valor))
    return ano >= minimo


def _competencia_ano_valido(valor, minimo=None):
    minimo = minimo or ano_corrente()
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return False
    return int(data.year) >= minimo


def filtrar_periodo_operacional_pagamentos(df, ano_minimo=None):
    if df is None or df.empty or "Ano" not in df.columns:
        return pd.DataFrame(columns=PAYMENT_COLUMNS)

    ano_minimo = ano_minimo or ano_corrente()
    return df[
        df["Ano"].apply(
            lambda valor: _ano_valido(valor, ano_minimo)
        )
    ].copy()


def filtrar_periodo_operacional_acordos(df, ano_minimo=None):
    if df is None or df.empty or "Competência" not in df.columns:
        return pd.DataFrame(columns=AGREEMENT_COLUMNS)

    ano_minimo = ano_minimo or ano_corrente()
    return df[
        df["Competência"].apply(
            lambda valor: _competencia_ano_valido(valor, ano_minimo)
        )
    ].copy()


def _site_index(sites):
    indice = {}
    for site in (sites or {}).values():
        microsiga = normalizar_codigo_microsiga(getattr(site, "microsiga", ""))
        if not microsiga:
            continue
        indice[microsiga] = {
            "Código Aquiles": _texto(getattr(site, "codigo_topos", "")),
            "Nome SNMPc": _texto(getattr(site, "nome", "")),
            "Nome Site": _texto(getattr(site, "nome_cadastro", "")),
            "Site localizado": "Sim",
        }
    return indice


def vincular_site(registro, sites):
    microsiga = normalizar_codigo_microsiga(registro.get("Microsiga"))
    registro["Microsiga"] = microsiga
    vinculo = _site_index(sites).get(microsiga)
    if vinculo:
        registro.update(vinculo)
    else:
        registro.update({
            "Código Aquiles": "",
            "Nome SNMPc": "",
            "Nome Site": "",
            "Site localizado": "Não",
        })
    return registro


def _id_estavel(prefixo, registro, campos):
    partes = [prefixo]
    partes.extend(_texto(registro.get(campo)) for campo in campos)
    digest = hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:16]
    return f"{prefixo.upper()}-{digest}"


def _ler_excel(arquivo):
    return pd.ExcelFile(arquivo, engine="openpyxl")


def _normalizar_fonte_excel(fonte):
    if isinstance(fonte, pd.ExcelFile):
        return fonte, False

    return _ler_excel(fonte), True


def _normalizar_colunas(df, aliases):
    colunas = []
    usados = set()
    for coluna in df.columns:
        nome = aliases.get(_texto(coluna), _texto(coluna))
        if not nome:
            nome = f"Coluna {len(colunas) + 1}"
        base = nome
        contador = 2
        while nome in usados:
            nome = f"{base} {contador}"
            contador += 1
        colunas.append(nome)
        usados.add(nome)
    df = df.copy()
    df.columns = colunas
    return df


def ler_pagamentos_excel(arquivo):
    xl, fechar = _normalizar_fonte_excel(arquivo)

    try:
        if "Fechamento 2016 a 2025" not in xl.sheet_names:
            return pd.DataFrame(columns=PAYMENT_COLUMNS)
        df = pd.read_excel(
            xl,
            sheet_name="Fechamento 2016 a 2025",
            header=5,
            dtype=object,
        )
    finally:
        if fechar:
            xl.close()

    df = _normalizar_colunas(df, PAYMENT_HEADER_ALIASES)
    colunas_uteis = [col for col in df.columns if not str(col).startswith("Coluna")]
    df = df[colunas_uteis]
    df = df[df.get("Ano").notna() if "Ano" in df.columns else pd.Series(False, index=df.index)]
    registros = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _idx, linha in df.iterrows():
        registro = {coluna: _texto(linha.get(coluna)) for coluna in df.columns}
        if not any(_texto(registro.get(campo)) for campo in ["Nome", "Fornecedor", "Microsiga", "Subtotal"]):
            continue
        registro["Competência"] = _competencia(registro.get("Competência"))
        registro["Dia vencimento"] = _texto(registro.get("Dia vencimento"))
        registro["Data de vencimento"] = _data_vencimento(registro.get("Competência"), registro.get("Dia vencimento"))
        for coluna in PAYMENT_NUMERIC_COLUMNS:
            registro[coluna] = _numero(registro.get(coluna))
        registro["Status"] = "Pendente"
        registro["Observação interna"] = ""
        registro["Importado em"] = agora
        registro["Atualizado em"] = agora
        registro["ID SGS"] = _id_estavel(
            "pag",
            registro,
            ["Ano", "Competência", "Nome", "Fornecedor", "Microsiga", "OC Primário", "OC Secundário", "Subtotal"],
        )
        registros.append({coluna: registro.get(coluna, "") for coluna in PAYMENT_COLUMNS})
    return filtrar_periodo_operacional_pagamentos(
        pd.DataFrame(registros, columns=PAYMENT_COLUMNS)
    )


def ler_acordos_excel(arquivo):
    xl, fechar = _normalizar_fonte_excel(arquivo)

    try:
        if "Acordos" not in xl.sheet_names:
            return pd.DataFrame(columns=AGREEMENT_COLUMNS)
        df = pd.read_excel(
            xl,
            sheet_name="Acordos",
            header=8,
            dtype=object,
        )
    finally:
        if fechar:
            xl.close()

    df = _normalizar_colunas(df, AGREEMENT_HEADER_ALIASES)
    colunas = [col for col in ["Obs", "Competência", "Acordo", "Nome", "Resp", "Aprovado Sindico", "PAGO", "Microsiga", "Valor Acordo", "Descrição", "Multa + Juros"] if col in df.columns]
    df = df[colunas]
    if "Nome" in df.columns:
        df = df[df["Nome"].notna()]
    registros = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _idx, linha in df.iterrows():
        registro = {coluna: _texto(linha.get(coluna)) for coluna in df.columns}
        if not any(_texto(registro.get(campo)) for campo in ["Nome", "Microsiga", "Valor Acordo", "Descrição"]):
            continue
        registro["Competência"] = _competencia(registro.get("Competência"))
        for coluna in AGREEMENT_NUMERIC_COLUMNS:
            registro[coluna] = _numero(registro.get(coluna))
        pago = _texto(registro.get("PAGO")).casefold()
        aprovado = _texto(registro.get("Aprovado Sindico")).casefold()
        if pago == "sim":
            status = "Quitado"
        elif aprovado == "sim":
            status = "Aprovado"
        else:
            status = "Em negociação"
        registro["Status"] = status
        registro["Observação interna"] = ""
        registro["Importado em"] = agora
        registro["Atualizado em"] = agora
        registro["ID SGS"] = _id_estavel(
            "aco",
            registro,
            ["Competência", "Nome", "Microsiga", "Valor Acordo", "Descrição"],
        )
        registros.append({coluna: registro.get(coluna, "") for coluna in AGREEMENT_COLUMNS})
    return filtrar_periodo_operacional_acordos(
        pd.DataFrame(registros, columns=AGREEMENT_COLUMNS)
    )


def carregar_pagamentos():
    return filtrar_periodo_operacional_pagamentos(
        pd.DataFrame(read_json(PAYMENTS_FILE, []), columns=PAYMENT_COLUMNS)
    )


def carregar_acordos():
    return filtrar_periodo_operacional_acordos(
        pd.DataFrame(read_json(AGREEMENTS_FILE, []), columns=AGREEMENT_COLUMNS)
    )


def salvar_pagamentos(df):
    write_json_atomic(
        PAYMENTS_FILE,
        _records(
            filtrar_periodo_operacional_pagamentos(df),
            PAYMENT_COLUMNS
        )
    )


def salvar_acordos(df):
    write_json_atomic(
        AGREEMENTS_FILE,
        _records(
            filtrar_periodo_operacional_acordos(df),
            AGREEMENT_COLUMNS
        )
    )


def _records(df, columns):
    if df is None or df.empty:
        return []
    data = df.copy()
    for coluna in columns:
        if coluna not in data.columns:
            data[coluna] = ""
    data = data[columns]
    return data.where(pd.notna(data), "").to_dict(orient="records")


def _mesclar_por_id(df_atual, df_novo, colunas, preservar_edicao=True):
    if df_atual is None or df_atual.empty:
        return df_novo.copy(), {"novos": len(df_novo), "atualizados": 0, "duplicados": 0}
    atual = df_atual.copy()
    novo = df_novo.copy()
    atual_por_id = {row["ID SGS"]: row for row in atual.to_dict(orient="records")}
    novos = 0
    atualizados = 0
    duplicados = 0
    for row in novo.to_dict(orient="records"):
        chave = row.get("ID SGS")
        if chave in atual_por_id:
            existente = atual_por_id[chave]
            if preservar_edicao:
                row["Status"] = existente.get("Status", row.get("Status"))
                row["Observação interna"] = existente.get("Observação interna", row.get("Observação interna"))
                row["Importado em"] = existente.get("Importado em", row.get("Importado em"))
            colunas_comparacao = [
                coluna
                for coluna in colunas
                if coluna not in FINANCE_AUDIT_COLUMNS
            ]
            if any(_texto(existente.get(c)) != _texto(row.get(c)) for c in colunas_comparacao):
                atualizados += 1
            else:
                duplicados += 1
            atual_por_id[chave] = row
        else:
            atual_por_id[chave] = row
            novos += 1
    resultado = pd.DataFrame(list(atual_por_id.values()), columns=colunas)
    return resultado, {"novos": novos, "atualizados": atualizados, "duplicados": duplicados}


def importar_planilha_financeira(arquivo, sites=None, salvar=False, usuario=""):
    xl = _ler_excel(arquivo)

    try:
        pagamentos = ler_pagamentos_excel(xl)
        acordos = ler_acordos_excel(xl)
    finally:
        xl.close()

    if sites is not None:
        pagamentos = pagamentos.apply(lambda row: pd.Series(vincular_site(row.to_dict(), sites)), axis=1) if not pagamentos.empty else pagamentos
        acordos = acordos.apply(lambda row: pd.Series(vincular_site(row.to_dict(), sites)), axis=1) if not acordos.empty else acordos
        pagamentos = pagamentos[PAYMENT_COLUMNS]
        acordos = acordos[AGREEMENT_COLUMNS]
    pagamentos_mesclados, resumo_pag = _mesclar_por_id(carregar_pagamentos(), pagamentos, PAYMENT_COLUMNS)
    acordos_mesclados, resumo_aco = _mesclar_por_id(carregar_acordos(), acordos, AGREEMENT_COLUMNS)
    resumo = {
        "pagamentos": {
            **resumo_pag,
            "importados": len(pagamentos),
            "com_site": int((pagamentos.get("Site localizado", pd.Series(dtype=str)) == "Sim").sum()) if not pagamentos.empty else 0,
            "sem_site": int((pagamentos.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not pagamentos.empty else 0,
            "sem_microsiga": int(pagamentos.get("Microsiga", pd.Series(dtype=str)).astype(str).str.strip().eq("").sum()) if not pagamentos.empty else 0,
        },
        "acordos": {
            **resumo_aco,
            "importados": len(acordos),
            "com_site": int((acordos.get("Site localizado", pd.Series(dtype=str)) == "Sim").sum()) if not acordos.empty else 0,
            "sem_site": int((acordos.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not acordos.empty else 0,
            "sem_microsiga": int(acordos.get("Microsiga", pd.Series(dtype=str)).astype(str).str.strip().eq("").sum()) if not acordos.empty else 0,
        },
    }
    if salvar:
        salvar_pagamentos(pagamentos_mesclados)
        salvar_acordos(acordos_mesclados)
        registrar_log_sistema(
            "financeiro_importacao",
            usuario=usuario,
            status="sucesso",
            detalhes=resumo,
        )
    return {
        "pagamentos": pagamentos,
        "acordos": acordos,
        "pagamentos_mesclados": pagamentos_mesclados,
        "acordos_mesclados": acordos_mesclados,
        "resumo": resumo,
    }


def status_pagamento_exibicao(row, hoje=None):
    status = _texto(row.get("Status")) or "Pendente"
    if status in {"Pago", "Cancelado", "Exportado"}:
        return status
    hoje = hoje or date.today()
    venc = pd.to_datetime(row.get("Data de vencimento"), errors="coerce")
    if not pd.isna(venc) and venc.date() < hoje:
        return "Vencido"
    return status


def preparar_pagamentos_exibicao(df=None):
    df = carregar_pagamentos() if df is None else df.copy()
    if df.empty:
        return pd.DataFrame(columns=PAYMENT_COLUMNS)
    df["Status Atual"] = df.apply(status_pagamento_exibicao, axis=1)
    return df


def dashboard_financeiro():
    pagamentos = preparar_pagamentos_exibicao()
    acordos = carregar_acordos()
    total_pendente = 0.0
    total_vencido = 0.0
    proximos_30 = 0.0
    hoje = date.today()
    if not pagamentos.empty:
        pendentes = pagamentos[~pagamentos["Status Atual"].isin(["Pago", "Cancelado"])]
        total_pendente = float(pendentes["Subtotal"].sum())
        total_vencido = float(pagamentos.loc[pagamentos["Status Atual"].eq("Vencido"), "Subtotal"].sum())
        datas = pd.to_datetime(pagamentos["Data de vencimento"], errors="coerce")
        mask_30 = datas.dt.date.between(hoje, hoje + timedelta(days=30)) & ~pagamentos["Status Atual"].isin(["Pago", "Cancelado"])
        proximos_30 = float(pagamentos.loc[mask_30.fillna(False), "Subtotal"].sum())
    acordos_abertos = 0
    total_acordos_abertos = 0.0
    if not acordos.empty:
        abertos = acordos[~acordos["Status"].isin(["Quitado", "Cancelado"])]
        acordos_abertos = len(abertos)
        total_acordos_abertos = float(abertos["Valor Acordo"].sum())
    return {
        "pagamentos": pagamentos,
        "acordos": acordos,
        "total_pendente": total_pendente,
        "total_vencido": total_vencido,
        "proximos_30": proximos_30,
        "acordos_abertos": acordos_abertos,
        "total_acordos_abertos": total_acordos_abertos,
    }


def dataframe_para_excel(df, sheet_name="Dados"):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Dados")
    buffer.seek(0)
    return buffer.getvalue()
