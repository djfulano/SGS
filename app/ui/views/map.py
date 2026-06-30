import re
from datetime import datetime

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

from app.auth import can_view_values
from app.services.map_service import carregar_cache_geocoding
from app.services.map_service import carregar_cache_mapa
from app.services.map_service import chave_cache_mapa
from app.services.map_service import compilar_dados_mapa
from app.services.map_service import dataframes_mapa
from app.services.map_service import geocodificar_endereco
from app.services.map_service import mapbox_api_key
from app.services.map_service import maptiler_satellite_style_url
from app.services.map_service import limites_mapa
from app.services.map_service import provedor_mapa_satelite
from app.services.map_service import salvar_cache_geocoding
from app.services.map_service import salvar_cache_mapa
from app.services.map_export import montar_kml_mapa
from app.services.map_export import montar_kmz_mapa
from app.services.site_metrics import montar_escopo_sites
from app.services.site_metrics import montar_resumo_selecao_sites
from app.ui.components.tables import mostrar_grid
from app.ui.navigation import mostrar_subnavegacao
from app.ui.session import usuario_logado


MAPA_GERAL_CACHE_KEY = "__mapa_geral__"

COLUNAS_BUSCA_SITES = [
    "Site",
    "Endereco",
    "Cidade",
    "UF",
    "CEP",
    "Setorial"
]
COLUNAS_BUSCA_CLIENTES = [
    "Cliente",
    "Assinatura",
    "Produto",
    "Endereco",
    "Cidade",
    "Site",
    "Setorial",
    "Equipamento"
]
COLUNAS_BUSCA_LINKS_CLIENTES = [
    "Site",
    "Cliente",
    "Assinatura",
    "Setorial",
    "Produto"
]
COLUNAS_BUSCA_LINKS_SITES = [
    "Site Pai",
    "Site Filho",
    "Setorial",
    "Tipo Vínculo",
    "Nome Link",
    "Origem Endpoint",
    "Destino Endpoint"
]
COLUNAS_BUSCA_NAO_PLOTADOS = [
    "Site",
    "Cliente",
    "Assinatura",
    "Endereco",
    "Motivo",
    "Vínculo"
]
ITENS_EXPORTACAO_MAPA = {
    "Sites": "sites",
    "Clientes": "clientes",
    "Vínculos site x cliente": "links_clientes",
    "Vínculos entre sites": "links_sites",
    "Itens não plotados": "nao_plotados"
}
DETALHES_EXPORTACAO_MAPA = [
    "Endereço",
    "Coordenadas",
    "Setorial",
    "Distância",
    "Produto",
    "Equipamento",
    "Receita",
    "Motivo"
]


def usuario_pode_ver_valores_clientes():
    return can_view_values(
        usuario_logado()
    )


def sanitizar_tooltip_receita(texto):
    if not isinstance(texto, str) or "Receita:" not in texto:
        return texto

    return re.sub(
        r"(Receita:\s*)(.*?)(?=(<br\s*/?>|$))",
        r"\1Restrito",
        texto,
        flags=re.IGNORECASE
    )


def ocultar_valores_clientes_mapa(df, pode_ver_valores=False):
    if df is None or df.empty or pode_ver_valores:
        return df.copy() if df is not None else df

    df_restrito = df.copy()

    for coluna in [
        "Receita",
        "Mensalidade"
    ]:
        if coluna in df_restrito.columns:
            df_restrito[coluna] = "Restrito"

    if "Tooltip" in df_restrito.columns:
        df_restrito["Tooltip"] = df_restrito["Tooltip"].apply(
            sanitizar_tooltip_receita
        )

    return df_restrito


def filtro_dataframe_busca(df, termo, colunas):
    termo = str(termo or "").strip()

    if df.empty or not termo:
        return df.copy()

    filtro = pd.Series(
        False,
        index=df.index
    )

    for coluna in colunas:
        if coluna not in df.columns:
            continue

        filtro = filtro | df[coluna].astype(str).str.contains(
            termo,
            case=False,
            regex=False,
            na=False
        )

    return df[filtro].copy()


def filtrar_links_visiveis(df_links_clientes, df_links_sites, sites_visiveis, clientes_visiveis):
    if not df_links_clientes.empty:
        links_clientes = df_links_clientes[
            df_links_clientes["Site"].astype(str).isin(sites_visiveis)
            & df_links_clientes["Cliente"].astype(str).isin(clientes_visiveis)
        ].copy()
    else:
        links_clientes = df_links_clientes.copy()

    if not df_links_sites.empty:
        links_sites = df_links_sites[
            df_links_sites["Site Pai"].astype(str).isin(sites_visiveis)
            & df_links_sites["Site Filho"].astype(str).isin(sites_visiveis)
        ].copy()
    else:
        links_sites = df_links_sites.copy()

    return links_clientes, links_sites


def aplicar_busca_mapa(df_sites, df_clientes, df_links_clientes, df_links_sites, df_nao_plotados, termo):
    termo = str(termo or "").strip()

    if not termo:
        return {
            "ativo": False,
            "termo": "",
            "sites": df_sites,
            "clientes": df_clientes,
            "links_clientes": df_links_clientes,
            "links_sites": df_links_sites,
            "sites_tabela": df_sites,
            "clientes_tabela": df_clientes,
            "links_clientes_tabela": df_links_clientes,
            "links_sites_tabela": df_links_sites,
            "sites_resultado": df_sites.iloc[0:0].copy(),
            "clientes_resultado": df_clientes.iloc[0:0].copy(),
            "links_clientes_resultado": df_links_clientes.iloc[0:0].copy(),
            "links_sites_resultado": df_links_sites.iloc[0:0].copy(),
            "nao_plotados": df_nao_plotados,
            "resultados_plotados": 0,
            "resultados_nao_plotados": 0,
            "sem_resultado": False
        }

    sites_encontrados = filtro_dataframe_busca(
        df_sites,
        termo,
        COLUNAS_BUSCA_SITES
    )
    clientes_encontrados = filtro_dataframe_busca(
        df_clientes,
        termo,
        COLUNAS_BUSCA_CLIENTES
    )
    links_clientes_encontrados = filtro_dataframe_busca(
        df_links_clientes,
        termo,
        COLUNAS_BUSCA_LINKS_CLIENTES
    )
    links_sites_encontrados = filtro_dataframe_busca(
        df_links_sites,
        termo,
        COLUNAS_BUSCA_LINKS_SITES
    )
    nao_plotados_encontrados = filtro_dataframe_busca(
        df_nao_plotados,
        termo,
        COLUNAS_BUSCA_NAO_PLOTADOS
    )

    sites_visiveis = set()
    clientes_visiveis = set()

    if not sites_encontrados.empty and "Site" in sites_encontrados.columns:
        sites_visiveis.update(sites_encontrados["Site"].astype(str))

    if not clientes_encontrados.empty:
        if "Site" in clientes_encontrados.columns:
            sites_visiveis.update(clientes_encontrados["Site"].astype(str))
        if "Cliente" in clientes_encontrados.columns:
            clientes_visiveis.update(clientes_encontrados["Cliente"].astype(str))

    if not links_clientes_encontrados.empty:
        sites_visiveis.update(links_clientes_encontrados["Site"].astype(str))
        clientes_visiveis.update(links_clientes_encontrados["Cliente"].astype(str))

    if not links_sites_encontrados.empty:
        sites_visiveis.update(links_sites_encontrados["Site Pai"].astype(str))
        sites_visiveis.update(links_sites_encontrados["Site Filho"].astype(str))

    resultados_plotados = len(sites_encontrados) + len(clientes_encontrados)

    if sites_visiveis or clientes_visiveis:
        sites_tabela = (
            df_sites[df_sites["Site"].astype(str).isin(sites_visiveis)].copy()
            if "Site" in df_sites.columns
            else df_sites.iloc[0:0].copy()
        )
        clientes_tabela = (
            df_clientes[df_clientes["Cliente"].astype(str).isin(clientes_visiveis)].copy()
            if "Cliente" in df_clientes.columns
            else df_clientes.iloc[0:0].copy()
        )
        links_clientes_tabela, links_sites_tabela = filtrar_links_visiveis(
            df_links_clientes,
            df_links_sites,
            sites_visiveis,
            clientes_visiveis
        )
    else:
        sites_tabela = df_sites.iloc[0:0].copy()
        clientes_tabela = df_clientes.iloc[0:0].copy()
        links_clientes_tabela = df_links_clientes.iloc[0:0].copy()
        links_sites_tabela = df_links_sites.iloc[0:0].copy()

    resultados_nao_plotados = len(nao_plotados_encontrados)

    return {
        "ativo": True,
        "termo": termo,
        "sites": df_sites,
        "clientes": df_clientes,
        "links_clientes": df_links_clientes,
        "links_sites": df_links_sites,
        "sites_tabela": sites_tabela,
        "clientes_tabela": clientes_tabela,
        "links_clientes_tabela": links_clientes_tabela,
        "links_sites_tabela": links_sites_tabela,
        "sites_resultado": sites_tabela,
        "clientes_resultado": clientes_tabela,
        "links_clientes_resultado": links_clientes_tabela,
        "links_sites_resultado": links_sites_tabela,
        "nao_plotados": nao_plotados_encontrados,
        "resultados_plotados": resultados_plotados,
        "resultados_nao_plotados": resultados_nao_plotados,
        "sem_resultado": resultados_plotados == 0 and resultados_nao_plotados == 0
    }


def marcador_endereco_temporario(termo, ponto):
    if not ponto:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "Endereco": termo,
            "Latitude": float(ponto["lat"]),
            "Longitude": float(ponto["lon"]),
            "Tooltip": f"<b>Endereço pesquisado</b><br/>{termo}",
            "Cor": [245, 180, 40, 240],
            "Icone": "📍"
        }
    ])


def cor_rgba(cor, fallback):
    if isinstance(cor, (list, tuple)) and len(cor) >= 3:
        try:
            alpha = int(cor[3]) if len(cor) >= 4 else 255
            return [
                max(0, min(255, int(cor[0]))),
                max(0, min(255, int(cor[1]))),
                max(0, min(255, int(cor[2]))),
                max(0, min(255, alpha))
            ]
        except (TypeError, ValueError):
            return fallback

    return fallback


def cor_com_alpha(cor, alpha, fallback):
    rgba = cor_rgba(cor, fallback)
    return [
        rgba[0],
        rgba[1],
        rgba[2],
        alpha
    ]


def preparar_marcadores_sites(df_sites, zoom_mapa=13):
    if df_sites.empty:
        return df_sites.copy()

    df = df_sites.copy()
    df["Marcador"] = "📍"
    df["Alvo"] = "•"
    df["Tamanho Marcador"] = 28
    df["Tamanho Alvo"] = 13
    df["Offset Marcador"] = [[0, -18] for _indice in range(len(df))]
    df["Offset Alvo"] = [[0, 0] for _indice in range(len(df))]
    df["Cor Marcador"] = (
        df["Cor"]
        if "Cor" in df.columns
        else [[30, 80, 120, 230] for _indice in range(len(df))]
    )
    df["Cor Alvo"] = (
        df["Cor"]
        if "Cor" in df.columns
        else [[30, 80, 120, 255] for _indice in range(len(df))]
    )
    df["Cor Marcador"] = df["Cor Marcador"].apply(
        lambda cor: cor_com_alpha(cor, 191, [30, 80, 120, 191])
    )
    df["Cor Borda"] = [[17, 24, 39, 90] for _indice in range(len(df))]
    df["Raio Marcador"] = 22.5
    df["Raio Min Pixels"] = 10
    df["Raio Max Pixels"] = 23
    df["Largura Borda"] = 1
    df["CorMarcador"] = df["Cor Marcador"]
    df["CorBorda"] = df["Cor Borda"]
    df["RaioMarcador"] = df["Raio Marcador"]
    df["RaioMinPixels"] = df["Raio Min Pixels"]
    df["RaioMaxPixels"] = df["Raio Max Pixels"]
    df["LarguraBorda"] = df["Largura Borda"]

    return df


def preparar_marcadores_clientes(df_clientes, zoom_mapa=13):
    if df_clientes.empty:
        return df_clientes.copy()

    df = df_clientes.copy()
    df["Marcador"] = "•"
    df["Alvo"] = "+"
    df["Tamanho Marcador"] = 18
    df["Tamanho Alvo"] = 11
    df["Offset Marcador"] = [[0, 0] for _indice in range(len(df))]
    df["Offset Alvo"] = [[0, 0] for _indice in range(len(df))]
    df["Cor Marcador"] = [[130, 130, 130, 220] for _indice in range(len(df))]
    df["Cor Alvo"] = [[255, 255, 255, 230] for _indice in range(len(df))]
    df["Cor Marcador"] = df["Cor Marcador"].apply(
        lambda cor: cor_com_alpha(cor, 191, [130, 130, 130, 191])
    )
    df["Cor Borda"] = [[17, 24, 39, 70] for _indice in range(len(df))]
    df["Raio Marcador"] = 12.5
    df["Raio Min Pixels"] = 7
    df["Raio Max Pixels"] = 17
    df["Largura Borda"] = 1
    df["CorMarcador"] = df["Cor Marcador"]
    df["CorBorda"] = df["Cor Borda"]
    df["RaioMarcador"] = df["Raio Marcador"]
    df["RaioMinPixels"] = df["Raio Min Pixels"]
    df["RaioMaxPixels"] = df["Raio Max Pixels"]
    df["LarguraBorda"] = df["Largura Borda"]

    return df


def preparar_marcadores_busca(df_marcador, zoom_mapa=13):
    if df_marcador.empty:
        return df_marcador.copy()

    df = df_marcador.copy()
    df["Marcador"] = "📍"
    df["Alvo"] = "•"
    df["Tamanho Marcador"] = 32
    df["Tamanho Alvo"] = 14
    df["Offset Marcador"] = [[0, -20] for _indice in range(len(df))]
    df["Offset Alvo"] = [[0, 0] for _indice in range(len(df))]
    df["Cor Marcador"] = (
        df["Cor"]
        if "Cor" in df.columns
        else [[245, 180, 40, 240] for _indice in range(len(df))]
    )
    df["Cor Alvo"] = [[255, 255, 255, 245] for _indice in range(len(df))]
    df["Cor Marcador"] = df["Cor Marcador"].apply(
        lambda cor: cor_com_alpha(cor, 191, [245, 180, 40, 191])
    )
    df["Cor Borda"] = [[17, 24, 39, 110] for _indice in range(len(df))]
    df["Raio Marcador"] = 30
    df["Raio Min Pixels"] = 12
    df["Raio Max Pixels"] = 28
    df["Largura Borda"] = 1
    df["CorMarcador"] = df["Cor Marcador"]
    df["CorBorda"] = df["Cor Borda"]
    df["RaioMarcador"] = df["Raio Marcador"]
    df["RaioMinPixels"] = df["Raio Min Pixels"]
    df["RaioMaxPixels"] = df["Raio Max Pixels"]
    df["LarguraBorda"] = df["Largura Borda"]

    return df


def camadas_marcadores_geometricos(df_marcadores):
    if df_marcadores.empty:
        return []

    raio_min_pixels = int(df_marcadores["RaioMinPixels"].iloc[0])
    raio_max_pixels = int(df_marcadores["RaioMaxPixels"].iloc[0])

    return [
        pdk.Layer(
            "ScatterplotLayer",
            data=df_marcadores,
            get_position="[Longitude, Latitude]",
            get_fill_color="CorMarcador",
            get_line_color="CorBorda",
            get_radius="RaioMarcador",
            get_line_width="LarguraBorda",
            radius_min_pixels=raio_min_pixels,
            radius_max_pixels=raio_max_pixels,
            stroked=True,
            filled=True,
            pickable=True
        )
    ]


def buscar_endereco_temporario(termo):
    termo = str(termo or "").strip()

    if not termo:
        return pd.DataFrame()

    cache_geocoding = carregar_cache_geocoding()

    try:
        ponto = geocodificar_endereco(
            termo,
            cache_geocoding
        )
    except requests.RequestException:
        ponto = None

    salvar_cache_geocoding(cache_geocoding)

    return marcador_endereco_temporario(
        termo,
        ponto
    )


def mostrar_exportador_mapa(
    resultado_busca,
    df_sites,
    df_clientes,
    df_links_clientes,
    df_links_sites,
    df_nao_plotados,
    df_sites_tabela,
    df_clientes_tabela,
    df_links_clientes_tabela,
    df_links_sites_tabela,
    df_nao_plotados_tabela
):
    with st.expander("Exportar mapa", expanded=False):
        col_formato, col_escopo = st.columns(2)

        with col_formato:
            formato = st.radio(
                "Formato",
                [
                    "KMZ",
                    "KML"
                ],
                horizontal=True,
                key="mapa_exportar_formato"
            )

        opcoes_escopo = ["Mapa completo"]

        if resultado_busca.get("ativo"):
            opcoes_escopo.append("Resultado da busca")

        with col_escopo:
            escopo_exportacao = st.radio(
                "Escopo",
                opcoes_escopo,
                horizontal=True,
                key="mapa_exportar_escopo"
            )

        itens_selecionados = st.multiselect(
            "Itens",
            list(ITENS_EXPORTACAO_MAPA.keys()),
            default=list(ITENS_EXPORTACAO_MAPA.keys()),
            key="mapa_exportar_itens"
        )
        detalhes_selecionados = st.multiselect(
            "Informações no detalhe",
            DETALHES_EXPORTACAO_MAPA,
            default=DETALHES_EXPORTACAO_MAPA,
            key="mapa_exportar_detalhes"
        )

        if escopo_exportacao == "Resultado da busca":
            sites_exportacao = df_sites_tabela
            clientes_exportacao = df_clientes_tabela
            links_clientes_exportacao = df_links_clientes_tabela
            links_sites_exportacao = df_links_sites_tabela
            nao_plotados_exportacao = df_nao_plotados_tabela
        else:
            sites_exportacao = df_sites
            clientes_exportacao = df_clientes
            links_clientes_exportacao = df_links_clientes
            links_sites_exportacao = df_links_sites
            nao_plotados_exportacao = df_nao_plotados

        itens_chaves = [
            ITENS_EXPORTACAO_MAPA[item]
            for item in itens_selecionados
        ]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_base = f"sgs_mapa_{timestamp}"

        if formato == "KMZ":
            conteudo = montar_kmz_mapa(
                sites_exportacao,
                clientes_exportacao,
                links_clientes_exportacao,
                links_sites_exportacao,
                nao_plotados_exportacao,
                itens=itens_chaves,
                campos_detalhe=detalhes_selecionados
            )
            nome_arquivo = f"{nome_base}.kmz"
            mime = "application/vnd.google-earth.kmz"
        else:
            conteudo = montar_kml_mapa(
                sites_exportacao,
                clientes_exportacao,
                links_clientes_exportacao,
                links_sites_exportacao,
                nao_plotados_exportacao,
                itens=itens_chaves,
                campos_detalhe=detalhes_selecionados
            )
            nome_arquivo = f"{nome_base}.kml"
            mime = "application/vnd.google-earth.kml+xml"

        st.download_button(
            "Baixar arquivo",
            data=conteudo,
            file_name=nome_arquivo,
            mime=mime,
            disabled=not bool(itens_chaves),
            key="mapa_exportar_download"
        )


def pontos_centro_mapa(df_sites, df_clientes, df_marcador):
    pontos_lat = []
    pontos_lon = []

    for df in [
        df_sites,
        df_clientes,
        df_marcador
    ]:
        if df.empty:
            continue

        if "Latitude" not in df.columns or "Longitude" not in df.columns:
            continue

        pontos_lat.extend(df["Latitude"].tolist())
        pontos_lon.extend(df["Longitude"].tolist())

    return pontos_lat, pontos_lon


def centro_zoom_mapa(
    df_sites,
    df_clientes,
    df_sites_resultado,
    df_clientes_resultado,
    df_marcador,
    busca_ativa
):
    if not df_marcador.empty:
        latitudes, longitudes = pontos_centro_mapa(
            pd.DataFrame(),
            pd.DataFrame(),
            df_marcador
        )

        return latitudes, longitudes, 16

    if busca_ativa and (
        not df_sites_resultado.empty
        or not df_clientes_resultado.empty
    ):
        latitudes, longitudes = pontos_centro_mapa(
            df_sites_resultado,
            df_clientes_resultado,
            pd.DataFrame()
        )

        return latitudes, longitudes, 14

    latitudes, longitudes = pontos_centro_mapa(
        df_sites,
        df_clientes,
        pd.DataFrame()
    )

    return latitudes, longitudes, 9


def deve_atualizar_cache_mapa_geral(
    sites_escolhidos,
    sites,
    incluir_filhos,
    incluir_clientes,
    limite_clientes,
    resumo
):
    return (
        set(sites_escolhidos) == set(sites.keys())
        and bool(incluir_filhos)
        and bool(incluir_clientes)
        and int(limite_clientes) >= int(resumo.get("clientes_total") or 0)
    )


def salvar_cache_mapa_geral(pacote):
    cache = carregar_cache_mapa()
    cache[MAPA_GERAL_CACHE_KEY] = pacote
    salvar_cache_mapa(cache)


def carregar_pacote_mapa_geral():
    cache = carregar_cache_mapa()
    pacote = cache.get(MAPA_GERAL_CACHE_KEY)

    return pacote if isinstance(pacote, dict) else None


def renderizar_pacote_mapa(
    pacote,
    *,
    visualizacao="Satélite",
    busca_key="mapa_busca",
    limpar_key="mapa_limpar_busca",
    limpar_flag_key="mapa_busca_limpar_pendente",
    mostrar_metricas=True,
    mostrar_exportador=True,
    mostrar_tabelas=True,
    prefixo_key="mapa"
):
    df_sites, df_clientes, df_links_clientes, df_links_sites, df_nao_plotados = dataframes_mapa(
        pacote
    )
    pode_ver_valores_clientes = usuario_pode_ver_valores_clientes()
    df_clientes = ocultar_valores_clientes_mapa(
        df_clientes,
        pode_ver_valores_clientes
    )
    df_links_clientes = ocultar_valores_clientes_mapa(
        df_links_clientes,
        pode_ver_valores_clientes
    )
    df_nao_plotados = ocultar_valores_clientes_mapa(
        df_nao_plotados,
        pode_ver_valores_clientes
    )

    if st.session_state.pop(limpar_flag_key, False):
        st.session_state[busca_key] = ""

    col_busca, col_limpar = st.columns([4, 1])

    with col_busca:
        termo_busca_mapa = st.text_input(
            "Buscar no mapa",
            placeholder="Site, cliente, assinatura, produto, equipamento ou endereço",
            key=busca_key
        )

    with col_limpar:
        st.write("")
        if st.button(
            "Limpar busca",
            key=limpar_key,
            disabled=not bool(str(termo_busca_mapa or "").strip())
        ):
            st.session_state[limpar_flag_key] = True
            st.rerun()

    resultado_busca = aplicar_busca_mapa(
        df_sites,
        df_clientes,
        df_links_clientes,
        df_links_sites,
        df_nao_plotados,
        termo_busca_mapa
    )
    df_marcador_busca = pd.DataFrame()

    if resultado_busca["ativo"]:
        st.caption(
            "Busca ativa: "
            f"{resultado_busca['resultados_plotados']} item(ns) plotado(s) e "
            f"{resultado_busca['resultados_nao_plotados']} item(ns) não plotado(s) encontrado(s)."
        )

        if resultado_busca["sem_resultado"]:
            df_marcador_busca = buscar_endereco_temporario(
                termo_busca_mapa
            )

            if df_marcador_busca.empty:
                st.warning(
                    "Nenhum item ou endereço encontrado para a busca informada."
                )
            else:
                st.info(
                    "Endereço encontrado e marcado temporariamente no mapa."
                )

    df_sites_mapa = resultado_busca["sites"]
    df_clientes_mapa = resultado_busca["clientes"]
    df_links_clientes_mapa = resultado_busca["links_clientes"]
    df_links_sites_mapa = resultado_busca["links_sites"]
    df_sites_tabela = resultado_busca["sites_tabela"]
    df_clientes_tabela = resultado_busca["clientes_tabela"]
    df_links_clientes_tabela = resultado_busca["links_clientes_tabela"]
    df_links_sites_tabela = resultado_busca["links_sites_tabela"]
    df_nao_plotados_tabela = resultado_busca["nao_plotados"]

    if mostrar_exportador:
        mostrar_exportador_mapa(
            resultado_busca,
            df_sites,
            df_clientes,
            df_links_clientes,
            df_links_sites,
            df_nao_plotados,
            df_sites_tabela,
            df_clientes_tabela,
            df_links_clientes_tabela,
            df_links_sites_tabela,
            df_nao_plotados_tabela
        )

    if df_sites.empty and df_clientes.empty:

        st.warning(
            "Não há coordenadas de sites ou clientes para exibir neste escopo."
        )

        return

    pontos_lat, pontos_lon, zoom_mapa = centro_zoom_mapa(
        df_sites_mapa,
        df_clientes_mapa,
        resultado_busca["sites_resultado"],
        resultado_busca["clientes_resultado"],
        df_marcador_busca,
        resultado_busca["ativo"]
    )

    if not pontos_lat:
        pontos_lat, pontos_lon, zoom_mapa = centro_zoom_mapa(
            df_sites,
            df_clientes,
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            False
        )

    if mostrar_metricas:
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Sites com coordenada",
            len(df_sites)
        )

        col2.metric(
            "Clientes no mapa",
            len(df_clientes)
        )

        col3.metric(
            "Vínculos desenhados",
            len(df_links_clientes) + len(df_links_sites)
        )
        st.caption(
            f"Itens não plotados: {len(df_nao_plotados)}"
        )

    view_state = pdk.ViewState(
        latitude=sum(pontos_lat) / len(pontos_lat),
        longitude=sum(pontos_lon) / len(pontos_lon),
        zoom=zoom_mapa,
        pitch=0
    )

    camadas = []
    df_rotulos_distancia = pd.concat(
        [
            df_links_sites_mapa,
            df_links_clientes_mapa
        ],
        ignore_index=True
    )
    if not df_rotulos_distancia.empty:
        df_rotulos_distancia = df_rotulos_distancia[
            df_rotulos_distancia["Ponto Rotulo"].notna()
        ]

    if not df_links_clientes_mapa.empty:

        camadas.append(pdk.Layer(
            "LineLayer",
            data=df_links_clientes_mapa,
            get_source_position="Origem",
            get_target_position="Destino",
            get_color="Cor",
            get_width=3,
            pickable=True
        ))

    if not df_links_sites_mapa.empty:

        camadas.append(pdk.Layer(
            "LineLayer",
            data=df_links_sites_mapa,
            get_source_position="Origem",
            get_target_position="Destino",
            get_color="Cor",
            get_width=7,
            pickable=True
        ))

    if not df_rotulos_distancia.empty:

        camadas.append(pdk.Layer(
            "TextLayer",
            data=df_rotulos_distancia,
            get_position="Ponto Rotulo",
            get_text="Rotulo Distancia",
            get_color="Cor",
            get_size=12,
            get_alignment_baseline="'center'",
            get_pixel_offset=[0, -10],
            pickable=True
        ))

    if not df_clientes_mapa.empty:
        df_marcadores_clientes = preparar_marcadores_clientes(
            df_clientes_mapa,
            zoom_mapa
        )

        camadas.extend(
            camadas_marcadores_geometricos(df_marcadores_clientes)
        )

    if not df_sites_mapa.empty:
        df_marcadores_sites = preparar_marcadores_sites(
            df_sites_mapa,
            zoom_mapa
        )

        camadas.extend(
            camadas_marcadores_geometricos(df_marcadores_sites)
        )

    if not df_marcador_busca.empty:
        df_marcador_busca_visual = preparar_marcadores_busca(
            df_marcador_busca,
            zoom_mapa
        )

        camadas.extend(
            camadas_marcadores_geometricos(df_marcador_busca_visual)
        )

    estilo_ruas = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
    estilo_satelite = "mapbox://styles/mapbox/satellite-streets-v12"
    provedor_satelite = provedor_mapa_satelite()
    token_mapbox = mapbox_api_key()

    if visualizacao == "Satélite" and provedor_satelite == "maptiler":

        estilo_maptiler = maptiler_satellite_style_url()

        if estilo_maptiler:

            estilo_satelite = estilo_maptiler

        else:

            st.caption(
                "A visualização por satélite usa MapTiler; configure "
                "MAPTILER_API_KEY no ambiente."
            )

    elif visualizacao == "Satélite" and not token_mapbox:

        st.caption(
            "A visualização por satélite usa estilo Mapbox; se o fundo não "
            "aparecer, configure MAPBOX_API_KEY no ambiente."
        )

    estilos_mapa = {
        "Ruas": estilo_ruas,
        "Satélite": estilo_satelite
    }

    api_keys = (
        {
            "mapbox": token_mapbox
        }
        if token_mapbox and provedor_satelite == "mapbox"
        else None
    )

    st.pydeck_chart(
        pdk.Deck(
            map_style=estilos_mapa[visualizacao],
            map_provider="mapbox" if visualizacao == "Satélite" else "carto",
            api_keys=api_keys,
            initial_view_state=view_state,
            layers=camadas,
            tooltip={
                "html": "{Tooltip}"
            }
        )
    )

    if not mostrar_tabelas:
        return

    opcoes_abas_mapa = [
        "Sites",
        "Clientes",
        "Vinculos",
        "Não plotados"
    ]

    aba_mapa = st.segmented_control(
        "Dados do mapa",
        opcoes_abas_mapa,
        selection_mode="single",
        key=f"{prefixo_key}_aba_dados",
        label_visibility="collapsed",
        width="stretch"
    )

    if not aba_mapa:

        aba_mapa = "Sites"

    if aba_mapa == "Sites":

        if df_sites_tabela.empty:

            st.info("Nenhum site com latitude/longitude no cadastro.")

        else:

            mostrar_grid(
                df_sites_tabela.drop(
                    columns=[
                        "Cor",
                        "Cor Suave",
                        "Icone",
                        "Tooltip"
                    ],
                    errors="ignore"
                ),
                height=260,
                key=f"{prefixo_key}_sites_plotados"
            )

    elif aba_mapa == "Clientes":

        if df_clientes_tabela.empty:

            st.info("Nenhum cliente geocodificado para este escopo.")

        else:

            mostrar_grid(
                df_clientes_tabela.drop(
                    columns=[
                        "Cor",
                        "Tooltip"
                    ],
                    errors="ignore"
                ),
                height=260,
                key=f"{prefixo_key}_clientes_plotados"
            )

    elif aba_mapa == "Vinculos":

        dados_vinculos = []

        if not df_links_sites_tabela.empty:

            dados_vinculos.extend(
                df_links_sites_tabela.assign(Tipo="Site filho").to_dict("records")
            )

        if not df_links_clientes_tabela.empty:

            dados_vinculos.extend(
                df_links_clientes_tabela.assign(Tipo="Cliente").to_dict("records")
            )

        if not dados_vinculos:

            st.info("Nenhum vínculo com coordenadas para desenhar.")

        else:

            mostrar_grid(
                pd.DataFrame(dados_vinculos),
                height=260,
                key=f"{prefixo_key}_vinculos_plotados"
            )

    elif aba_mapa == "Não plotados":

        if df_nao_plotados_tabela.empty:

            st.info("Todos os itens elegíveis foram plotados ou vinculados.")

        else:

            mostrar_grid(
                df_nao_plotados_tabela,
                height=320,
                key=f"{prefixo_key}_itens_nao_plotados"
            )


def mostrar_mapa_personalizado(sites, enlaces_sites=None):

    st.header("Mapa personalizado")
    enlaces_sites = enlaces_sites or []
    config_limites_mapa = limites_mapa()

    opcoes_site = sorted(sites.keys())

    col1, col2 = st.columns([3, 1])

    with col1:

        sites_escolhidos = st.multiselect(
            "Sites para exibir",
            opcoes_site,
            key="mapa_sites_escolhidos"
        )

    with col2:

        visualizacao = st.radio(
            "Visualização",
            [
                "Ruas",
                "Satélite"
            ],
            index=1,
            horizontal=True,
            key="mapa_visualizacao"
        )

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:

        incluir_filhos = st.checkbox(
            "Carregar sites filhos",
            value=True,
            key="mapa_incluir_filhos"
        )

    with col2:

        incluir_clientes = st.checkbox(
            "Carregar clientes",
            value=True,
            key="mapa_incluir_clientes"
        )

    with col3:

        limite_clientes = st.number_input(
            "Limite de clientes na compilação",
            min_value=1,
            max_value=5000,
            value=int(config_limites_mapa["limite_clientes_padrao"]),
            step=100
        )

    with col4:
        exibir_enlaces_snmpc = st.checkbox(
            "Enlaces SNMPc entre sites",
            value=bool(enlaces_sites),
            disabled=not bool(enlaces_sites),
            key="mapa_exibir_enlaces_snmpc"
        )

    if not sites_escolhidos:

        st.info(
            "Escolha um ou mais sites para preparar o mapa."
        )

        return

    sites_selecionados, sites_usados = montar_escopo_sites(
        [
            sites[nome]
            for nome in sites_escolhidos
            if nome in sites
        ],
        incluir_filhos
    )

    resumo = montar_resumo_selecao_sites(
        sites_selecionados,
        sites_usados
    )

    col_acao_topologia, _col_acao_vazio = st.columns([1, 4])

    with col_acao_topologia:

        if st.button(
            "Carregar na Topologia",
            key="mapa_carregar_topologia"
        ):
            tipos_topologia = sorted({
                sites[nome_site].tipo
                for nome_site in sites_escolhidos
                if nome_site in sites
            })
            st.session_state["sites_selecionados_multiplos"] = sites_escolhidos
            st.session_state["incluir_filhos_sites"] = incluir_filhos
            if tipos_topologia:
                st.session_state["tipos_sites_multiplos"] = tipos_topologia
            st.session_state["mostrar_clientes_sites_selecionados"] = False
            st.session_state["proxima_aba_principal"] = "sites"
            st.rerun()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Sites no escopo",
        len(sites_usados)
    )

    col2.metric(
        "Clientes no escopo",
        resumo["clientes_total"]
    )

    col3.metric(
        "Clientes diretos",
        resumo["clientes_diretos"]
    )

    chave = chave_cache_mapa(
        sites_usados,
        incluir_clientes,
        limite_clientes,
        enlaces_sites if exibir_enlaces_snmpc else []
    )
    cache = carregar_cache_mapa()
    pacote = cache.get(chave)

    col1, col2 = st.columns([1, 4])

    with col1:

        compilar = st.button(
            "Compilar mapa",
            type="primary",
            key="mapa_compilar"
        )

    with col2:

        if pacote:

            st.caption(
                f"Mapa pré-compilado em {pacote.get('gerado_em', '')}. "
                "Use Compilar mapa para atualizar o pacote e refazer a geocodificação deste escopo."
            )

        else:

            st.caption(
                "Este escopo ainda não tem mapa compilado. "
                "A primeira compilação pode demorar por causa da geocodificação."
            )

    if compilar and chave in cache:

        del cache[chave]
        salvar_cache_mapa(cache)
        pacote = None

    if compilar or not pacote:

        status_sites = st.empty()
        progresso_clientes = st.progress(0) if incluir_clientes else None
        status_clientes = st.empty() if incluir_clientes else None

        try:

            pacote, cacheado = compilar_dados_mapa(
                sites_selecionados,
                sites_usados,
                incluir_clientes,
                limite_clientes,
                enlaces_sites=enlaces_sites if exibir_enlaces_snmpc else [],
                atualizar_geocoding_sites=compilar,
                atualizar_geocoding_clientes=compilar,
                status_sites_callback=status_sites.caption,
                status_clientes_callback=(
                    status_clientes.caption
                    if status_clientes
                    else None
                ),
                progress_clientes_callback=(
                    progresso_clientes.progress
                    if progresso_clientes
                    else None
                )
            )

        finally:

            status_sites.empty()

            if progresso_clientes:

                progresso_clientes.empty()

            if status_clientes:

                status_clientes.empty()

        st.success(
            "Mapa carregado do cache."
            if cacheado
            else "Mapa compilado e salvo no cache local."
        )

    if deve_atualizar_cache_mapa_geral(
        sites_escolhidos,
        sites,
        incluir_filhos,
        incluir_clientes,
        limite_clientes,
        resumo
    ):
        salvar_cache_mapa_geral(pacote)

    renderizar_pacote_mapa(
        pacote,
        visualizacao=visualizacao,
        busca_key="mapa_personalizado_busca",
        limpar_key="mapa_personalizado_limpar_busca",
        limpar_flag_key="mapa_personalizado_busca_limpar_pendente",
        mostrar_metricas=True,
        mostrar_exportador=True,
        mostrar_tabelas=True,
        prefixo_key="mapa_personalizado"
    )


def mostrar_mapa_geral():
    st.header("Mapa geral")

    pacote = carregar_pacote_mapa_geral()

    if not pacote:
        st.info(
            "Mapa geral ainda não compilado. Use Mapa Personalizado com todos os sites, "
            "sites filhos e clientes para compilar o mapa geral."
        )
        return

    renderizar_pacote_mapa(
        pacote,
        visualizacao="Satélite",
        busca_key="mapa_geral_busca",
        limpar_key="mapa_geral_limpar_busca",
        limpar_flag_key="mapa_geral_busca_limpar_pendente",
        mostrar_metricas=False,
        mostrar_exportador=False,
        mostrar_tabelas=False,
        prefixo_key="mapa_geral"
    )


def mostrar_mapa_clientes(sites, enlaces_sites=None):
    funcao = mostrar_subnavegacao(
        [
            (
                "mapa_geral",
                "Mapa Geral",
                mostrar_mapa_geral
            ),
            (
                "mapa_personalizado",
                "Mapa Personalizado",
                lambda: mostrar_mapa_personalizado(
                    sites,
                    enlaces_sites
                )
            )
        ],
        key="mapa_subaba"
    )

    if funcao:
        funcao()
