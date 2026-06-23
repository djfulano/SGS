import re

import pandas as pd
import streamlit as st

from app.config import CLIENTES_FILE
from app.importers.excel_importer import normalizar_assinatura
from app.importers.excel_importer import valor_texto
from app.services.map_service import endereco_cliente
from app.services.product_catalog import enrich_products_with_catalog


PRODUTOS_SVA = (
    "neofirewall",
    "neowifi",
    "neobalance",
    "neocaptive"
)


def eh_produto_sva(produto):
    return str(
        produto
    ).strip().lower().startswith(PRODUTOS_SVA)


def montar_clientes_produtos(sites):
    dados = []

    for site in sites.values():
        for cliente in site.clientes:
            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": cliente.num_assinatura,
                "Produto": getattr(cliente, "produto", ""),
                "Receita": cliente.receita,
                "Site": site.nome,
                "Setorial": getattr(cliente, "setorial", None) or "Direto",
                "Predio": getattr(cliente, "predio_estrutura", None) or "",
                "Endereco": endereco_cliente(cliente)
            })

    return enrich_products_with_catalog(
        pd.DataFrame(dados)
    )


def montar_produtos_equipamentos(sites, equipamentos):
    df_clientes = montar_clientes_produtos(sites)

    if df_clientes.empty:
        return pd.DataFrame()

    df_equipamentos = pd.DataFrame(equipamentos)

    if df_equipamentos.empty:
        return pd.DataFrame()

    colunas_equipamentos = [
        "Assinatura",
        "Equipamento",
        "Endereco",
        "Icone",
        "Status",
        "Predio",
        "Site",
        "Setorial",
        "Parent",
        "Cliente Estrutura"
    ]

    df_equipamentos = df_equipamentos[colunas_equipamentos]
    df_equipamentos = df_equipamentos[
        df_equipamentos["Assinatura"].astype(str).str.strip() != ""
    ]

    return enrich_products_with_catalog(
        df_clientes.merge(
            df_equipamentos,
            on="Assinatura",
            how="inner",
            suffixes=(
                " Cliente",
                " Equipamento"
            )
        )
    )


def montar_clientes_produtos_base(sites):
    df_clientes = carregar_clientes_excel_sva(
        CLIENTES_FILE,
        str(CLIENTES_FILE.stat().st_mtime)
    )

    if df_clientes.empty:
        return montar_clientes_produtos(sites)

    vinculados = montar_indice_clientes_vinculados(sites)

    df_vinculos = pd.DataFrame(
        [
            {
                "Assinatura": assinatura,
                "Site": vinculo.get("Site Vinculado", ""),
                "Setorial": vinculo.get("Setorial Vinculado", "")
            }
            for assinatura, vinculo in vinculados.items()
        ]
    )

    if df_vinculos.empty:
        df_clientes["Site"] = ""
        df_clientes["Setorial"] = ""
        return df_clientes

    return df_clientes.merge(
        df_vinculos,
        on="Assinatura",
        how="left"
    ).fillna({
        "Site": "",
        "Setorial": ""
    })


def merge_produtos_equipamentos(df_clientes, df_equipamentos):
    return df_clientes.merge(
        df_equipamentos,
        on="Assinatura",
        how="inner",
        suffixes=(
            " Cliente",
            " Equipamento"
        )
    )


@st.cache_data(show_spinner=False)
def carregar_clientes_excel_sva(caminho_arquivo=CLIENTES_FILE, versao_cache=None):
    df = pd.read_excel(
        caminho_arquivo,
        header=7
    )

    dados = []

    for _indice, linha in df.iterrows():
        assinatura = normalizar_assinatura(
            linha.get("NUM ASSINATURA")
        )
        nome = valor_texto(
            linha,
            "NOME CLIENTE"
        )

        if not assinatura or not nome:
            continue

        dados.append({
            "Cliente": nome,
            "Assinatura": assinatura,
            "Produto": valor_texto(
                linha,
                "PRODUTO"
            ),
            "Receita": linha.get("MENSALIDADE", 0),
            "Endereco": valor_texto(
                linha,
                "ENDERECO COMPLETO"
            ),
            "Bairro": valor_texto(
                linha,
                "BAIRRO"
            ),
            "Cidade": valor_texto(
                linha,
                "CIDADE"
            )
        })

    return enrich_products_with_catalog(
        pd.DataFrame(dados)
    )


def montar_indice_clientes_vinculados(sites):
    indice = {}

    for site in sites.values():
        for cliente in site.clientes:
            indice[cliente.num_assinatura] = {
                "Site Vinculado": site.nome,
                "Setorial Vinculado": getattr(cliente, "setorial", None) or "Direto"
            }

    return indice


def montar_sva_clientes(sites, equipamentos):
    df_clientes = carregar_clientes_excel_sva(
        CLIENTES_FILE,
        str(CLIENTES_FILE.stat().st_mtime)
    )

    if df_clientes.empty:
        return pd.DataFrame()

    df_clientes = df_clientes[
        df_clientes["Produto"].apply(eh_produto_sva)
    ]

    if df_clientes.empty:
        return pd.DataFrame()

    prefixos_sva = [
        "CL-APP-",
        "CL_AFW-",
        "CL-ART-",
        "FW-DAVO-"
    ]
    equipamentos_por_assinatura = {}

    for equipamento in equipamentos:
        nome_equipamento = str(
            equipamento.get("Equipamento") or ""
        ).strip()
        nome_equipamento_upper = nome_equipamento.upper()

        prefixo_encontrado = next(
            (
                prefixo
                for prefixo in prefixos_sva
                if nome_equipamento_upper.startswith(prefixo)
            ),
            None
        )

        if not prefixo_encontrado:
            continue

        assinatura_match = re.search(
            r"\d+",
            nome_equipamento[len(prefixo_encontrado):]
        )

        if not assinatura_match:
            continue

        assinatura_equipamento = assinatura_match.group(0)

        for assinatura in df_clientes["Assinatura"].unique():
            if assinatura and assinatura == assinatura_equipamento:
                equipamentos_por_assinatura.setdefault(
                    assinatura,
                    []
                ).append(equipamento)

    vinculados = montar_indice_clientes_vinculados(sites)
    dados = []

    for _indice, cliente in df_clientes.iterrows():
        assinatura = cliente["Assinatura"]
        equipamentos_cliente = equipamentos_por_assinatura.get(
            assinatura,
            []
        )
        vinculo = vinculados.get(
            assinatura,
            {}
        )

        if not equipamentos_cliente:
            dados.append({
                "Cliente": cliente["Cliente"],
                "Assinatura": assinatura,
                "Produto": cliente["Produto"],
                "Receita": cliente["Receita"],
                "Status Vinculo": "Nao aparece no SNMPc",
                "Site Vinculado": vinculo.get("Site Vinculado", ""),
                "Setorial Vinculado": vinculo.get("Setorial Vinculado", ""),
                "Site Equipamento": "",
                "Setorial Equipamento": "",
                "Parent": "",
                "Equipamento": "",
                "Icone": "",
                "Endereco Equipamento": "",
                "Status Equipamento": "",
                "Endereco Cliente": cliente["Endereco"],
                "Bairro": cliente["Bairro"],
                "Cidade": cliente["Cidade"]
            })
            continue

        for equipamento in equipamentos_cliente:
            dados.append({
                "Cliente": cliente["Cliente"],
                "Assinatura": assinatura,
                "Produto": cliente["Produto"],
                "Receita": cliente["Receita"],
                "Status Vinculo": (
                    "Vinculado a site"
                    if vinculo
                    else "Sem site direto"
                ),
                "Site Vinculado": vinculo.get("Site Vinculado", ""),
                "Setorial Vinculado": vinculo.get("Setorial Vinculado", ""),
                "Site Equipamento": equipamento.get("Site") or "",
                "Setorial Equipamento": equipamento.get("Setorial") or "",
                "Parent": equipamento.get("Parent") or "",
                "Equipamento": equipamento.get("Equipamento") or "",
                "Icone": equipamento.get("Icone") or "",
                "Endereco Equipamento": equipamento.get("Endereco") or "",
                "Status Equipamento": equipamento.get("Status") or "",
                "Endereco Cliente": cliente["Endereco"],
                "Bairro": cliente["Bairro"],
                "Cidade": cliente["Cidade"]
            })

    return enrich_products_with_catalog(
        pd.DataFrame(dados)
    )
