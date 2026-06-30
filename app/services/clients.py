import pandas as pd

from app.config import CLIENTES_FILE
from app.importers.excel_importer import ler_clientes_base
from app.services.client_viability import carregar_clientes_viabilidade
from app.services.equipment_catalog import load_equipment_catalog
from app.services.map_service import endereco_cliente
from app.services.product_catalog import enrich_products_with_catalog
from app.services.products import montar_indice_clientes_vinculados


def valor_site(site, atributo, padrao=""):
    return getattr(site, atributo, padrao) or padrao


def rotulo_site(site):
    if site is None:
        return ""

    return (
        f"{site.nome} - {valor_site(site, 'codigo_topos')} / "
        f"{valor_site(site, 'nome_cadastro')} - {valor_site(site, 'microsiga')}"
    )


def montar_indice_equipamentos(equipamentos):
    indice = {}

    for equipamento in equipamentos or []:
        assinatura = str(equipamento.get("Assinatura") or "").strip()

        if assinatura:
            indice.setdefault(assinatura, []).append(equipamento)

    return indice


def montar_catalogo_por_icone():
    catalogo = load_equipment_catalog()

    if catalogo.empty or "Ícone" not in catalogo.columns:
        return {}

    return {
        str(linha.get("Ícone") or "").strip(): linha.to_dict()
        for _indice, linha in catalogo.iterrows()
        if str(linha.get("Ícone") or "").strip()
    }


def equipamento_enriquecido(equipamento, catalogo):
    icone = str(equipamento.get("Icone") or "").strip()
    cadastro = catalogo.get(icone, {})
    modelo_cadastro = str(
        cadastro.get("Modelo") or cadastro.get("Nome") or ""
    ).strip()
    nome_snmpc = str(equipamento.get("Equipamento") or "").strip()

    return {
        "Ícone": icone,
        "Equipamento": nome_snmpc,
        "Nome Equipamento": modelo_cadastro or icone or nome_snmpc,
        "Modelo Equipamento": modelo_cadastro,
        "Fabricante Equipamento": cadastro.get("Fabricante") or "",
        "Software Equipamento": cadastro.get("Software") or "",
        "Tipo Equipamento": cadastro.get("Tipo") or "",
        "Código Equipamento": cadastro.get("Código") or "",
        "Valor Equipamento": cadastro.get("Valor") or 0,
        "Status Equipamento": equipamento.get("Status") or "",
        "Site Equipamento": equipamento.get("Site") or "",
        "Setorial Equipamento": equipamento.get("Setorial") or "",
        "Endereço Equipamento": equipamento.get("Endereco") or "",
        "IP Equipamento": equipamento.get("Endereco") or ""
    }


def texto_resumo_equipamento(item):
    nome = str(item.get("Nome Equipamento") or "").strip() or "Não informado"
    ip = str(item.get("IP Equipamento") or "").strip() or "Não informado"

    return f"Equipamento: {nome} | IP: {ip}"


def resumo_equipamentos(assinatura, indice_equipamentos, catalogo):
    equipamentos = indice_equipamentos.get(assinatura, [])

    if not equipamentos:
        return {
            "Qtd Equipamentos": 0,
            "Equipamentos": "",
            "Ícones Equipamentos": "",
            "Tipos Equipamentos": "",
            "Valor Equipamentos": 0
        }

    enriquecidos = [
        equipamento_enriquecido(equipamento, catalogo)
        for equipamento in equipamentos
    ]

    return {
        "Qtd Equipamentos": len(enriquecidos),
        "Equipamentos": "\n".join(
            texto_resumo_equipamento(item)
            for item in enriquecidos
        ),
        "Ícones Equipamentos": ", ".join(sorted({
            str(item["Ícone"])
            for item in enriquecidos
            if str(item["Ícone"]).strip()
        })),
        "Tipos Equipamentos": ", ".join(sorted({
            str(item["Tipo Equipamento"])
            for item in enriquecidos
            if str(item["Tipo Equipamento"]).strip()
        })),
        "Valor Equipamentos": sum(
            float(item.get("Valor Equipamento") or 0)
            for item in enriquecidos
        )
    }


def goto_snmpc_cliente(site, assinatura):
    assinatura = str(assinatura or "").strip()

    if not assinatura:
        return ""

    for cliente_estrutura in getattr(site, "clientes_estrutura", []):
        assinatura_estrutura = str(
            cliente_estrutura.get("assinatura") or ""
        ).strip()

        if assinatura_estrutura == assinatura:
            return str(cliente_estrutura.get("nome") or "").strip()

    return ""


def montar_clientes_vinculados(sites, indice_equipamentos, catalogo):
    dados = []

    for site in sites.values():
        for cliente in site.clientes:
            assinatura = str(cliente.num_assinatura).strip()
            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": assinatura,
                "Produto": getattr(cliente, "produto", ""),
                "Gerente de contas": getattr(cliente, "gerente_contas", ""),
                "Receita": cliente.receita,
                "Vínculo": "Vinculado",
                "Site": site.nome,
                "Site Completo": rotulo_site(site),
                "Setorial": getattr(cliente, "setorial", None) or "Direto",
                "Código Aquiles": valor_site(site, "codigo_topos"),
                "Código Microsiga": valor_site(site, "microsiga"),
                "Nome Site": valor_site(site, "nome_cadastro"),
                "Status Site": valor_site(site, "status_cadastro"),
                "Tipo Site": valor_site(site, "tipo"),
                "Cidade Site": valor_site(site, "cidade"),
                "CEP": getattr(cliente, "cep", ""),
                "Endereço": endereco_cliente(cliente),
                "Bairro": getattr(cliente, "bairro", ""),
                "Cidade": getattr(cliente, "cidade", ""),
                **resumo_equipamentos(assinatura, indice_equipamentos, catalogo)
            })

    return dados


def montar_clientes_vinculados_consulta(sites, indice_equipamentos, catalogo):
    dados = []
    dados_viabilidade = carregar_clientes_viabilidade()

    for site in sites.values():
        for cliente in site.clientes:
            assinatura = str(cliente.num_assinatura).strip()
            viabilidade = dados_viabilidade.get(assinatura, {})
            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": assinatura,
                "Produto": getattr(cliente, "produto", ""),
                "Gerente de contas": getattr(cliente, "gerente_contas", ""),
                "Receita": cliente.receita,
                "Vínculo": "Vinculado",
                "Site": site.nome,
                "Setorial": getattr(cliente, "setorial", None) or "Direto",
                "GoTo SNMPc": goto_snmpc_cliente(site, assinatura),
                "Latitude": viabilidade.get("latitude", getattr(cliente, "latitude", 0)),
                "Longitude": viabilidade.get("longitude", getattr(cliente, "longitude", 0)),
                "Altitude": viabilidade.get("altitude", getattr(cliente, "altitude", 0)),
                "Altura": viabilidade.get("altura", getattr(cliente, "altura", 0)),
                **resumo_equipamentos(assinatura, indice_equipamentos, catalogo)
            })

    return dados


def montar_clientes_sem_vinculo(sites, indice_equipamentos, catalogo, clientes_base):
    dados = []
    vinculados = montar_indice_clientes_vinculados(sites)

    for assinatura, cliente in clientes_base.items():
        assinatura = str(assinatura).strip()

        if not assinatura or assinatura in vinculados:
            continue

        dados.append({
            "Cliente": cliente.get("Cliente") or "",
            "Assinatura": assinatura,
            "Produto": cliente.get("Produto") or "",
            "Gerente de contas": cliente.get("Gerente Contas") or "",
            "Receita": cliente.get("Receita") or 0,
            "Vínculo": "Sem vínculo",
            "Site": "",
            "Site Completo": "",
            "Setorial": "",
            "Código Aquiles": "",
            "Código Microsiga": "",
            "Nome Site": "",
            "Status Site": "",
            "Tipo Site": "",
            "Cidade Site": "",
            "CEP": cliente.get("CEP") or "",
            "Endereço": cliente.get("Endereco") or "",
            "Bairro": cliente.get("Bairro") or "",
            "Cidade": cliente.get("Cidade") or "",
            **resumo_equipamentos(assinatura, indice_equipamentos, catalogo)
        })

    return dados


def montar_clientes_sem_vinculo_consulta(
    sites,
    indice_equipamentos,
    catalogo,
    clientes_base
):
    dados = []
    vinculados = montar_indice_clientes_vinculados(sites)
    dados_viabilidade = carregar_clientes_viabilidade()

    for assinatura, cliente in clientes_base.items():
        assinatura = str(assinatura).strip()

        if not assinatura or assinatura in vinculados:
            continue
        viabilidade = dados_viabilidade.get(assinatura, {})

        dados.append({
            "Cliente": cliente.get("Cliente") or "",
            "Assinatura": assinatura,
            "Produto": cliente.get("Produto") or "",
            "Gerente de contas": cliente.get("Gerente Contas") or "",
            "Receita": cliente.get("Receita") or 0,
            "Vínculo": "Sem vínculo",
            "Site": "",
            "Setorial": "",
            "GoTo SNMPc": "",
            "Latitude": viabilidade.get("latitude", 0),
            "Longitude": viabilidade.get("longitude", 0),
            "Altitude": viabilidade.get("altitude", 0),
            "Altura": viabilidade.get("altura", 0),
            **resumo_equipamentos(assinatura, indice_equipamentos, catalogo)
        })

    return dados


def montar_base_clientes(sites, equipamentos, clientes_base=None):
    indice_equipamentos = montar_indice_equipamentos(equipamentos)
    catalogo = montar_catalogo_por_icone()
    clientes_base = (
        clientes_base
        if clientes_base is not None
        else ler_clientes_base(CLIENTES_FILE)
    )

    dados = montar_clientes_vinculados(sites, indice_equipamentos, catalogo)
    dados.extend(
        montar_clientes_sem_vinculo(
            sites,
            indice_equipamentos,
            catalogo,
            clientes_base
        )
    )

    df = pd.DataFrame(dados)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "Cliente",
                "Assinatura",
                "Produto",
                "Gerente de contas",
                "Receita",
                "Vínculo",
                "Site",
                "Setorial"
            ]
        )

    return enrich_products_with_catalog(df).sort_values(
        by=[
            "Cliente",
            "Assinatura"
        ]
    ).reset_index(drop=True)


def montar_base_consulta_clientes(sites, equipamentos, clientes_base=None):
    indice_equipamentos = montar_indice_equipamentos(equipamentos)
    catalogo = montar_catalogo_por_icone()
    clientes_base = (
        clientes_base
        if clientes_base is not None
        else ler_clientes_base(CLIENTES_FILE)
    )

    dados = montar_clientes_vinculados_consulta(
        sites,
        indice_equipamentos,
        catalogo
    )
    dados.extend(
        montar_clientes_sem_vinculo_consulta(
            sites,
            indice_equipamentos,
            catalogo,
            clientes_base
        )
    )

    df = pd.DataFrame(dados)

    colunas = [
        "Cliente",
        "Assinatura",
        "Produto",
        "Gerente de contas",
        "Receita",
        "Vínculo",
        "Site",
        "Setorial",
        "GoTo SNMPc",
        "Latitude",
        "Longitude",
        "Altitude",
        "Altura",
        "Qtd Equipamentos",
        "Equipamentos"
    ]

    if df.empty:
        return pd.DataFrame(columns=colunas)

    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = ""

    return df[colunas].sort_values(
        by=[
            "Cliente",
            "Assinatura"
        ]
    ).reset_index(drop=True)


def equipamentos_cliente(assinatura, equipamentos):
    catalogo = montar_catalogo_por_icone()
    indice = montar_indice_equipamentos(equipamentos)

    return pd.DataFrame([
        equipamento_enriquecido(equipamento, catalogo)
        for equipamento in indice.get(str(assinatura or "").strip(), [])
    ])


def filtrar_clientes(df, termo):
    termo = str(termo or "").strip()

    if not termo or df.empty:
        return df

    colunas_busca = [
        coluna
        for coluna in [
            "Cliente",
            "Assinatura",
            "Produto",
            "Gerente de contas",
            "Site",
            "Site Completo",
            "Endereço",
            "Cidade",
            "Bairro"
        ]
        if coluna in df.columns
    ]
    filtro = pd.Series(False, index=df.index)

    for coluna in colunas_busca:
        filtro = filtro | df[coluna].astype(str).str.contains(
            termo,
            case=False,
            regex=False,
            na=False
        )

    return df[filtro]


def filtrar_clientes_consulta(df, termo):
    termo = str(termo or "").strip()

    if not termo or df.empty:
        return df

    colunas_busca = [
        coluna
        for coluna in [
            "Cliente",
            "Assinatura",
            "Produto",
            "Gerente de contas",
            "Site"
        ]
        if coluna in df.columns
    ]
    filtro = pd.Series(False, index=df.index)

    for coluna in colunas_busca:
        filtro = filtro | df[coluna].astype(str).str.contains(
            termo,
            case=False,
            regex=False,
            na=False
        )

    return df[filtro]


def resumo_clientes(df):
    if df.empty:
        return {
            "clientes": 0,
            "receita": 0,
            "produtos": 0,
            "sites": 0,
            "sem_vinculo": 0
        }

    return {
        "clientes": int(df["Assinatura"].nunique()),
        "receita": float(df["Receita"].fillna(0).astype(float).sum()),
        "produtos": int(df["Produto"].replace("", pd.NA).dropna().nunique()) if "Produto" in df.columns else 0,
        "sites": int(df["Site"].replace("", pd.NA).dropna().nunique()) if "Site" in df.columns else 0,
        "sem_vinculo": int((df["Vínculo"] == "Sem vínculo").sum()) if "Vínculo" in df.columns else 0
    }


def agrupar_clientes(df, coluna):
    if df.empty or coluna not in df.columns:
        return pd.DataFrame()

    agrupado = (
        df.groupby(coluna, dropna=False)
        .agg(
            Clientes=("Assinatura", "nunique"),
            Receita=("Receita", "sum"),
            Produtos=("Produto", "nunique")
        )
        .reset_index()
        .rename(columns={coluna: "Grupo"})
    )
    agrupado["Grupo"] = agrupado["Grupo"].replace("", "Não informado").fillna(
        "Não informado"
    )

    return agrupado.sort_values(by="Receita", ascending=False)
