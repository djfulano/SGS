import pandas as pd

from app.config import MAP_CACHE_FILE
from app.reports.site_financials import montar_detalhes_topos
from app.services.clients import montar_base_clientes
from app.services.equipment_catalog import load_equipment_catalog
from app.services.product_catalog import load_product_catalog
from app.services.site_registry_service import load_site_contacts
from app.storage import read_json


def normalizar_status(valor):
    return str(valor or "").strip().casefold()


def aplicar_filtro_status_sites(df_sites, apenas_ativos=True):
    if df_sites.empty or not apenas_ativos or "Status Cadastro" not in df_sites.columns:
        return df_sites.copy()

    return df_sites[
        df_sites["Status Cadastro"].apply(normalizar_status).eq("ativo")
    ].copy()


def valor_float(serie):
    return pd.to_numeric(
        serie,
        errors="coerce"
    ).fillna(0)


def percentual(parte, total):
    return float(parte) / float(total) if float(total or 0) else 0.0


def carregar_cache_mapa():
    return read_json(
        MAP_CACHE_FILE,
        {}
    )


def mapa_nao_plotados_dataframe():
    cache = carregar_cache_mapa()
    nao_plotados = cache.get("nao_plotados") or []

    if not nao_plotados:
        return pd.DataFrame()

    return pd.DataFrame(nao_plotados)


def mapa_distancias_dataframe():
    cache = carregar_cache_mapa()
    registros = []

    for item in cache.get("links_clientes") or []:
        registros.append({
            "Tipo": "Cliente",
            "Site": item.get("Site") or "",
            "Destino": item.get("Cliente") or "",
            "Distância Km": item.get("Distância Km") or item.get("Distância Site Km") or 0
        })

    for item in cache.get("links_sites") or []:
        registros.append({
            "Tipo": "Site filho",
            "Site": item.get("Site Pai") or "",
            "Destino": item.get("Site Filho") or "",
            "Distância Km": item.get("Distância Km") or 0
        })

    return pd.DataFrame(registros)


def preparar_bases_insights(sites, equipamentos, apenas_ativos=True):
    df_sites = montar_detalhes_topos(sites)
    df_sites = aplicar_filtro_status_sites(
        df_sites,
        apenas_ativos=apenas_ativos
    )
    df_clientes = montar_base_clientes(
        sites,
        equipamentos
    )

    if apenas_ativos and not df_sites.empty and not df_clientes.empty:
        sites_ativos = set(
            df_sites["Site SNMPc"].dropna().astype(str)
        )
        df_clientes = df_clientes[
            (df_clientes["Site"].astype(str).isin(sites_ativos))
            | (df_clientes["Vínculo"].astype(str).eq("Sem vínculo"))
        ].copy()

    return df_sites, df_clientes


def resumo_geral(sites, equipamentos, apenas_ativos=True):
    df_sites, df_clientes = preparar_bases_insights(
        sites,
        equipamentos,
        apenas_ativos=apenas_ativos
    )
    resumo = resumo_geral_filtrado(
        df_sites,
        df_clientes,
        equipamentos
    )
    nao_plotados = mapa_nao_plotados_dataframe()
    resumo["Itens Não Plotados"] = len(nao_plotados)

    return resumo


def resumo_geral_filtrado(df_sites, df_clientes, equipamentos):
    receita = (
        valor_float(df_sites["Receita Total"]).sum()
        if "Receita Total" in df_sites.columns
        else 0
    )
    custo = (
        valor_float(df_sites["Custo"]).sum()
        if "Custo" in df_sites.columns
        else 0
    )
    resultado = receita - custo

    return {
        "Receita": receita,
        "Custo": custo,
        "Resultado": resultado,
        "Margem %": percentual(resultado, receita),
        "Sites": len(df_sites),
        "Clientes": df_clientes["Assinatura"].nunique() if "Assinatura" in df_clientes.columns else 0,
        "Produtos": df_clientes["Produto"].replace("", pd.NA).dropna().nunique() if "Produto" in df_clientes.columns else 0,
        "Equipamentos": len(equipamentos or []),
        "Sites Deficitários": len(sites_deficitarios(df_sites)),
        "Sites Sem Clientes": len(sites_sem_clientes(df_sites)),
        "Clientes Sem Vínculo": len(clientes_sem_vinculo(df_clientes)),
        "Clientes Sem Equipamento": len(clientes_sem_equipamento(df_clientes)),
        "Itens Não Plotados": 0
    }


def sites_deficitarios(df_sites):
    if df_sites.empty:
        return pd.DataFrame()

    df = df_sites.copy()
    df["Resultado"] = valor_float(df.get("Resultado", 0))

    return df[df["Resultado"] < 0].sort_values(
        by="Resultado"
    )


def sites_sem_clientes(df_sites):
    if df_sites.empty or "Clientes Total" not in df_sites.columns:
        return pd.DataFrame()

    df = df_sites.copy()
    df["Clientes Total"] = valor_float(df["Clientes Total"])

    return df[df["Clientes Total"] == 0].sort_values(
        by="Custo",
        ascending=False
    )


def clientes_sem_vinculo(df_clientes):
    if df_clientes.empty or "Vínculo" not in df_clientes.columns:
        return pd.DataFrame()

    return df_clientes[
        df_clientes["Vínculo"].astype(str).eq("Sem vínculo")
    ].copy()


def clientes_sem_equipamento(df_clientes):
    if df_clientes.empty or "Qtd Equipamentos" not in df_clientes.columns:
        return pd.DataFrame()

    df = df_clientes.copy()
    df["Qtd Equipamentos"] = valor_float(df["Qtd Equipamentos"])

    return df[df["Qtd Equipamentos"] == 0]


def agrupar_sites(df_sites, coluna):
    if df_sites.empty or coluna not in df_sites.columns:
        return pd.DataFrame()

    return (
        df_sites.groupby(coluna, dropna=False)
        .agg(
            Sites=("Site SNMPc", "nunique"),
            Clientes=("Clientes Total", "sum"),
            Receita=("Receita Total", "sum"),
            Custo=("Custo", "sum"),
            Resultado=("Resultado", "sum")
        )
        .reset_index()
        .rename(columns={coluna: "Grupo"})
        .sort_values(by="Resultado", ascending=True)
    )


def agrupar_clientes(df_clientes, coluna):
    if df_clientes.empty or coluna not in df_clientes.columns:
        return pd.DataFrame()

    return (
        df_clientes.groupby(coluna, dropna=False)
        .agg(
            Clientes=("Assinatura", "nunique"),
            Receita=("Receita", "sum"),
            Sites=("Site", "nunique")
        )
        .reset_index()
        .rename(columns={coluna: "Grupo"})
        .sort_values(by="Receita", ascending=False)
    )


def ranking_sites(df_sites, coluna, ascendente=False, limite=20):
    if df_sites.empty or coluna not in df_sites.columns:
        return pd.DataFrame()

    return df_sites.sort_values(
        by=coluna,
        ascending=ascendente
    ).head(limite)


def ranking_clientes(df_clientes, coluna="Receita", ascendente=False, limite=20):
    if df_clientes.empty or coluna not in df_clientes.columns:
        return pd.DataFrame()

    return df_clientes.sort_values(
        by=coluna,
        ascending=ascendente
    ).head(limite)


def equipamentos_dataframe(equipamentos):
    if not equipamentos:
        return pd.DataFrame()

    return pd.DataFrame(equipamentos)


def equipamentos_sem_catalogo(equipamentos):
    df_equipamentos = equipamentos_dataframe(equipamentos)

    if df_equipamentos.empty or "Icone" not in df_equipamentos.columns:
        return pd.DataFrame()

    catalogo = load_equipment_catalog()

    if catalogo.empty or "Ícone" not in catalogo.columns:
        return df_equipamentos

    icones_catalogo = set(catalogo["Ícone"].astype(str).str.strip())

    return df_equipamentos[
        ~df_equipamentos["Icone"].astype(str).str.strip().isin(icones_catalogo)
    ].copy()


def produtos_sem_catalogo(df_clientes):
    if df_clientes.empty or "Produto" not in df_clientes.columns:
        return pd.DataFrame()

    catalogo = load_product_catalog()

    if catalogo.empty or "Nome" not in catalogo.columns:
        return df_clientes[
            df_clientes["Produto"].astype(str).str.strip().ne("")
        ].copy()

    produtos_catalogo = set(catalogo["Nome"].astype(str).str.strip())

    return df_clientes[
        df_clientes["Produto"].astype(str).str.strip().ne("")
        & ~df_clientes["Produto"].astype(str).str.strip().isin(produtos_catalogo)
    ].copy()


def contatos_por_codigo():
    contatos = load_site_contacts()

    if contatos.empty:
        return set()

    return set(
        contatos["CÓDIGO AQUILES"].astype(str).str.strip()
    )


def sites_sem_contato(df_sites):
    if df_sites.empty or "Codigo" not in df_sites.columns:
        return pd.DataFrame()

    codigos_com_contato = contatos_por_codigo()

    return df_sites[
        ~df_sites["Codigo"].astype(str).str.strip().isin(codigos_com_contato)
    ].copy()


def sites_relacionamento_critico(df_sites):
    if df_sites.empty or "Relacionamento" not in df_sites.columns:
        return pd.DataFrame()

    termos = (
        "critico",
        "crítico",
        "risco",
        "restrito",
        "restrição",
        "bloqueio",
        "desligamento"
    )
    filtro = df_sites["Relacionamento"].astype(str).str.casefold().apply(
        lambda valor: any(termo in valor for termo in termos)
    )

    return df_sites[filtro].sort_values(
        by="Receita Total",
        ascending=False
    )


def sites_cadastro_incompleto(df_sites):
    if df_sites.empty:
        return pd.DataFrame()

    colunas = [
        coluna
        for coluna in [
            "Codigo",
            "Microsiga",
            "Nome Cadastro",
            "Contrato",
            "Categoria",
            "Perfil",
            "Endereco",
            "Cidade",
            "UF"
        ]
        if coluna in df_sites.columns
    ]

    if not colunas:
        return pd.DataFrame()

    df = df_sites.copy()
    df["Campos Pendentes"] = df[colunas].apply(
        lambda linha: ", ".join(
            coluna
            for coluna in colunas
            if not str(linha.get(coluna) or "").strip()
        ),
        axis=1
    )

    return df[df["Campos Pendentes"].astype(str).str.strip().ne("")]


def alertas_gerenciais(df_sites, df_clientes, equipamentos):
    alertas = []

    def adicionar(indicador, quantidade, impacto, prioridade):
        alertas.append({
            "Indicador": indicador,
            "Quantidade": int(quantidade),
            "Impacto": impacto,
            "Prioridade": prioridade
        })

    adicionar("Sites deficitários", len(sites_deficitarios(df_sites)), "Financeiro", "Alta")
    adicionar("Sites sem clientes", len(sites_sem_clientes(df_sites)), "Financeiro", "Alta")
    adicionar("Clientes sem vínculo", len(clientes_sem_vinculo(df_clientes)), "Comercial/Operacional", "Média")
    adicionar("Clientes sem equipamento", len(clientes_sem_equipamento(df_clientes)), "Operacional", "Média")
    adicionar("Equipamentos sem cadastro", len(equipamentos_sem_catalogo(equipamentos)), "Operacional", "Média")
    adicionar("Produtos sem cadastro", len(produtos_sem_catalogo(df_clientes)), "Comercial", "Média")
    adicionar("Sites sem contato", len(sites_sem_contato(df_sites)), "Governança", "Média")
    adicionar("Sites com relacionamento crítico", len(sites_relacionamento_critico(df_sites)), "Risco", "Alta")

    return pd.DataFrame(alertas).sort_values(
        by=[
            "Prioridade",
            "Quantidade"
        ],
        ascending=[
            True,
            False
        ]
    )
