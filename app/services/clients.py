import pandas as pd
import unicodedata

from app.config import CLIENTES_FILE
from app.importers.excel_importer import ler_clientes_base
from app.services.client_viability import carregar_clientes_viabilidade
from app.services.equipment_catalog import load_equipment_catalog
from app.services.map_service import endereco_cliente
from app.services.product_catalog import enrich_products_with_catalog
from app.services.products import montar_indice_clientes_vinculados


COLUNAS_ASSINATURAS_CUSTOS_CLIENTE = [
    "Assinatura",
    "Cliente",
    "Produto",
    "Gerente de contas",
    "Site principal",
    "Sites de atendimento",
    "Quantidade de sites"
]

COLUNAS_SITES_CUSTOS_CLIENTE = [
    "Nome",
    "Nome SNMPc",
    "Tipo",
    "Status",
    "Assinaturas",
    "Quantidade de assinaturas",
    "Vínculos",
    "Custo"
]


def normalizar_busca_custos_cliente(valor):
    texto = unicodedata.normalize(
        "NFKD",
        str(valor or "")
    )

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold().strip()


def _numero_custo_site(valor):
    if valor is None or valor == "":
        return 0.0

    try:
        return float(valor)
    except (TypeError, ValueError):
        texto = str(valor).strip().replace("R$", "").replace(" ", "")

        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        try:
            return float(texto)
        except (TypeError, ValueError):
            return 0.0


def levantar_custos_sites_cliente(sites, termo):
    colunas_assinaturas = COLUNAS_ASSINATURAS_CUSTOS_CLIENTE
    colunas_sites = COLUNAS_SITES_CUSTOS_CLIENTE
    termo_normalizado = normalizar_busca_custos_cliente(termo)

    resultado_vazio = {
        "assinaturas": pd.DataFrame(columns=colunas_assinaturas),
        "sites": pd.DataFrame(columns=colunas_sites),
        "total_assinaturas": 0,
        "total_sites": 0,
        "custo_total": 0.0
    }

    if not termo_normalizado:
        return resultado_vazio

    sites_iteraveis = (
        sites.values()
        if isinstance(sites, dict)
        else (sites or [])
    )
    assinaturas_encontradas = {}
    sites_encontrados = {}

    for site_principal in sites_iteraveis:
        for cliente in getattr(site_principal, "clientes", []):
            assinatura = str(
                getattr(cliente, "num_assinatura", "") or ""
            ).strip()
            nome_cliente = str(
                getattr(cliente, "nome", "") or ""
            ).strip()

            if (
                termo_normalizado not in normalizar_busca_custos_cliente(
                    assinatura
                )
                and termo_normalizado not in normalizar_busca_custos_cliente(
                    nome_cliente
                )
            ):
                continue

            vinculos = list(
                getattr(cliente, "vinculos_atendimento", []) or []
            )

            if not vinculos:
                vinculos = [{
                    "site": site_principal,
                    "tipo": "Principal",
                    "setorial": getattr(cliente, "setorial", None)
                }]

            sites_da_assinatura = {}

            for vinculo in vinculos:
                site_vinculado = vinculo.get("site")

                if site_vinculado is None:
                    continue

                nome_snmpc = str(
                    getattr(site_vinculado, "nome", "") or ""
                ).strip()

                if not nome_snmpc:
                    continue

                tipo_vinculo = str(
                    vinculo.get("tipo") or "Principal"
                ).strip()
                sites_da_assinatura.setdefault(nome_snmpc, site_vinculado)
                agregado_site = sites_encontrados.setdefault(
                    nome_snmpc,
                    {
                        "site": site_vinculado,
                        "assinaturas": set(),
                        "vinculos": set()
                    }
                )
                agregado_site["assinaturas"].add(assinatura)
                agregado_site["vinculos"].add(tipo_vinculo)

            registro_assinatura = assinaturas_encontradas.setdefault(
                assinatura,
                {
                    "Assinatura": assinatura,
                    "Cliente": nome_cliente,
                    "Produto": str(
                        getattr(cliente, "produto", "") or ""
                    ).strip(),
                    "Gerente de contas": str(
                        getattr(cliente, "gerente_contas", "") or ""
                    ).strip(),
                    "Site principal": str(
                        getattr(site_principal, "nome", "") or ""
                    ).strip(),
                    "sites": {}
                }
            )
            registro_assinatura["sites"].update(sites_da_assinatura)

    if not assinaturas_encontradas:
        return resultado_vazio

    linhas_assinaturas = []

    for registro in assinaturas_encontradas.values():
        nomes_sites = sorted(registro.pop("sites"))
        linhas_assinaturas.append({
            **registro,
            "Sites de atendimento": ", ".join(nomes_sites),
            "Quantidade de sites": len(nomes_sites)
        })

    linhas_sites = []

    for nome_snmpc, agregado in sites_encontrados.items():
        site = agregado["site"]
        assinaturas = sorted(agregado["assinaturas"])
        linhas_sites.append({
            "Nome": str(
                getattr(site, "nome_cadastro", "") or ""
            ).strip(),
            "Nome SNMPc": nome_snmpc,
            "Tipo": str(getattr(site, "tipo", "") or "").strip(),
            "Status": str(
                getattr(site, "status_cadastro", "") or ""
            ).strip(),
            "Assinaturas": ", ".join(assinaturas),
            "Quantidade de assinaturas": len(assinaturas),
            "Vínculos": ", ".join(sorted(agregado["vinculos"])),
            "Custo": _numero_custo_site(getattr(site, "custo", 0))
        })

    df_assinaturas = pd.DataFrame(
        linhas_assinaturas,
        columns=colunas_assinaturas
    ).sort_values(
        by=["Cliente", "Assinatura"],
        kind="stable"
    ).reset_index(drop=True)
    df_sites = pd.DataFrame(
        linhas_sites,
        columns=colunas_sites
    ).sort_values(
        by=["Nome", "Nome SNMPc"],
        kind="stable"
    ).reset_index(drop=True)

    return {
        "assinaturas": df_assinaturas,
        "sites": df_sites,
        "total_assinaturas": int(df_assinaturas["Assinatura"].nunique()),
        "total_sites": int(df_sites["Nome SNMPc"].nunique()),
        "custo_total": float(df_sites["Custo"].sum())
    }


def valor_site(site, atributo, padrao=""):
    return getattr(site, atributo, padrao) or padrao


def rotulo_site(site):
    if site is None:
        return ""

    return (
        f"{site.nome} - {valor_site(site, 'codigo_topos')} / "
        f"{valor_site(site, 'nome_cadastro')} - {valor_site(site, 'microsiga')}"
    )


def resumo_vinculos_atendimento(cliente):
    vinculos = []

    for vinculo in getattr(cliente, "vinculos_atendimento", []):
        site = vinculo.get("site")

        if site is None:
            continue

        vinculos.append({
            "Site": getattr(site, "nome", ""),
            "Setorial": vinculo.get("setorial") or "Direto",
            "Vínculo": vinculo.get("tipo") or "Principal"
        })

    return {
        "Sites de atendimento": ", ".join(
            item["Site"]
            for item in vinculos
            if item["Site"]
        ),
        "Setoriais de atendimento": ", ".join(
            item["Setorial"]
            for item in vinculos
        ),
        "Vínculos de atendimento": vinculos
    }


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
                **resumo_vinculos_atendimento(cliente),
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
                "Endereço": endereco_cliente(cliente),
                "Latitude": viabilidade.get("latitude", getattr(cliente, "latitude", 0)),
                "Longitude": viabilidade.get("longitude", getattr(cliente, "longitude", 0)),
                "Altitude": viabilidade.get("altitude", getattr(cliente, "altitude", 0)),
                "Altura": viabilidade.get("altura", getattr(cliente, "altura", 0)),
                **resumo_vinculos_atendimento(cliente),
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
            "Sites de atendimento": "",
            "Setoriais de atendimento": "",
            "Vínculos de atendimento": [],
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
            "Endereço": cliente.get("Endereco") or "",
            "Latitude": viabilidade.get("latitude", 0),
            "Longitude": viabilidade.get("longitude", 0),
            "Altitude": viabilidade.get("altitude", 0),
            "Altura": viabilidade.get("altura", 0),
            "Sites de atendimento": "",
            "Setoriais de atendimento": "",
            "Vínculos de atendimento": [],
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
        "Endereço",
        "Sites de atendimento",
        "Setoriais de atendimento",
        "Vínculos de atendimento",
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
            "Site",
            "Sites de atendimento"
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
