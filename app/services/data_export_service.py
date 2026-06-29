from io import BytesIO
from pathlib import Path

import pandas as pd

from app.config import CLIENTES_FILE
from app.config import CONTRACTS_INDEX_FILE
from app.config import MAP_CACHE_FILE
from app.importers.structure_importer import caminho_estrutura_txt
from app.importers.topos_importer import caminho_sites_excel
from app.logs import carregar_logs_sistema
from app.logs import carregar_logs_usuario
from app.services.contract_service import load_contract_index
from app.services.equipment_catalog import load_equipment_catalog
from app.services.map_export import montar_kml_mapa
from app.services.map_export import montar_kmz_mapa
from app.services.map_service import carregar_cache_mapa
from app.services.map_service import dataframes_mapa
from app.services.product_catalog import load_product_catalog
from app.services.site_registry_service import load_site_contacts


DETALHES_PADRAO_MAPA = [
    "Endereço",
    "Coordenadas",
    "Setorial",
    "Distância",
    "Produto",
    "Equipamento",
    "Receita",
    "Motivo"
]


def arquivo_para_download(path):
    path = Path(path)

    if not path.exists() or not path.is_file():
        return None

    return {
        "data": path.read_bytes(),
        "file_name": path.name,
        "size": path.stat().st_size
    }


def dataframe_para_excel(df, sheet_name="Dados"):
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name[:31] or "Dados"
        )

    buffer.seek(0)
    return buffer.getvalue()


def exportar_equipamentos_excel():
    return dataframe_para_excel(
        load_equipment_catalog(),
        "Equipamentos"
    )


def exportar_produtos_excel():
    return dataframe_para_excel(
        load_product_catalog(),
        "Produtos"
    )


def exportar_contatos_sites_excel():
    return dataframe_para_excel(
        load_site_contacts(),
        "Contatos"
    )


def exportar_indice_documentos_excel():
    index = load_contract_index()
    registros = []

    for codigo_site, documentos in index.get("sites", {}).items():
        for documento in documentos or []:
            registros.append({
                "Código Aquiles": codigo_site,
                "Arquivo": documento.get("original_filename") or "",
                "Caminho": documento.get("path") or "",
                "Tamanho": documento.get("size") or 0,
                "Observação": documento.get("notes") or "",
                "Enviado por": documento.get("uploaded_by") or "",
                "Enviado em": documento.get("uploaded_at") or "",
                "Arquivado": bool(documento.get("archived")),
                "Arquivado por": documento.get("archived_by") or "",
                "Arquivado em": documento.get("archived_at") or ""
            })

    return dataframe_para_excel(
        pd.DataFrame(registros),
        "Documentos"
    )


def exportar_logs_excel():
    registros = []

    for origem, logs in [
        ("Sistema", carregar_logs_sistema(limite=100000)),
        ("Usuários", carregar_logs_usuario(limite=100000))
    ]:
        for log in logs:
            registros.append({
                "Origem": origem,
                "Data/Hora": log.get("data_hora") or "",
                "Evento": log.get("evento") or "",
                "Usuário": log.get("usuario") or "",
                "Status": log.get("status") or "",
                "Detalhes": log.get("detalhes") or {}
            })

    df = pd.DataFrame(registros)

    if not df.empty and "Detalhes" in df.columns:
        df["Detalhes"] = df["Detalhes"].astype(str)

    return dataframe_para_excel(
        df,
        "Logs"
    )


def pacote_mapa_mais_recente():
    cache = carregar_cache_mapa()

    if not isinstance(cache, dict) or not cache:
        return None

    pacotes = [
        pacote
        for pacote in cache.values()
        if isinstance(pacote, dict)
    ]

    if not pacotes:
        return None

    return sorted(
        pacotes,
        key=lambda pacote: str(pacote.get("gerado_em") or pacote.get("compiled_at") or ""),
        reverse=True
    )[0]


def exportar_mapa(formato="KMZ"):
    pacote = pacote_mapa_mais_recente()

    if not pacote:
        return None

    df_sites, df_clientes, df_links_clientes, df_links_sites, df_nao_plotados = dataframes_mapa(
        pacote
    )

    if formato == "KML":
        return montar_kml_mapa(
            df_sites,
            df_clientes,
            df_links_clientes,
            df_links_sites,
            df_nao_plotados,
            campos_detalhe=DETALHES_PADRAO_MAPA
        )

    return montar_kmz_mapa(
        df_sites,
        df_clientes,
        df_links_clientes,
        df_links_sites,
        df_nao_plotados,
        campos_detalhe=DETALHES_PADRAO_MAPA
    )


def caminho_exportacao_clientes():
    return Path(CLIENTES_FILE)


def caminho_exportacao_snmpc():
    return Path(caminho_estrutura_txt())


def caminho_exportacao_sites():
    return Path(caminho_sites_excel())


def caminho_cache_mapa():
    return Path(MAP_CACHE_FILE)


def caminho_indice_documentos():
    return Path(CONTRACTS_INDEX_FILE)
