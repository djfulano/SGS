from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.config import CONFIG_DIR
from app.logs import registrar_log_sistema
from app.services.site_registry_service import load_site_registry
from app.services.site_metrics import sites_descendentes
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
    "Fonte",
    "Status Fonte",
    "Empresa",
    "Aprovação/Negociação",
    "OC / Conta Contábil",
    "Data relatório",
    "Conciliação",
    "Dias em atraso fonte",
    "Prazo suspensão/negativação",
    "Data programada pagamento",
    "Vencimento original",
    "Projeção",
    "Banco pagamento",
    "Favorecido",
    "Nota Fiscal",
    "Conta Financeira",
    "Valor principal",
    "Ajustes",
    "Valor Total a Pagar",
    "Informação extra",
    "Tipo de despesa",
    "PF/PJ",
    "Referente",
    "Despesas",
    "Observação fonte",
    "Vencimento auxiliar",
    "Valor auxiliar",
    "Data pagamento auxiliar",
    "Multa auxiliar",
    "Dias auxiliar",
    "Mora auxiliar",
    "Total a pagar auxiliar",
    "Total pago auxiliar",
    "Diferença a pagar auxiliar",
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
    "ID Pagamento",
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
    "Fonte",
    "Tipo de despesa",
    "Data de vencimento",
    "Data programada pagamento",
    "Prioridade",
    "Favorecido",
    "Aprovação/Negociação",
    "OC / Conta Contábil",
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
    "Valor principal",
    "Ajustes",
    "Valor Total a Pagar",
    "Valor auxiliar",
    "Multa auxiliar",
    "Mora auxiliar",
    "Total a pagar auxiliar",
    "Total pago auxiliar",
    "Diferença a pagar auxiliar",
]

AGREEMENT_NUMERIC_COLUMNS = [
    "Valor Acordo",
    "Multa + Juros",
]

FINANCE_AUDIT_COLUMNS = {
    "Importado em",
    "Atualizado em",
}

TOPO_SHEET = "TOPOS"
TOPO_SOURCE = "TOPO EM ABERTO"
TOPO_AGREEMENT_TYPE = "ACORDO/PARCELAMENTO"
TOPO_RECURRING_TYPE = "RECORRENTE"

TOPO_COLUMNS = {
    "ANO": "Ano",
    "COMPETÊNCIA MÊS DO VENCIMENTO": "Competência",
    "EMP": "Empresa",
    "STATUS (A VENCER/PAGO/ EM ATRASO)": "Status Fonte",
    "APROVAÇÃO/NEGOCIAÇÃO": "Aprovação/Negociação",
    "O.C / CONTA CONTÁBIL": "OC / Conta Contábil",
    "DATA RELATÓRIO (PREENCHER A DATA QUE RECEBEU PARA INCLUSÃO)": "Data relatório",
    "CONCILIAÇÃO": "Conciliação",
    "DIAS EM ATRASO - VCTO X DATA PGTO": "Dias em atraso fonte",
    "PRAZO SUSPENSÃO SERVIÇOS / NEGATIVAÇÃO": "Prazo suspensão/negativação",
    "DATA PAGAMENTO (FLUXO DE CAIXA)": "Data programada pagamento",
    "VENCIMENTO ORIGINAL": "Vencimento original",
    "PROJEÇÃO": "Projeção",
    "BANCO PGTO": "Banco pagamento",
    "PRIORIDADE": "Prioridade",
    "TIPO PGTO": "Tipo",
    "FAVORECIDO": "Favorecido",
    "N° Nota Fiscal (informação referente a despesa/entrada)": "Nota Fiscal",
    "CONTA FINANCEIRA": "Conta Financeira",
    "VALOR": "Valor principal",
    "JUROS/DESC/CRED/DIF A PAGAR": "Ajustes",
    "VALOR TOTAL A PAGAR": "Valor Total a Pagar",
    "INFORMAÇÃO EXTRA (DESCRIÇÃO DO SERVIÇO)": "Informação extra",
    "TIPO DE DESPESA": "Tipo de despesa",
    "PF/PJ": "PF/PJ",
    "VENCIMENTO": "Vencimento auxiliar",
    "Valor": "Valor auxiliar",
    "Data Pagamento": "Data pagamento auxiliar",
    "Multa": "Multa auxiliar",
    "Dias": "Dias auxiliar",
    "Mora": "Mora auxiliar",
    "Total a Pagar": "Total a pagar auxiliar",
    "Total pago": "Total pago auxiliar",
    "Diferença a pagar": "Diferença a pagar auxiliar",
    "COMPETÊNCIA": "Competência fonte",
    "REFERENTE": "Referente",
    "DESPESAS": "Despesas",
    "DESCRIÇÃO": "Descrição",
    "OBSERVAÇÃO - APURAÇÃO PROJEÇÃO": "Observação fonte",
    "NOME BANCO": "Banco",
    "BANCO": "Cód",
    "AG": "Agência",
    "CC": "C/Corrente",
    "CNPJ/CPF": "CNPJ/CPF",
    "CHAVE PIX": "PIX",
    "MULTA": "Multa",
    "JUROS": "Juros",
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
        formato_iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}", texto))
        data = pd.to_datetime(
            texto,
            errors="coerce",
            dayfirst=not formato_iso,
            yearfirst=formato_iso,
        )
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


def _registro_site_financeiro(
    microsiga,
    codigo_aquiles,
    nome_snmpc,
    nome_site,
    status,
):
    return {
        "microsiga": normalizar_codigo_microsiga(microsiga),
        "codigo_topos": _texto(codigo_aquiles),
        "nome": _texto(nome_snmpc),
        "nome_cadastro": _texto(nome_site),
        "status_cadastro": _texto(status),
    }


def sites_financeiros_cadastrados(sites=None, cadastro_sites=None):
    """Retorna o cadastro completo usado pelos vínculos financeiros."""
    cadastro = load_site_registry() if cadastro_sites is None else cadastro_sites.copy()
    registros = []
    vistos = set()
    codigos_cadastro = set()

    if cadastro is not None and not cadastro.empty:
        for linha in cadastro.to_dict(orient="records"):
            site = _registro_site_financeiro(
                linha.get("CÓDIGO MICROSIGA"),
                linha.get("CÓDIGO AQUILES"),
                linha.get("SMNPC"),
                linha.get("NOME"),
                linha.get("Status"),
            )
            chave = (site["microsiga"], site["codigo_topos"], site["nome"])
            if site["microsiga"] and chave not in vistos:
                registros.append(site)
                vistos.add(chave)
                codigos_cadastro.add(site["microsiga"])

    # Mantém compatibilidade com sites técnicos ainda não presentes na planilha.
    for item in (sites or {}).values():
        site = _registro_site_financeiro(
            getattr(item, "microsiga", ""),
            getattr(item, "codigo_topos", ""),
            getattr(item, "nome", ""),
            getattr(item, "nome_cadastro", ""),
            getattr(item, "status_cadastro", ""),
        )
        chave = (site["microsiga"], site["codigo_topos"], site["nome"])
        if (
            site["microsiga"]
            and site["microsiga"] not in codigos_cadastro
            and chave not in vistos
        ):
            registros.append(site)
            vistos.add(chave)
    return registros


def _sites_por_microsiga(sites=None, cadastro_sites=None):
    indice = {}
    for site in sites_financeiros_cadastrados(sites, cadastro_sites):
        indice.setdefault(site["microsiga"], []).append(site)
    return indice


def _codigo_microsiga_registro(registro):
    codigo = normalizar_codigo_microsiga(registro.get("Microsiga"))
    if codigo:
        return codigo
    favorecido = (
        registro.get("Favorecido")
        or registro.get("Nome")
        or registro.get("Fornecedor")
    )
    return extrair_microsiga_favorecido(favorecido)


def vincular_site(registro, sites=None, cadastro_sites=None):
    microsiga = _codigo_microsiga_registro(registro)
    registro["Microsiga"] = microsiga
    candidatos = _sites_por_microsiga(sites, cadastro_sites).get(microsiga, [])
    if len(candidatos) == 1:
        site = candidatos[0]
        registro.update({
            "Código Aquiles": site["codigo_topos"],
            "Nome SNMPc": site["nome"],
            "Nome Site": site["nome_cadastro"],
            "Site localizado": "Sim",
        })
    else:
        registro.update({
            "Código Aquiles": "",
            "Nome SNMPc": "",
            "Nome Site": "",
            "Site localizado": "Não",
        })
    return registro


def enriquecer_vinculos_financeiros(
    df,
    sites=None,
    cadastro_sites=None,
    forcar=False,
):
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    indice = _sites_por_microsiga(sites, cadastro_sites)
    dados = df.copy()

    def enriquecer(linha):
        registro = linha.to_dict()
        codigo = _codigo_microsiga_registro(registro)
        registro["Microsiga"] = codigo
        if (
            not forcar
            and _texto(registro.get("Site localizado")).casefold() == "sim"
            and codigo
        ):
            return pd.Series(registro)
        candidatos = indice.get(codigo, []) if codigo else []
        if len(candidatos) == 1:
            site = candidatos[0]
            registro.update({
                "Código Aquiles": site["codigo_topos"],
                "Nome SNMPc": site["nome"],
                "Nome Site": site["nome_cadastro"],
                "Site localizado": "Sim",
            })
        else:
            registro.update({
                "Código Aquiles": "",
                "Nome SNMPc": "",
                "Nome Site": "",
                "Site localizado": "Não",
            })
        return pd.Series(registro)

    return dados.apply(enriquecer, axis=1)


def _id_estavel(prefixo, registro, campos):
    partes = [prefixo]
    partes.extend(_texto(registro.get(campo)) for campo in campos)
    digest = hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:16]
    return f"{prefixo.upper()}-{digest}"


def _ler_excel(arquivo):
    caminho = str(getattr(arquivo, "name", arquivo)).lower()
    engine = "xlrd" if caminho.endswith(".xls") else "openpyxl"
    return pd.ExcelFile(arquivo, engine=engine)


def formato_planilha_financeira(arquivo):
    xl, fechar = _normalizar_fonte_excel(arquivo)
    try:
        return TOPO_SOURCE if TOPO_SHEET in xl.sheet_names else "NOVO FECHAMENTO"
    finally:
        if fechar:
            xl.close()


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


def extrair_microsiga_favorecido(valor):
    correspondencia = re.search(r"(\d{6})\s*$", _texto(valor))
    return correspondencia.group(1) if correspondencia else ""


def _valor_data_fonte(valor):
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    return _excel_date(valor)


def _tipo_despesa(valor):
    return " ".join(_texto(valor).upper().split())


def ler_topos_em_aberto_excel(arquivo):
    xl, fechar = _normalizar_fonte_excel(arquivo)
    try:
        if TOPO_SHEET not in xl.sheet_names:
            return (
                pd.DataFrame(columns=PAYMENT_COLUMNS),
                pd.DataFrame(columns=AGREEMENT_COLUMNS),
            )
        fonte = pd.read_excel(
            xl,
            sheet_name=TOPO_SHEET,
            header=0,
            dtype=object,
        )
    finally:
        if fechar:
            xl.close()

    fonte.columns = [_texto(coluna) for coluna in fonte.columns]
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pagamentos = []
    acordos = []
    ocorrencias = {}

    for _idx, linha in fonte.iterrows():
        favorecido = _texto(linha.get("FAVORECIDO"))
        tipo_despesa = _tipo_despesa(linha.get("TIPO DE DESPESA"))
        valor_total = _numero(linha.get("VALOR TOTAL A PAGAR"))
        vencimento = _valor_data_fonte(linha.get("VENCIMENTO ORIGINAL"))
        if not any([favorecido, tipo_despesa, valor_total, vencimento]):
            continue

        registro = {coluna: "" for coluna in PAYMENT_COLUMNS}
        for origem, destino in TOPO_COLUMNS.items():
            registro[destino] = linha.get(origem, "")

        for coluna in PAYMENT_COLUMNS:
            if coluna not in PAYMENT_NUMERIC_COLUMNS:
                registro[coluna] = _texto(registro.get(coluna))
        for coluna in PAYMENT_NUMERIC_COLUMNS:
            registro[coluna] = _numero(registro.get(coluna))

        for coluna in [
            "Competência",
            "Data relatório",
            "Data programada pagamento",
            "Vencimento original",
            "Vencimento auxiliar",
            "Data pagamento auxiliar",
        ]:
            registro[coluna] = _valor_data_fonte(registro.get(coluna))

        registro["Fonte"] = TOPO_SOURCE
        registro["Status"] = "Pendente"
        registro["Tipo de despesa"] = tipo_despesa
        registro["Microsiga"] = extrair_microsiga_favorecido(favorecido)
        registro["Nome"] = favorecido
        registro["Fornecedor"] = favorecido
        registro["Data de vencimento"] = registro["Vencimento original"]
        registro["Subtotal"] = valor_total
        registro["Valor Total a Pagar"] = valor_total
        registro["Descrição"] = (
            _texto(registro.get("Descrição"))
            or _texto(registro.get("Informação extra"))
        )
        registro["OC Primário"] = _texto(registro.get("OC / Conta Contábil"))
        registro["Observação interna"] = ""
        registro["Importado em"] = agora
        registro["Atualizado em"] = agora

        identidade = (
            registro["Microsiga"],
            registro["Vencimento original"],
            tipo_despesa,
            f"{valor_total:.6f}",
            favorecido,
            _texto(registro.get("OC / Conta Contábil")),
        )
        ocorrencias[identidade] = ocorrencias.get(identidade, 0) + 1
        registro["ID SGS"] = _id_estavel(
            "topo",
            {**registro, "Ocorrência": ocorrencias[identidade]},
            [
                "Microsiga",
                "Vencimento original",
                "Tipo de despesa",
                "Valor Total a Pagar",
                "Favorecido",
                "OC / Conta Contábil",
                "Ocorrência",
            ],
        )
        pagamentos.append(registro)

        if tipo_despesa == TOPO_AGREEMENT_TYPE:
            acordo = {coluna: "" for coluna in AGREEMENT_COLUMNS}
            acordo.update({
                "ID SGS": registro["ID SGS"].replace("TOPO-", "ACO-", 1),
                "ID Pagamento": registro["ID SGS"],
                "Status": "Em pagamento",
                "Competência": registro["Competência"],
                "Acordo": registro["Aprovação/Negociação"],
                "Nome": favorecido,
                "Aprovado Sindico": registro["Aprovação/Negociação"],
                "PAGO": "NÃO",
                "Microsiga": registro["Microsiga"],
                "Valor Acordo": valor_total,
                "Descrição": registro["Descrição"],
                "Multa + Juros": registro["Multa"] + registro["Juros"],
                "Fonte": TOPO_SOURCE,
                "Tipo de despesa": tipo_despesa,
                "Data de vencimento": registro["Data de vencimento"],
                "Data programada pagamento": registro["Data programada pagamento"],
                "Prioridade": registro["Prioridade"],
                "Favorecido": favorecido,
                "Aprovação/Negociação": registro["Aprovação/Negociação"],
                "OC / Conta Contábil": registro["OC / Conta Contábil"],
                "Observação interna": "",
                "Importado em": agora,
                "Atualizado em": agora,
            })
            acordos.append(acordo)

    return (
        pd.DataFrame(pagamentos, columns=PAYMENT_COLUMNS),
        pd.DataFrame(acordos, columns=AGREEMENT_COLUMNS),
    )


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
    return pd.DataFrame(read_json(PAYMENTS_FILE, []), columns=PAYMENT_COLUMNS)


def carregar_acordos():
    return pd.DataFrame(read_json(AGREEMENTS_FILE, []), columns=AGREEMENT_COLUMNS)


def salvar_pagamentos(df):
    write_json_atomic(
        PAYMENTS_FILE,
        _records(df, PAYMENT_COLUMNS)
    )


def salvar_acordos(df):
    write_json_atomic(
        AGREEMENTS_FILE,
        _records(df, AGREEMENT_COLUMNS)
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


def importar_planilha_financeira(
    arquivo,
    sites=None,
    salvar=False,
    usuario="",
    substituir_base_antiga=False,
):
    xl = _ler_excel(arquivo)

    try:
        formato = TOPO_SOURCE if TOPO_SHEET in xl.sheet_names else "NOVO FECHAMENTO"
        if formato == TOPO_SOURCE:
            pagamentos, acordos = ler_topos_em_aberto_excel(xl)
        else:
            pagamentos = ler_pagamentos_excel(xl)
            acordos = ler_acordos_excel(xl)
    finally:
        xl.close()

    cadastro_sites = load_site_registry()
    pagamentos = enriquecer_vinculos_financeiros(
        pagamentos,
        sites=sites,
        cadastro_sites=cadastro_sites,
        forcar=True,
    )
    acordos = enriquecer_vinculos_financeiros(
        acordos,
        sites=sites,
        cadastro_sites=cadastro_sites,
        forcar=True,
    )
    pagamentos = pagamentos[PAYMENT_COLUMNS]
    acordos = acordos[AGREEMENT_COLUMNS]

    pagamentos_atuais = carregar_pagamentos()
    acordos_atuais = carregar_acordos()
    primeira_importacao_topos = (
        formato == TOPO_SOURCE
        and not pagamentos_atuais.get("Fonte", pd.Series(dtype=str)).eq(TOPO_SOURCE).any()
    )
    requer_substituicao = primeira_importacao_topos and (
        not pagamentos_atuais.empty or not acordos_atuais.empty
    )
    if salvar and requer_substituicao and not substituir_base_antiga:
        raise ValueError(
            "A primeira importação de TOPO EM ABERTO exige confirmação para substituir a base financeira antiga."
        )

    base_pagamentos = (
        pd.DataFrame(columns=PAYMENT_COLUMNS)
        if primeira_importacao_topos and substituir_base_antiga
        else pagamentos_atuais
    )
    base_acordos = (
        pd.DataFrame(columns=AGREEMENT_COLUMNS)
        if primeira_importacao_topos and substituir_base_antiga
        else acordos_atuais
    )
    pagamentos_mesclados, resumo_pag = _mesclar_por_id(base_pagamentos, pagamentos, PAYMENT_COLUMNS)
    acordos_mesclados, resumo_aco = _mesclar_por_id(base_acordos, acordos, AGREEMENT_COLUMNS)

    pagamentos_status = preparar_pagamentos_exibicao(pagamentos)
    vencidos = int(pagamentos_status["Status Atual"].eq("Vencido").sum()) if not pagamentos_status.empty else 0
    programados = len(pagamentos_status) - vencidos
    resumo = {
        "formato": formato,
        "primeira_importacao_topos": primeira_importacao_topos,
        "requer_substituicao_base_antiga": requer_substituicao,
        "pagamentos": {
            **resumo_pag,
            "importados": len(pagamentos),
            "com_site": int((pagamentos.get("Site localizado", pd.Series(dtype=str)) == "Sim").sum()) if not pagamentos.empty else 0,
            "sem_site": int((pagamentos.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not pagamentos.empty else 0,
            "sem_microsiga": int(pagamentos.get("Microsiga", pd.Series(dtype=str)).astype(str).str.strip().eq("").sum()) if not pagamentos.empty else 0,
            "vencidos": vencidos,
            "programados": programados,
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
        "formato": formato,
        "primeira_importacao_topos": primeira_importacao_topos,
        "requer_substituicao_base_antiga": requer_substituicao,
        "pagamentos": pagamentos,
        "acordos": acordos,
        "pagamentos_mesclados": pagamentos_mesclados,
        "acordos_mesclados": acordos_mesclados,
        "resumo": resumo,
    }


def status_pagamento_exibicao(row, hoje=None):
    status = _texto(row.get("Status")) or "Pendente"
    if status in {"Pago", "Cancelado"}:
        return status
    hoje = hoje or date.today()
    venc = pd.to_datetime(row.get("Data de vencimento"), errors="coerce")
    if not pd.isna(venc) and venc.date() < hoje:
        return "Vencido"
    return status


def preparar_pagamentos_exibicao(
    df=None,
    hoje=None,
    enriquecer=True,
    cadastro_sites=None,
):
    df = carregar_pagamentos() if df is None else df.copy()
    if df.empty:
        return pd.DataFrame(columns=PAYMENT_COLUMNS)
    if enriquecer:
        df = enriquecer_vinculos_financeiros(
            df,
            cadastro_sites=cadastro_sites,
        )
    df["Status Atual"] = df.apply(
        lambda row: status_pagamento_exibicao(row, hoje=hoje),
        axis=1,
    )
    return df


def preparar_acordos_exibicao(df=None, cadastro_sites=None):
    df = carregar_acordos() if df is None else df.copy()
    if df.empty:
        return pd.DataFrame(columns=AGREEMENT_COLUMNS)
    return enriquecer_vinculos_financeiros(
        df,
        cadastro_sites=cadastro_sites,
    )


def _abertos_pagamentos(pagamentos):
    if pagamentos.empty:
        return pagamentos.copy()
    return pagamentos[~pagamentos["Status Atual"].isin(["Pago", "Cancelado"])].copy()


def _abertos_acordos(acordos, pagamentos=None):
    if acordos.empty:
        return acordos.copy()
    abertos = acordos[~acordos["Status"].isin(["Quitado", "Cancelado"])].copy()
    if pagamentos is None or pagamentos.empty or "ID Pagamento" not in abertos.columns:
        return abertos
    fechados = set(
        pagamentos.loc[
            pagamentos["Status Atual"].isin(["Pago", "Cancelado"]),
            "ID SGS",
        ].astype(str)
    )
    return abertos[~abertos["ID Pagamento"].astype(str).isin(fechados)].copy()


def _serie_mensal(df, coluna_data, coluna_valor="Subtotal"):
    if df.empty or coluna_data not in df.columns:
        return pd.DataFrame(columns=["Mês", "Valor"])
    dados = df.copy()
    dados["_data"] = pd.to_datetime(dados[coluna_data], errors="coerce")
    dados["_valor"] = pd.to_numeric(dados.get(coluna_valor, 0), errors="coerce").fillna(0.0)
    dados = dados[dados["_data"].notna()]
    if dados.empty:
        return pd.DataFrame(columns=["Mês", "Valor"])
    dados["Mês"] = dados["_data"].dt.to_period("M").astype(str)
    return dados.groupby("Mês", as_index=False)["_valor"].sum().rename(columns={"_valor": "Valor"})


def _programacao_mensal_por_tipo(df, inicio=None):
    colunas = ["Mês", "Mensalidades", "Acordos", "Total"]
    if df.empty or "Data de vencimento" not in df.columns or "Tipo de despesa" not in df.columns:
        return pd.DataFrame(columns=colunas)

    dados = df.copy()
    dados["_data"] = pd.to_datetime(dados["Data de vencimento"], errors="coerce")
    dados["_valor"] = pd.to_numeric(dados.get("Subtotal", 0), errors="coerce").fillna(0.0)
    dados["_categoria"] = dados["Tipo de despesa"].apply(_tipo_despesa).map({
        TOPO_RECURRING_TYPE: "Mensalidades",
        TOPO_AGREEMENT_TYPE: "Acordos",
    })
    dados = dados[dados["_data"].notna() & dados["_categoria"].notna()]
    if dados.empty:
        return pd.DataFrame(columns=colunas)

    dados["Mês"] = dados["_data"].dt.to_period("M").astype(str)
    serie = dados.pivot_table(
        index="Mês",
        columns="_categoria",
        values="_valor",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    serie.columns.name = None
    for coluna in ["Mensalidades", "Acordos"]:
        if coluna not in serie.columns:
            serie[coluna] = 0.0
    serie["Total"] = serie["Mensalidades"] + serie["Acordos"]
    serie = serie[colunas].sort_values("Mês").reset_index(drop=True)

    if inicio is not None and not serie.empty:
        periodo_inicial = pd.Period(pd.Timestamp(inicio), freq="M")
        periodo_final = pd.Period(serie["Mês"].max(), freq="M")
        meses = pd.period_range(periodo_inicial, periodo_final, freq="M").astype(str)
        serie = (
            serie.set_index("Mês")
            .reindex(meses, fill_value=0.0)
            .rename_axis("Mês")
            .reset_index()
        )
    return serie[colunas]


def _aging_atrasados(atrasados, hoje):
    faixas = ["0-30", "31-90", "91-180", "181-365", "Mais de 365"]
    if atrasados.empty:
        return pd.DataFrame({"Faixa": faixas, "Quantidade": 0, "Valor": 0.0})
    dados = atrasados.copy()
    datas = pd.to_datetime(dados["Data de vencimento"], errors="coerce")
    dados["_dias"] = datas.apply(lambda valor: (hoje - valor.date()).days if not pd.isna(valor) else -1)
    dados["Faixa"] = pd.cut(
        dados["_dias"],
        bins=[-1, 30, 90, 180, 365, float("inf")],
        labels=faixas,
    )
    dados["_valor"] = pd.to_numeric(dados["Subtotal"], errors="coerce").fillna(0.0)
    resumo = dados.groupby("Faixa", observed=False).agg(
        Quantidade=("ID SGS", "count"),
        Valor=("_valor", "sum"),
    ).reset_index()
    resumo["Faixa"] = resumo["Faixa"].astype(str)
    return resumo


def _ranking_saldos(abertos):
    if abertos.empty:
        return pd.DataFrame(columns=["Nome Site", "Nome SNMPc", "Microsiga", "Obrigações", "Saldo em aberto"])
    vinculados = abertos[abertos.get("Site localizado", pd.Series(index=abertos.index, dtype=str)).eq("Sim")].copy()
    if vinculados.empty:
        return pd.DataFrame(columns=["Nome Site", "Nome SNMPc", "Microsiga", "Obrigações", "Saldo em aberto"])
    vinculados["_valor"] = pd.to_numeric(vinculados["Subtotal"], errors="coerce").fillna(0.0)
    return vinculados.groupby(
        ["Nome Site", "Nome SNMPc", "Microsiga"],
        dropna=False,
        as_index=False,
    ).agg(
        Obrigações=("ID SGS", "count"),
        **{"Saldo em aberto": ("_valor", "sum")},
    ).sort_values("Saldo em aberto", ascending=False).head(20)


def dashboard_financeiro(hoje=None):
    hoje = hoje or date.today()
    cadastro_sites = load_site_registry()
    pagamentos = preparar_pagamentos_exibicao(
        hoje=hoje,
        cadastro_sites=cadastro_sites,
    )
    acordos = preparar_acordos_exibicao(cadastro_sites=cadastro_sites)
    abertos = _abertos_pagamentos(pagamentos)
    atrasados = abertos[abertos["Status Atual"].eq("Vencido")].copy() if not abertos.empty else abertos
    acordos_abertos_df = _abertos_acordos(acordos, pagamentos)

    total_pendente = float(pd.to_numeric(abertos.get("Subtotal", 0), errors="coerce").fillna(0).sum()) if not abertos.empty else 0.0
    total_vencido = float(pd.to_numeric(atrasados.get("Subtotal", 0), errors="coerce").fillna(0).sum()) if not atrasados.empty else 0.0
    total_acordos_abertos = float(pd.to_numeric(acordos_abertos_df.get("Valor Acordo", 0), errors="coerce").fillna(0).sum()) if not acordos_abertos_df.empty else 0.0

    datas = pd.to_datetime(abertos.get("Data de vencimento", pd.Series(index=abertos.index, dtype=str)), errors="coerce")
    mask_30 = datas.dt.date.between(hoje, hoje + timedelta(days=30)) if not abertos.empty else pd.Series(dtype=bool)
    proximos_30 = float(pd.to_numeric(abertos.loc[mask_30.fillna(False), "Subtotal"], errors="coerce").fillna(0).sum()) if not abertos.empty else 0.0

    sites_acordo = set(acordos_abertos_df.loc[acordos_abertos_df["Site localizado"].eq("Sim"), "Microsiga"].astype(str)) if not acordos_abertos_df.empty else set()
    sites_atrasados = set(atrasados.loc[atrasados["Site localizado"].eq("Sim"), "Microsiga"].astype(str)) if not atrasados.empty else set()
    sem_vinculo = abertos[abertos.get("Site localizado", pd.Series(index=abertos.index, dtype=str)).eq("Não")] if not abertos.empty else abertos

    programados = abertos.copy()
    inicio_mes = hoje.replace(day=1)
    if not programados.empty:
        datas_programadas = pd.to_datetime(programados["Data de vencimento"], errors="coerce")
        programados = programados[datas_programadas.dt.date.ge(inicio_mes).fillna(False)]
    origem_mensal = _serie_mensal(atrasados, "Data de vencimento")
    acumulado = _serie_mensal(atrasados, "Data de vencimento")
    if not acumulado.empty:
        acumulado["Valor acumulado"] = acumulado["Valor"].cumsum()
    return {
        "pagamentos": pagamentos,
        "acordos": acordos,
        "total_pendente": total_pendente,
        "total_vencido": total_vencido,
        "proximos_30": proximos_30,
        "abertos": abertos,
        "atrasados": atrasados,
        "acordos_abertos_df": acordos_abertos_df,
        "acordos_abertos": len(acordos_abertos_df),
        "total_acordos_abertos": total_acordos_abertos,
        "sites_com_acordo": len(sites_acordo),
        "sites_atrasados_sem_acordo": len(sites_atrasados - sites_acordo),
        "sem_vinculo_quantidade": len(sem_vinculo),
        "sem_vinculo_valor": float(pd.to_numeric(sem_vinculo.get("Subtotal", 0), errors="coerce").fillna(0).sum()) if not sem_vinculo.empty else 0.0,
        "programacao_mensal": _programacao_mensal_por_tipo(programados, inicio=inicio_mes),
        "origem_mensal": origem_mensal,
        "acumulado_atrasados": acumulado,
        "aging": _aging_atrasados(atrasados, hoje),
        "ranking_saldos": _ranking_saldos(abertos),
    }


CONCILIATION_COLUMNS = [
    "Tipo do problema",
    "Origem",
    "ID SGS",
    "Favorecido",
    "Microsiga extraído",
    "Vínculo atual",
    "Status",
    "Vencimento",
    "Valor",
    "Descrição",
    "Ação sugerida",
]


def _linha_conciliacao(
    problema,
    origem,
    registro=None,
    microsiga="",
    vinculo="",
    valor=0.0,
    acao="",
):
    registro = registro or {}
    return {
        "Tipo do problema": problema,
        "Origem": origem,
        "ID SGS": _texto(registro.get("ID SGS")),
        "Favorecido": _texto(
            registro.get("Favorecido")
            or registro.get("Nome")
            or registro.get("Fornecedor")
        ),
        "Microsiga extraído": microsiga,
        "Vínculo atual": vinculo or _texto(registro.get("Nome SNMPc")),
        "Status": _texto(registro.get("Status Atual") or registro.get("Status")),
        "Vencimento": _texto(registro.get("Data de vencimento")),
        "Valor": float(valor or 0),
        "Descrição": _texto(
            registro.get("Descrição") or registro.get("Informação extra")
        ),
        "Ação sugerida": acao,
    }


def analisar_conciliacao_financeira(
    sites,
    pagamentos=None,
    acordos=None,
    cadastro_sites=None,
):
    cadastro_sites = (
        load_site_registry() if cadastro_sites is None else cadastro_sites.copy()
    )
    pagamentos = preparar_pagamentos_exibicao(pagamentos, enriquecer=False)
    acordos = carregar_acordos() if acordos is None else acordos.copy()
    pagamentos = enriquecer_vinculos_financeiros(
        pagamentos,
        sites=sites,
        cadastro_sites=cadastro_sites,
    )
    acordos = enriquecer_vinculos_financeiros(
        acordos,
        sites=sites,
        cadastro_sites=cadastro_sites,
    )
    indice_sites = _sites_por_microsiga(sites, cadastro_sites)
    problemas = []

    for codigo, sites_codigo in indice_sites.items():
        if len(sites_codigo) <= 1:
            continue
        nomes = "; ".join(
            sorted(_texto(site.get("nome")) for site in sites_codigo)
        )
        problemas.append(_linha_conciliacao(
            "Código Microsiga duplicado no cadastro",
            "Cadastro de Sites",
            microsiga=codigo,
            vinculo=nomes,
            acao="Revisar o Código Microsiga no cadastro dos sites.",
        ))

    payment_ids = set(
        pagamentos.get("ID SGS", pd.Series(dtype=str)).astype(str)
    )
    fontes = [
        ("Pagamento", pagamentos, "Subtotal"),
        ("Acordo", acordos, "Valor Acordo"),
    ]
    for origem, dataframe, coluna_valor in fontes:
        if dataframe is None or dataframe.empty:
            continue
        for registro in dataframe.to_dict(orient="records"):
            favorecido = (
                registro.get("Favorecido")
                or registro.get("Nome")
                or registro.get("Fornecedor")
            )
            microsiga = normalizar_codigo_microsiga(registro.get("Microsiga"))
            if not microsiga:
                microsiga = extrair_microsiga_favorecido(favorecido)
            valor = _numero(registro.get(coluna_valor))
            sites_codigo = indice_sites.get(microsiga, []) if microsiga else []
            vinculo_atual = _texto(registro.get("Nome SNMPc"))

            if not microsiga:
                problemas.append(_linha_conciliacao(
                    "Sem Código Microsiga",
                    origem,
                    registro,
                    valor=valor,
                    acao="Identificar o Código Microsiga e revisar o cadastro financeiro.",
                ))
            elif not sites_codigo:
                problemas.append(_linha_conciliacao(
                    "Código Microsiga não encontrado",
                    origem,
                    registro,
                    microsiga=microsiga,
                    valor=valor,
                    acao="Cadastrar ou corrigir o Código Microsiga na base de Sites.",
                ))
            elif len(sites_codigo) == 1:
                site_atual = sites_codigo[0]
                nome_atual = _texto(site_atual.get("nome"))
                codigo_aquiles_atual = _texto(site_atual.get("codigo_topos"))
                registro_aquiles = _texto(registro.get("Código Aquiles"))
                marcado_vinculado = _texto(registro.get("Site localizado")).casefold() == "sim"
                if not marcado_vinculado:
                    problemas.append(_linha_conciliacao(
                        "Registro não vinculado a site existente",
                        origem,
                        registro,
                        microsiga=microsiga,
                        valor=valor,
                        acao=f"Reprocessar o vínculo; o código pertence a {nome_atual}.",
                    ))
                divergente = marcado_vinculado and (
                    (vinculo_atual and vinculo_atual != nome_atual)
                    or (
                        registro_aquiles
                        and codigo_aquiles_atual
                        and registro_aquiles != codigo_aquiles_atual
                    )
                )
                if divergente:
                    problemas.append(_linha_conciliacao(
                        "Vínculo incompatível com o cadastro atual",
                        origem,
                        registro,
                        microsiga=microsiga,
                        vinculo=vinculo_atual,
                        valor=valor,
                        acao=f"Revisar o vínculo; o cadastro atual aponta para {nome_atual}.",
                    ))
                status_site = _texto(
                    site_atual.get("status_cadastro")
                ).casefold()
                if status_site and status_site != "ativo":
                    problemas.append(_linha_conciliacao(
                        "Vínculo com site inativo",
                        origem,
                        registro,
                        microsiga=microsiga,
                        vinculo=nome_atual,
                        valor=valor,
                        acao="Revisar a obrigação e o status cadastral do site.",
                    ))

            vencimento = pd.to_datetime(
                registro.get("Data de vencimento"), errors="coerce"
            )
            if pd.isna(vencimento):
                problemas.append(_linha_conciliacao(
                    "Vencimento ausente ou inválido",
                    origem,
                    registro,
                    microsiga=microsiga,
                    vinculo=vinculo_atual,
                    valor=valor,
                    acao="Revisar a data de vencimento na origem financeira.",
                ))
            if valor <= 0:
                problemas.append(_linha_conciliacao(
                    "Valor ausente, zero ou inválido",
                    origem,
                    registro,
                    microsiga=microsiga,
                    vinculo=vinculo_atual,
                    valor=valor,
                    acao="Revisar o valor da obrigação na origem financeira.",
                ))
            if origem == "Acordo":
                payment_id = _texto(registro.get("ID Pagamento"))
                if not payment_id or payment_id not in payment_ids:
                    problemas.append(_linha_conciliacao(
                        "Acordo sem pagamento de origem",
                        origem,
                        registro,
                        microsiga=microsiga,
                        vinculo=vinculo_atual,
                        valor=valor,
                        acao="Revisar o ID do pagamento relacionado ao acordo.",
                    ))

    if not problemas:
        return pd.DataFrame(columns=CONCILIATION_COLUMNS)
    return pd.DataFrame(problemas, columns=CONCILIATION_COLUMNS).sort_values(
        ["Tipo do problema", "Origem", "Favorecido", "ID SGS"],
        kind="stable",
    ).reset_index(drop=True)


def historico_financeiro_site(
    microsiga,
    pagamentos=None,
    acordos=None,
    hoje=None,
):
    codigo = normalizar_codigo_microsiga(microsiga)
    hoje = hoje or date.today()
    pagamentos = preparar_pagamentos_exibicao(pagamentos, hoje=hoje)
    acordos = preparar_acordos_exibicao(acordos)

    def filtrar_codigo(df):
        if df is None or df.empty or not codigo:
            return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
        codigos = df.get("Microsiga", pd.Series(index=df.index, dtype=str)).map(
            normalizar_codigo_microsiga
        )
        return df[codigos.eq(codigo)].copy()

    pagamentos_site = filtrar_codigo(pagamentos)
    acordos_site = filtrar_codigo(acordos)
    realizados = pagamentos_site[
        pagamentos_site.get(
            "Status Atual", pd.Series(index=pagamentos_site.index, dtype=str)
        ).eq("Pago")
    ].copy()
    pendencias = pagamentos_site[
        ~pagamentos_site.get(
            "Status Atual", pd.Series(index=pagamentos_site.index, dtype=str)
        ).isin(["Pago", "Cancelado"])
    ].copy()
    vencidas = pendencias[
        pendencias.get(
            "Status Atual", pd.Series(index=pendencias.index, dtype=str)
        ).eq("Vencido")
    ].copy()
    datas_pendencias = pd.to_datetime(
        pendencias.get(
            "Data de vencimento", pd.Series(index=pendencias.index, dtype=str)
        ),
        errors="coerce",
    )
    futuras = pendencias[
        datas_pendencias.notna() & datas_pendencias.dt.date.ge(hoje)
    ].copy()
    acordos_abertos = _abertos_acordos(acordos_site, pagamentos_site)

    def soma(df, coluna):
        if df is None or df.empty or coluna not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[coluna], errors="coerce").fillna(0).sum())

    return {
        "microsiga": codigo,
        "pagamentos": pagamentos_site,
        "realizados": realizados,
        "pendencias": pendencias,
        "vencidas": vencidas,
        "futuras": futuras,
        "acordos": acordos_site,
        "acordos_abertos": acordos_abertos,
        "valor_em_atraso": soma(vencidas, "Subtotal"),
        "parcelas_vencidas": len(vencidas),
        "valor_futuro": soma(futuras, "Subtotal"),
        "parcelas_futuras": len(futuras),
        "valor_acordos_abertos": soma(acordos_abertos, "Valor Acordo"),
        "quantidade_acordos_abertos": len(acordos_abertos),
        "valor_realizado": soma(realizados, "Subtotal"),
        "quantidade_realizada": len(realizados),
    }


def resumo_atraso_site(microsiga, pagamentos=None, hoje=None):
    historico = historico_financeiro_site(
        microsiga,
        pagamentos=pagamentos,
        acordos=pd.DataFrame(columns=AGREEMENT_COLUMNS),
        hoje=hoje,
    )
    return {
        "valor_em_atraso": historico["valor_em_atraso"],
        "parcelas_vencidas": historico["parcelas_vencidas"],
    }


def _clientes_unicos_sites(sites):
    clientes = {}
    for site in sites:
        for cliente in getattr(site, "clientes", []) or []:
            assinatura = _texto(getattr(cliente, "num_assinatura", ""))
            chave = assinatura or (
                f"{getattr(site, 'nome', '')}|"
                f"{_texto(getattr(cliente, 'nome', ''))}"
            )
            clientes.setdefault(chave, cliente)
    return clientes


def _resumo_clientes_sites(sites):
    clientes = _clientes_unicos_sites(sites)
    return {
        "clientes": len(clientes),
        "receita": sum(
            _numero(getattr(cliente, "receita", 0))
            for cliente in clientes.values()
        ),
    }


def _tipo_parcela_relatorio(valor):
    tipo = _tipo_despesa(valor)
    if tipo == TOPO_AGREEMENT_TYPE:
        return "Acordo"
    if tipo == TOPO_RECURRING_TYPE:
        return "Mensalidade"
    return _texto(valor) or "Não informado"


def montar_relatorio_financeiro_sites(
    sites_selecionados,
    pagamentos=None,
    hoje=None,
    cadastro_sites=None,
):
    hoje = hoje or date.today()
    selecionados = []
    nomes_vistos = set()
    for site in sites_selecionados or []:
        nome = _texto(getattr(site, "nome", ""))
        if not nome or nome in nomes_vistos:
            continue
        selecionados.append(site)
        nomes_vistos.add(nome)

    colunas_resumo = [
        "Nome",
        "Nome SNMPc",
        "Código Aquiles",
        "Código Microsiga",
        "Clientes Totais",
        "Receita Total",
        "Parcelas Atrasadas",
        "Valor em Atraso",
    ]
    colunas_parcelas = [
        "ID SGS",
        "Site",
        "Nome SNMPc",
        "Código Microsiga",
        "Favorecido",
        "Tipo",
        "Competência",
        "Vencimento",
        "Dias em Atraso",
        "Valor",
        "Prioridade",
        "OC",
        "Descrição",
        "Status",
    ]
    if not selecionados:
        return {
            "resumo": {
                "clientes_total": 0,
                "receita_total": 0.0,
                "parcelas_atrasadas": 0,
                "valor_em_atraso": 0.0,
            },
            "sites": pd.DataFrame(columns=colunas_resumo),
            "parcelas": pd.DataFrame(columns=colunas_parcelas),
            "sites_sem_microsiga": [],
        }

    pagamentos = preparar_pagamentos_exibicao(
        pagamentos,
        hoje=hoje,
        cadastro_sites=cadastro_sites,
    )
    atrasadas = pagamentos[
        pagamentos.get(
            "Status Atual",
            pd.Series(index=pagamentos.index, dtype=str),
        ).eq("Vencido")
    ].copy()
    if not atrasadas.empty:
        atrasadas["_microsiga"] = atrasadas.get(
            "Microsiga",
            pd.Series(index=atrasadas.index, dtype=str),
        ).map(normalizar_codigo_microsiga)
        atrasadas["_vencimento"] = pd.to_datetime(
            atrasadas.get("Data de vencimento"),
            errors="coerce",
        )
        atrasadas["_id_relatorio"] = [
            _texto(valor) or f"linha-{indice}"
            for indice, valor in zip(
                atrasadas.index,
                atrasadas.get(
                    "ID SGS",
                    pd.Series(index=atrasadas.index, dtype=str),
                ),
            )
        ]

    sites_escopo = {}
    for site in selecionados:
        for site_escopo in sites_descendentes(site):
            sites_escopo.setdefault(
                _texto(getattr(site_escopo, "nome", "")),
                site_escopo,
            )
    resumo_geral_clientes = _resumo_clientes_sites(sites_escopo.values())

    codigos_selecionados = {
        normalizar_codigo_microsiga(getattr(site, "microsiga", ""))
        for site in selecionados
        if normalizar_codigo_microsiga(getattr(site, "microsiga", ""))
    }
    atrasadas_selecionadas = (
        atrasadas[atrasadas["_microsiga"].isin(codigos_selecionados)].copy()
        if not atrasadas.empty
        else atrasadas
    )
    if not atrasadas_selecionadas.empty:
        atrasadas_selecionadas = atrasadas_selecionadas.drop_duplicates(
            "_id_relatorio",
            keep="first",
        )

    linhas_sites = []
    site_por_microsiga = {}
    sites_sem_microsiga = []
    for site in selecionados:
        microsiga = normalizar_codigo_microsiga(
            getattr(site, "microsiga", "")
        )
        if microsiga:
            site_por_microsiga.setdefault(microsiga, site)
        else:
            sites_sem_microsiga.append(
                _texto(getattr(site, "nome", ""))
            )
        parcelas_site = (
            atrasadas[atrasadas["_microsiga"].eq(microsiga)].copy()
            if microsiga and not atrasadas.empty
            else pd.DataFrame()
        )
        if not parcelas_site.empty:
            parcelas_site = parcelas_site.drop_duplicates(
                "_id_relatorio",
                keep="first",
            )
        resumo_clientes = _resumo_clientes_sites(
            sites_descendentes(site)
        )
        linhas_sites.append({
            "Nome": _texto(getattr(site, "nome_cadastro", "")),
            "Nome SNMPc": _texto(getattr(site, "nome", "")),
            "Código Aquiles": _texto(getattr(site, "codigo_topos", "")),
            "Código Microsiga": microsiga,
            "Clientes Totais": resumo_clientes["clientes"],
            "Receita Total": resumo_clientes["receita"],
            "Parcelas Atrasadas": len(parcelas_site),
            "Valor em Atraso": (
                float(
                    pd.to_numeric(
                        parcelas_site.get("Subtotal", 0),
                        errors="coerce",
                    ).fillna(0).sum()
                )
                if not parcelas_site.empty
                else 0.0
            ),
        })

    linhas_parcelas = []
    for _indice, parcela in atrasadas_selecionadas.sort_values(
        "_vencimento",
        kind="stable",
    ).iterrows():
        microsiga = parcela.get("_microsiga", "")
        site = site_por_microsiga.get(microsiga)
        vencimento = parcela.get("_vencimento")
        data_vencimento = None if pd.isna(vencimento) else vencimento.date()
        linhas_parcelas.append({
            "ID SGS": _texto(parcela.get("ID SGS")),
            "Site": (
                _texto(getattr(site, "nome_cadastro", ""))
                if site is not None
                else _texto(parcela.get("Nome Site"))
            ),
            "Nome SNMPc": (
                _texto(getattr(site, "nome", ""))
                if site is not None
                else _texto(parcela.get("Nome SNMPc"))
            ),
            "Código Microsiga": microsiga,
            "Favorecido": _texto(
                parcela.get("Favorecido")
                or parcela.get("Fornecedor")
                or parcela.get("Nome")
            ),
            "Tipo": _tipo_parcela_relatorio(
                parcela.get("Tipo de despesa")
            ),
            "Competência": _texto(parcela.get("Competência")),
            "Vencimento": (
                data_vencimento.isoformat()
                if data_vencimento is not None
                else ""
            ),
            "Dias em Atraso": (
                (hoje - data_vencimento).days
                if data_vencimento is not None
                else ""
            ),
            "Valor": _numero(parcela.get("Subtotal")),
            "Prioridade": _texto(parcela.get("Prioridade")),
            "OC": _texto(
                parcela.get("OC / Conta Contábil")
                or parcela.get("OC NOVA")
                or parcela.get("OC Primário")
            ),
            "Descrição": _texto(parcela.get("Descrição")),
            "Status": _texto(parcela.get("Status Atual")),
        })

    valor_em_atraso = (
        float(
            pd.to_numeric(
                atrasadas_selecionadas.get("Subtotal", 0),
                errors="coerce",
            ).fillna(0).sum()
        )
        if not atrasadas_selecionadas.empty
        else 0.0
    )
    return {
        "resumo": {
            "clientes_total": resumo_geral_clientes["clientes"],
            "receita_total": resumo_geral_clientes["receita"],
            "parcelas_atrasadas": len(atrasadas_selecionadas),
            "valor_em_atraso": valor_em_atraso,
        },
        "sites": pd.DataFrame(linhas_sites, columns=colunas_resumo),
        "parcelas": pd.DataFrame(linhas_parcelas, columns=colunas_parcelas),
        "sites_sem_microsiga": sites_sem_microsiga,
    }


def _moeda_relatorio_texto(valor):
    texto = f"{_numero(valor):,.2f}"
    return f"R$ {texto.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _data_relatorio_texto(valor):
    data = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(data) else data.strftime("%d/%m/%Y")


def texto_relatorio_financeiro_sites(
    relatorio,
    mostrar_receita=True,
    mostrar_valores_atraso=True,
    gerado_em=None,
):
    gerado_em = gerado_em or datetime.now()
    resumo = relatorio.get("resumo", {})
    linhas = [
        "RELATÓRIO FINANCEIRO POR SITES",
        f"Gerado em: {gerado_em:%d/%m/%Y %H:%M}",
        "",
        "RESUMO CONSOLIDADO",
        f"Clientes totais: {int(resumo.get('clientes_total', 0))}",
        (
            "Receita total: "
            + (
                _moeda_relatorio_texto(resumo.get("receita_total", 0))
                if mostrar_receita
                else "Restrito"
            )
        ),
        f"Parcelas atrasadas: {int(resumo.get('parcelas_atrasadas', 0))}",
        (
            "Valor total em atraso: "
            + (
                _moeda_relatorio_texto(resumo.get("valor_em_atraso", 0))
                if mostrar_valores_atraso
                else "Restrito"
            )
        ),
        "",
        "RESUMO POR SITE",
    ]
    for site in relatorio.get("sites", pd.DataFrame()).to_dict(orient="records"):
        linhas.extend([
            (
                f"- {site.get('Nome SNMPc') or '-'} - "
                f"{site.get('Código Aquiles') or '-'} / "
                f"{site.get('Nome') or '-'} - "
                f"{site.get('Código Microsiga') or '-'}"
            ),
            f"  Clientes totais: {int(site.get('Clientes Totais', 0))}",
            (
                "  Receita total: "
                + (
                    _moeda_relatorio_texto(site.get("Receita Total", 0))
                    if mostrar_receita
                    else "Restrito"
                )
            ),
            f"  Parcelas atrasadas: {int(site.get('Parcelas Atrasadas', 0))}",
            (
                "  Valor em atraso: "
                + (
                    _moeda_relatorio_texto(site.get("Valor em Atraso", 0))
                    if mostrar_valores_atraso
                    else "Restrito"
                )
            ),
            "",
        ])

    linhas.extend(["PARCELAS ATRASADAS"])
    parcelas = relatorio.get("parcelas", pd.DataFrame())
    if parcelas.empty:
        linhas.append("Nenhuma parcela atrasada para os sites selecionados.")
    else:
        for parcela in parcelas.to_dict(orient="records"):
            valor = (
                _moeda_relatorio_texto(parcela.get("Valor", 0))
                if mostrar_valores_atraso
                else "Restrito"
            )
            linhas.append(
                f"- {_data_relatorio_texto(parcela.get('Vencimento'))} | "
                f"{parcela.get('Nome SNMPc') or parcela.get('Site') or '-'} | "
                f"{parcela.get('Tipo') or '-'} | "
                f"{parcela.get('Favorecido') or '-'} | "
                f"{valor} | {parcela.get('Dias em Atraso') or 0} dia(s)"
            )
    return "\n".join(linhas)


def exportar_conciliacao_financeira_excel(df):
    return dataframe_para_excel(df, "Conciliação")


def dataframe_para_excel(df, sheet_name="Dados"):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Dados")
    buffer.seek(0)
    return buffer.getvalue()
