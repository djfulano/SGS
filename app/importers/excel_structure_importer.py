import json
from pathlib import Path

import pandas as pd

from app.config import STRUCTURE_LINKS_CACHE_FILE

from app.importers.txt_importer import importar_estrutura_de_linhas


SHEETS_LINKS = [
    "LinkTable",
    "NetworkTable"
]


def texto(valor):

    if pd.isna(valor):

        return ""

    return str(valor).strip()


def ler_planilha(caminho_arquivo, sheet_name):

    return pd.read_excel(
        caminho_arquivo,
        sheet_name=sheet_name,
        dtype=object
    )


def linha_estrutura(
    row,
    id_col,
    tipo,
    name_col="label",
    address_col="address",
    description_col="description",
    parent_col="parent_id",
    icon_col=None,
    group_col=None
):

    return {
        "ID": texto(row.get(id_col)),
        "Name": texto(row.get(name_col)),
        "Type": tipo,
        "Parent": texto(row.get(parent_col)),
        "Address": texto(row.get(address_col)),
        "Icon": texto(row.get(icon_col)) if icon_col else "",
        "Group1": texto(row.get(group_col)) if group_col else "",
        "Group2": "",
        "Status": "",
        "Description": texto(row.get(description_col))
    }


def converter_subnets(caminho_arquivo):

    df = ler_planilha(
        caminho_arquivo,
        "Subnets"
    )

    return [
        linha_estrutura(
            row,
            id_col="subnet_id",
            tipo="Subnet"
        )
        for _idx, row in df.iterrows()
    ]


def converter_nodes(caminho_arquivo):

    df = ler_planilha(
        caminho_arquivo,
        "NodeTable"
    )

    linhas = []

    for _idx, row in df.iterrows():

        linha = linha_estrutura(
            row,
            id_col="node_id",
            tipo="Device",
            icon_col="node_group",
            group_col="node_group"
        )
        linha["Status"] = texto(row.get("has_snmp"))
        linha["MAC"] = texto(row.get("mac_address"))
        linhas.append(linha)

    return linhas


def converter_gotos(caminho_arquivo):

    df = ler_planilha(
        caminho_arquivo,
        "Gotos"
    )

    return [
        linha_estrutura(
            row,
            id_col="goto_id",
            tipo="Goto"
        )
        for _idx, row in df.iterrows()
    ]


def normalizar_links(caminho_arquivo):

    links = {}

    for sheet_name in SHEETS_LINKS:

        try:

            df = ler_planilha(
                caminho_arquivo,
                sheet_name
            )

        except ValueError:

            links[sheet_name] = []

            continue

        registros = []

        for _idx, row in df.iterrows():

            registros.append({
                "id": texto(row.get("link_id")) or texto(row.get("network_id")),
                "label": texto(row.get("label")),
                "address": texto(row.get("address")),
                "description": texto(row.get("description")),
                "parent_id": texto(row.get("parent_id")),
                "start_pos": texto(row.get("start_pos")),
                "end_pos": texto(row.get("end_pos"))
            })

        links[sheet_name] = registros

    return links


def salvar_links_cache(links):

    caminho = STRUCTURE_LINKS_CACHE_FILE
    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    caminho.write_text(
        json.dumps(
            links,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def importar_estrutura_excel(caminho_arquivo):

    caminho = Path(caminho_arquivo)

    if not caminho.exists():

        raise FileNotFoundError(
            f"Arquivo de estrutura Excel nao encontrado: {caminho}"
        )

    linhas = []
    linhas.extend(
        converter_subnets(caminho)
    )
    linhas.extend(
        converter_nodes(caminho)
    )
    linhas.extend(
        converter_gotos(caminho)
    )

    salvar_links_cache(
        normalizar_links(caminho)
    )

    return importar_estrutura_de_linhas(linhas)
