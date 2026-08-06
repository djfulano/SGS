import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd

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

COLUNAS_RANKING_CLIENTES = [
    "Posição",
    "Cliente agrupado",
    "Receita Total",
    "Quantidade de assinaturas",
    "Assinaturas",
    "Quantidade de sites",
    "Sites",
    "Gerentes de Contas",
    "Produtos",
    "Nomes considerados",
]

TERMOS_IGNORADOS_NOME_CLIENTE = {
    "a",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "eireli",
    "epp",
    "ltda",
    "me",
    "para",
    "s",
    "sa",
}

TERMOS_GENERICOS_NOME_CLIENTE = {
    "comercio",
    "empresa",
    "industria",
    "servico",
    "servicos",
    "sociedade",
}


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


COLUNAS_RESUMO_ASSINATURAS_CLIENTES = [
    "Assinatura",
    "Nome",
    "Produto",
    "Receita",
    "Site",
    "Gerente de Contas",
]


def normalizar_selecao_assinaturas(assinaturas, assinaturas_validas):
    validas = {
        str(assinatura or "").strip()
        for assinatura in (assinaturas_validas or [])
        if str(assinatura or "").strip()
    }
    resultado = []
    vistos = set()

    for assinatura in assinaturas or []:
        assinatura = str(assinatura or "").strip()
        if not assinatura or assinatura not in validas or assinatura in vistos:
            continue
        resultado.append(assinatura)
        vistos.add(assinatura)

    return resultado


def sites_atendimento_registro_cliente(registro):
    sites = []

    vinculos = registro.get("Vínculos de atendimento")
    if not isinstance(vinculos, (list, tuple)):
        vinculos = []

    for vinculo in vinculos:
        if not isinstance(vinculo, dict):
            continue
        site = str(vinculo.get("Site") or "").strip()
        if site and site not in sites:
            sites.append(site)

    sites_texto = registro.get("Sites de atendimento")
    if pd.isna(sites_texto):
        sites_texto = ""
    for site in str(sites_texto or "").split(","):
        site = site.strip()
        if site and site not in sites:
            sites.append(site)

    site_principal = registro.get("Site")
    if pd.isna(site_principal):
        site_principal = ""
    site_principal = str(site_principal or "").strip()
    if (
        site_principal
        and site_principal.casefold() != "sem vínculo".casefold()
        and site_principal not in sites
    ):
        sites.insert(0, site_principal)

    return sites


def normalizar_nome_ranking_cliente(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold()
    termos = [
        termo
        for termo in re.findall(r"[a-z0-9]+", texto)
        if termo not in TERMOS_IGNORADOS_NOME_CLIENTE
    ]
    return " ".join(sorted(termos))


def _termos_distintivos_nome_cliente(nome_normalizado):
    return (
        set(str(nome_normalizado or "").split())
        - TERMOS_GENERICOS_NOME_CLIENTE
    )


def similaridade_nomes_clientes(nome_a, nome_b):
    normalizado_a = normalizar_nome_ranking_cliente(nome_a)
    normalizado_b = normalizar_nome_ranking_cliente(nome_b)

    if not normalizado_a or not normalizado_b:
        return 0.0
    if normalizado_a == normalizado_b:
        return 1.0

    termos_distintivos = (
        _termos_distintivos_nome_cliente(normalizado_a)
        & _termos_distintivos_nome_cliente(normalizado_b)
    )
    if not termos_distintivos:
        return 0.0

    return SequenceMatcher(
        None,
        normalizado_a,
        normalizado_b,
        autojunk=False,
    ).ratio()


def _lista_textual_ranking(valores):
    unicos = {
        str(valor or "").strip()
        for valor in valores
        if str(valor or "").strip()
    }
    return ", ".join(sorted(unicos, key=str.casefold))


def _ordenar_assinaturas_ranking(valores):
    assinaturas = {
        str(valor or "").strip()
        for valor in valores
        if str(valor or "").strip()
    }
    return sorted(
        assinaturas,
        key=lambda valor: (
            0 if valor.isdigit() else 1,
            int(valor) if valor.isdigit() else valor.casefold(),
        ),
    )


def montar_ranking_clientes_aproximado(df_clientes, limiar=0.90):
    if df_clientes is None or df_clientes.empty:
        return pd.DataFrame(columns=COLUNAS_RANKING_CLIENTES)

    base = df_clientes.copy()
    for coluna in [
        "Cliente",
        "Assinatura",
        "Receita",
        "Produto",
        "Gerente de contas",
        "Site",
        "Sites de atendimento",
        "Vínculos de atendimento",
    ]:
        if coluna not in base.columns:
            base[coluna] = ""

    base["Assinatura"] = base["Assinatura"].astype(str).str.strip()
    base = base[base["Assinatura"].ne("")].drop_duplicates(
        subset=["Assinatura"],
        keep="first",
    )
    if base.empty:
        return pd.DataFrame(columns=COLUNAS_RANKING_CLIENTES)

    base["Cliente"] = base["Cliente"].fillna("").astype(str).str.strip()
    base["Receita"] = pd.to_numeric(
        base["Receita"],
        errors="coerce",
    ).fillna(0.0)

    variantes = []
    for nome, registros_nome in base.groupby("Cliente", dropna=False):
        variantes.append({
            "nome": str(nome or "").strip() or "Não informado",
            "indices": registros_nome.index.tolist(),
            "receita": float(registros_nome["Receita"].sum()),
            "assinaturas": int(registros_nome["Assinatura"].nunique()),
        })
    variantes.sort(
        key=lambda item: (
            -item["receita"],
            -item["assinaturas"],
            item["nome"].casefold(),
        )
    )

    grupos = []
    grupos_por_normalizado = {}
    grupos_por_termo = {}
    for variante in variantes:
        nome_normalizado = normalizar_nome_ranking_cliente(variante["nome"])
        indice_exato = grupos_por_normalizado.get(nome_normalizado)
        indices_candidatos = set()
        for termo in _termos_distintivos_nome_cliente(nome_normalizado):
            indices_candidatos.update(grupos_por_termo.get(termo, set()))

        if indice_exato is not None:
            indices_candidatos.add(indice_exato)
        candidatos = [
            (
                similaridade_nomes_clientes(
                    variante["nome"],
                    grupo["representante"]["nome"],
                ),
                indice,
            )
            for indice in indices_candidatos
            for grupo in [grupos[indice]]
        ]
        melhor_score, melhor_indice = max(
            candidatos,
            default=(0.0, -1),
            key=lambda item: (item[0], -item[1]),
        )
        if melhor_score >= float(limiar):
            grupos[melhor_indice]["variantes"].append(variante)
        else:
            novo_indice = len(grupos)
            grupos.append({
                "representante": variante,
                "variantes": [variante],
            })
            grupos_por_normalizado.setdefault(nome_normalizado, novo_indice)
            for termo in _termos_distintivos_nome_cliente(nome_normalizado):
                grupos_por_termo.setdefault(termo, set()).add(novo_indice)

    linhas = []
    for grupo in grupos:
        indices = [
            indice
            for variante in grupo["variantes"]
            for indice in variante["indices"]
        ]
        registros = base.loc[indices].copy()
        assinaturas = _ordenar_assinaturas_ranking(registros["Assinatura"])
        sites = set()
        for registro in registros.to_dict(orient="records"):
            sites.update(sites_atendimento_registro_cliente(registro))

        linhas.append({
            "Cliente agrupado": grupo["representante"]["nome"],
            "Receita Total": float(registros["Receita"].sum()),
            "Quantidade de assinaturas": len(assinaturas),
            "Assinaturas": ", ".join(assinaturas),
            "Quantidade de sites": len(sites),
            "Sites": ", ".join(sorted(sites, key=str.casefold)),
            "Gerentes de Contas": _lista_textual_ranking(
                registros["Gerente de contas"]
            ),
            "Produtos": _lista_textual_ranking(registros["Produto"]),
            "Nomes considerados": _lista_textual_ranking(
                variante["nome"]
                for variante in grupo["variantes"]
            ),
        })

    resultado = pd.DataFrame(linhas).sort_values(
        ["Receita Total", "Cliente agrupado"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    resultado.insert(0, "Posição", range(1, len(resultado) + 1))
    return resultado[COLUNAS_RANKING_CLIENTES]


def filtrar_ranking_clientes(df_ranking, termo):
    termo = normalizar_busca_custos_cliente(termo)
    if not termo or df_ranking is None or df_ranking.empty:
        return df_ranking

    colunas = [
        "Cliente agrupado",
        "Assinaturas",
        "Sites",
        "Gerentes de Contas",
        "Nomes considerados",
    ]
    mascara = pd.Series(False, index=df_ranking.index)
    for coluna in colunas:
        mascara |= df_ranking[coluna].fillna("").astype(str).map(
            normalizar_busca_custos_cliente
        ).str.contains(termo, regex=False)
    return df_ranking[mascara].copy()


def montar_resumo_assinaturas_clientes(df_clientes, assinaturas):
    resultado_vazio = {
        "clientes": 0,
        "receita": 0.0,
        "sites": 0,
        "tabela": pd.DataFrame(columns=COLUNAS_RESUMO_ASSINATURAS_CLIENTES),
    }

    if df_clientes is None or df_clientes.empty:
        return resultado_vazio

    base = df_clientes.copy()
    base["Assinatura"] = base["Assinatura"].astype(str).str.strip()
    base = base.drop_duplicates(subset=["Assinatura"], keep="first")
    selecionadas = normalizar_selecao_assinaturas(
        assinaturas,
        base["Assinatura"].tolist(),
    )
    if not selecionadas:
        return resultado_vazio

    registros = {
        str(linha["Assinatura"]): linha.to_dict()
        for _indice, linha in base.iterrows()
    }
    linhas = []
    sites_unicos = set()
    receita_total = 0.0

    for assinatura in selecionadas:
        registro = registros[assinatura]
        sites = sites_atendimento_registro_cliente(registro)
        sites_unicos.update(sites)
        receita = pd.to_numeric(
            pd.Series([registro.get("Receita")]),
            errors="coerce",
        ).fillna(0).iloc[0]
        receita_total += float(receita)
        linhas.append({
            "Assinatura": assinatura,
            "Nome": str(registro.get("Cliente") or "").strip(),
            "Produto": str(registro.get("Produto") or "").strip(),
            "Receita": float(receita),
            "Site": ", ".join(sites) if sites else "Sem vínculo",
            "Gerente de Contas": str(
                registro.get("Gerente de contas") or ""
            ).strip(),
        })

    return {
        "clientes": len(linhas),
        "receita": receita_total,
        "sites": len(sites_unicos),
        "tabela": pd.DataFrame(
            linhas,
            columns=COLUNAS_RESUMO_ASSINATURAS_CLIENTES,
        ),
    }


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
