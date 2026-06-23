import hashlib
import html
import json
import math
import re
import time
from datetime import datetime
from urllib.parse import quote
from urllib.parse import quote_plus

import pandas as pd
import requests

from app.config import GEOCODING_CACHE_FILE
from app.config import MAP_CACHE_FILE
from app.services.map_settings import DEFAULT_MAP_CONFIG
from app.services.map_settings import load_map_config
from app.services.map_settings import map_config_value
from app.services.map_settings import normalizar_provedor_geocoding
from app.services.map_settings import normalizar_provedor
from app.services.data_loader import versao_cache_dados
from app.services.equipment_catalog import load_equipment_catalog
from app.services.site_metrics import sites_descendentes
from app.storage import read_json
from app.storage import write_json_atomic


MAPA_SCHEMA_VERSION = 11
COR_LINHA_SITE = [210, 30, 30, 145]
COR_LINHA_CLIENTE = [20, 150, 70, 125]
COR_LINHA_POP_POP = [35, 110, 255, 180]
COR_LINHA_POP_DC = [115, 95, 255, 175]
COR_LINHA_SNPMC_SITE = [70, 95, 135, 150]


def limites_mapa():
    config = load_map_config()

    return {
        "site_site": float(
            config.get("max_site_site_distance_km")
            or DEFAULT_MAP_CONFIG["max_site_site_distance_km"]
        ),
        "site_cliente": float(
            config.get("max_site_client_distance_km")
            or DEFAULT_MAP_CONFIG["max_site_client_distance_km"]
        ),
        "limite_clientes_padrao": int(
            config.get("default_client_limit")
            or DEFAULT_MAP_CONFIG["default_client_limit"]
        )
    }


def cor_site(nome_site):

    digest = hashlib.md5(
        nome_site.encode("utf-8")
    ).hexdigest()

    return [
        80 + int(digest[0:2], 16) % 150,
        80 + int(digest[2:4], 16) % 150,
        80 + int(digest[4:6], 16) % 150,
        190
    ]


def tipo_cor_mapa(nome_site, setorial):
    def tipo_no_texto(valor):
        texto = str(valor or "").upper()

        if re.search(r"(^|[_\-\s])POP($|[_\-\s])", texto):
            return "POP"
        if re.search(r"(^|[_\-\s])BH($|[_\-\s])", texto):
            return "BH"
        if re.search(r"(^|[_\-\s])REP\d*($|[_\-\s])", texto):
            return "REP"

        return ""

    return tipo_no_texto(setorial) or tipo_no_texto(nome_site)


def cor_setorial(nome_site, setorial):
    tipo = tipo_cor_mapa(
        nome_site,
        setorial
    )

    cores_tipo = {
        "POP": [20, 150, 70, 220],
        "BH": [245, 130, 35, 220],
        "REP": [245, 210, 45, 220]
    }

    if tipo in cores_tipo:
        return cores_tipo[tipo]

    chave = f"{nome_site or ''}|{setorial or 'Direto'}"
    digest = hashlib.md5(
        chave.encode("utf-8")
    ).hexdigest()

    return [
        35 + int(digest[0:2], 16) % 185,
        45 + int(digest[2:4], 16) % 175,
        55 + int(digest[4:6], 16) % 165,
        220
    ]


def cor_ponto_site(nome_site, base_cor, setorial):
    if tipo_cor_mapa(nome_site, ""):
        return cor_setorial(
            nome_site,
            ""
        )

    return cor_setorial(
        base_cor,
        setorial
    )


def cor_setorial_suave(nome_site, setorial):

    cor = cor_setorial(
        nome_site,
        setorial
    )

    return [
        cor[0],
        cor[1],
        cor[2],
        115
    ]


def cor_suave_de_cor(cor):
    cor = cor_rgba_mapa(
        cor,
        [30, 80, 120, 220]
    )

    return [
        cor[0],
        cor[1],
        cor[2],
        115
    ]


def cor_linha_cliente_por_site(cor_site):
    cor = cor_rgba_mapa(
        cor_site,
        COR_LINHA_CLIENTE
    )

    return [
        cor[0],
        cor[1],
        cor[2],
        COR_LINHA_CLIENTE[3]
    ]


def cor_rgba_mapa(cor, fallback):
    if isinstance(cor, (list, tuple)) and len(cor) >= 3:
        try:
            alpha = int(cor[3]) if len(cor) >= 4 else fallback[3]
            return [
                max(0, min(255, int(cor[0]))),
                max(0, min(255, int(cor[1]))),
                max(0, min(255, int(cor[2]))),
                max(0, min(255, alpha))
            ]
        except (TypeError, ValueError):
            return fallback

    return fallback


def texto_html(valor):

    return html.escape(
        str(valor or "")
    )


def formatar_moeda_mapa(valor):

    try:

        numero = float(valor or 0)

    except (TypeError, ValueError):

        return "R$ 0,00"

    return (
        f"R$ {numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def formatar_coordenadas(latitude, longitude):

    return f"{coordenada_float(latitude):.6f}, {coordenada_float(longitude):.6f}"


def catalogo_equipamentos_por_icone():

    try:

        df_catalogo = load_equipment_catalog()

    except Exception:

        return {}

    if df_catalogo.empty:

        return {}

    return {
        str(linha.get("Ícone") or "").strip(): str(
            linha.get("Nome") or ""
        ).strip()
        for linha in df_catalogo.to_dict("records")
        if str(linha.get("Ícone") or "").strip()
    }


def equipamentos_por_assinatura_sites(sites_usados):

    catalogo = catalogo_equipamentos_por_icone()
    equipamentos_por_assinatura = {}

    for site in sites_usados.values():

        for equipamento in getattr(site, "equipamentos", []) or []:

            assinatura = str(
                equipamento.get("Assinatura") or ""
            ).strip()

            if not assinatura:

                continue

            icone = str(
                equipamento.get("Icone") or ""
            ).strip()
            nome_catalogo = catalogo.get(icone, "")
            nome_exibicao = nome_catalogo or icone

            if not nome_exibicao:

                continue

            equipamentos_por_assinatura.setdefault(
                assinatura,
                []
            ).append(nome_exibicao)

    return {
        assinatura: ", ".join(
            sorted(set(nomes))
        )
        for assinatura, nomes in equipamentos_por_assinatura.items()
    }


def coordenada_float(valor):

    try:

        return float(valor)

    except (TypeError, ValueError):

        return 0.0


def coordenada_valida(latitude, longitude):

    latitude = coordenada_float(latitude)
    longitude = coordenada_float(longitude)

    return (
        latitude != 0
        and longitude != 0
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def distancia_km(latitude_origem, longitude_origem, latitude_destino, longitude_destino):

    lat1 = math.radians(
        coordenada_float(latitude_origem)
    )
    lon1 = math.radians(
        coordenada_float(longitude_origem)
    )
    lat2 = math.radians(
        coordenada_float(latitude_destino)
    )
    lon2 = math.radians(
        coordenada_float(longitude_destino)
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 6371.0088 * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1 - haversine)
    )


def arredondar_distancia(distancia):

    return round(
        float(distancia),
        2
    )


def endereco_site_mapa(site):

    endereco = getattr(site, "endereco", "")
    numero = getattr(site, "numero", "")

    if numero:

        endereco = f"{endereco}, {numero}" if endereco else numero

    partes_endereco = [
        endereco,
        getattr(site, "bairro", ""),
        getattr(site, "cidade", ""),
        getattr(site, "uf", ""),
        getattr(site, "cep", "")
    ]

    partes = [
        parte
        for parte in partes_endereco
        if str(parte).strip()
    ]

    if partes:
        partes.append("Brasil")

    return ", ".join(
        parte
        for parte in partes
    )


def provedor_geocoding():

    return normalizar_provedor_geocoding(
        map_config_value(
            "geocoding_provider",
            [
                "MAP_GEOCODING_PROVIDER",
                "GEOCODING_PROVIDER"
            ],
            DEFAULT_MAP_CONFIG["geocoding_provider"]
        )
    )


def chave_geocoding(endereco, provedor=None):

    provedor = str(
        provedor
        or provedor_geocoding()
    ).strip().upper()

    endereco_normalizado = str(endereco or "").strip().upper()

    if not endereco_normalizado:

        return ""

    return f"{provedor}::{endereco_normalizado}"


def ponto_site_mapa(
    site,
    cache_geocoding=None,
    atualizar_geocoding=False
):

    latitude = coordenada_float(
        getattr(site, "latitude", 0)
    )
    longitude = coordenada_float(
        getattr(site, "longitude", 0)
    )
    fonte_coordenada = "Cadastro"
    endereco = endereco_site_mapa(site)

    if atualizar_geocoding and cache_geocoding is not None and endereco:

        cache_geocoding.pop(
            chave_geocoding(endereco),
            None
        )

        try:

            ponto = geocodificar_endereco(
                endereco,
                cache_geocoding
            )

        except requests.RequestException:

            ponto = None

        if ponto:

            latitude = ponto["lat"]
            longitude = ponto["lon"]
            fonte_coordenada = "Endereco"

    if not coordenada_valida(latitude, longitude):

        if cache_geocoding is None or not endereco:

            return None

        try:

            ponto = geocodificar_endereco(
                endereco,
                cache_geocoding
            )

        except requests.RequestException:

            ponto = None

        if not ponto:

            return None

        latitude = ponto["lat"]
        longitude = ponto["lon"]
        fonte_coordenada = "Endereco"

    quantidade_clientes = len(
        getattr(site, "clientes", []) or []
    )

    tooltip = (
        f"<b>{texto_html(site.nome)}</b><br/>"
        f"Endereço: {texto_html(endereco)}<br/>"
        f"Coordenadas: {texto_html(formatar_coordenadas(latitude, longitude))}<br/>"
        f"Quantidade de clientes: {quantidade_clientes}"
    )

    return {
        "Site": site.nome,
        "Tipo": getattr(site, "tipo", ""),
        "Status": getattr(site, "status_cadastro", ""),
        "Endereco": endereco,
        "Latitude": latitude,
        "Longitude": longitude,
        "Fonte Coordenada": fonte_coordenada,
        "Icone": "🗼",
        "Quantidade Clientes": quantidade_clientes,
        "Tooltip": tooltip,
        "Cor": [30, 80, 120, 230]
    }


def diagnostico_site_nao_plotado(site, cache_geocoding):
    latitude = coordenada_float(
        getattr(site, "latitude", 0)
    )
    longitude = coordenada_float(
        getattr(site, "longitude", 0)
    )
    endereco = endereco_site_mapa(site)

    if not coordenada_valida(latitude, longitude) and not endereco:
        motivo = "Sem coordenadas válidas e sem endereço para geocodificar"
    elif not coordenada_valida(latitude, longitude):
        chave = chave_geocoding(endereco)
        motivo = (
            "Endereço não localizado na geocodificação"
            if chave in cache_geocoding and cache_geocoding.get(chave) is None
            else "Sem coordenadas válidas; geocodificação falhou ou não retornou ponto"
        )
    else:
        motivo = "Coordenadas não puderam ser usadas no mapa"

    return {
        "Tipo Item": "Site",
        "Site": site.nome,
        "Cliente": "",
        "Assinatura": "",
        "Vínculo": "",
        "Motivo": motivo,
        "Endereco": endereco,
        "Latitude": latitude,
        "Longitude": longitude
    }


def carregar_cache_mapa():

    return read_json(
        MAP_CACHE_FILE,
        {}
    )


def salvar_cache_mapa(cache):

    write_json_atomic(
        MAP_CACHE_FILE,
        cache
    )


def assinatura_localizacao_site(site):

    return {
        "site": getattr(site, "nome", ""),
        "endereco": endereco_site_mapa(site),
        "latitude": coordenada_float(
            getattr(site, "latitude", 0)
        ),
        "longitude": coordenada_float(
            getattr(site, "longitude", 0)
        )
    }


def chave_cache_mapa(
    sites_usados,
    incluir_clientes,
    limite_clientes,
    enlaces_sites=None,
    limite_site_site_km=None,
    limite_site_cliente_km=None
):
    limites = limites_mapa()
    limite_site_site_km = (
        limites["site_site"]
        if limite_site_site_km is None
        else float(limite_site_site_km)
    )
    limite_site_cliente_km = (
        limites["site_cliente"]
        if limite_site_cliente_km is None
        else float(limite_site_cliente_km)
    )

    dados = {
        "schema": MAPA_SCHEMA_VERSION,
        "versao_dados": versao_cache_dados(),
        "sites": sorted(sites_usados.keys()),
        "localizacao_sites": [
            assinatura_localizacao_site(site)
            for site in sorted(
                sites_usados.values(),
                key=lambda item: getattr(item, "nome", "")
            )
        ],
        "incluir_clientes": bool(incluir_clientes),
        "limite_clientes": int(limite_clientes),
        "limite_site_site_km": float(limite_site_site_km),
        "limite_site_cliente_km": float(limite_site_cliente_km),
        "enlaces_sites": sorted(
            (
                str(enlace.get("ID Link") or ""),
                str(enlace.get("Site Origem") or ""),
                str(enlace.get("Site Destino") or ""),
                str(enlace.get("Tipo Enlace") or "")
            )
            for enlace in (enlaces_sites or [])
        )
    }

    return hashlib.sha256(
        json.dumps(
            dados,
            sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def endereco_cliente(cliente):

    partes = [
        getattr(cliente, "endereco_completo", ""),
        getattr(cliente, "bairro", ""),
        getattr(cliente, "cidade", ""),
        "SP",
        "Brasil"
    ]

    return ", ".join(
        parte
        for parte in partes
        if str(parte).strip()
    )


def montar_clientes_mapa_sites(sites_usados, limite_clientes):

    dados = []
    equipamentos_por_assinatura = equipamentos_por_assinatura_sites(
        sites_usados
    )

    for site_atual in sites_usados.values():

        for cliente in site_atual.clientes:

            endereco = endereco_cliente(cliente)

            if not endereco:

                continue

            setorial = getattr(cliente, "setorial", None) or "Direto"
            receita = getattr(cliente, "receita", 0)
            produto = getattr(cliente, "produto", "")
            assinatura = cliente.num_assinatura
            equipamento = equipamentos_por_assinatura.get(
                str(assinatura),
                ""
            )
            cor = cor_setorial(
                site_atual.nome,
                setorial
            )

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": assinatura,
                "Site": site_atual.nome,
                "Setorial": setorial,
                "Produto": produto,
                "Receita": receita,
                "Equipamento": equipamento,
                "Endereco": endereco,
                "CEP": getattr(cliente, "cep", ""),
                "Bairro": getattr(cliente, "bairro", ""),
                "Cidade": getattr(cliente, "cidade", ""),
                "Texto": f"{cliente.nome}\n{cliente.num_assinatura}",
                "Tooltip": (
                    f"<b>{texto_html(cliente.nome)}</b><br/>"
                    f"Produto: {texto_html(produto)}<br/>"
                    f"Receita: {texto_html(formatar_moeda_mapa(receita))}"
                ),
                "Cor": cor
            })

            if len(dados) >= int(limite_clientes):

                return pd.DataFrame(dados)

    return pd.DataFrame(dados)


def carregar_cache_geocoding():

    return read_json(
        GEOCODING_CACHE_FILE,
        {}
    )


def salvar_cache_geocoding(cache):

    write_json_atomic(
        GEOCODING_CACHE_FILE,
        cache
    )


def ponto_resposta_maptiler(dados):

    features = dados.get("features") or []

    if not features:

        return None

    primeiro = features[0]
    geometry = primeiro.get("geometry") or {}
    coordinates = geometry.get("coordinates") or primeiro.get("center") or []

    if len(coordinates) < 2:

        return None

    return {
        "lat": float(coordinates[1]),
        "lon": float(coordinates[0]),
        "provider": "maptiler"
    }


def geocodificar_endereco_maptiler(endereco):

    token = maptiler_api_key()

    if not token:

        return None

    resposta = requests.get(
        f"https://api.maptiler.com/geocoding/{quote(str(endereco), safe='')}.json",
        params={
            "key": token,
            "limit": 1,
            "country": "br",
            "language": "pt"
        },
        timeout=15
    )

    resposta.raise_for_status()

    return ponto_resposta_maptiler(
        resposta.json()
    )


def geocodificar_endereco_nominatim(endereco):

    resposta = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": endereco,
            "format": "json",
            "limit": 1,
            "countrycodes": "br"
        },
        headers={
            "User-Agent": "SNMPC-Dashboard/1.0"
        },
        timeout=15
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not dados:

        return None

    return {
        "lat": float(dados[0]["lat"]),
        "lon": float(dados[0]["lon"]),
        "provider": "nominatim"
    }


def geocodificar_endereco_sem_cache(endereco, provedor):

    if provedor == "maptiler":

        ponto = geocodificar_endereco_maptiler(endereco)

        if ponto:

            return ponto

        return geocodificar_endereco_nominatim(endereco)

    return geocodificar_endereco_nominatim(endereco)


def geocodificar_endereco(endereco, cache):

    provedor = provedor_geocoding()
    chave = chave_geocoding(
        endereco,
        provedor
    )

    if not chave:

        return None

    if chave in cache:

        return cache[chave]

    ponto = geocodificar_endereco_sem_cache(
        endereco,
        provedor
    )

    if not ponto:

        cache[chave] = None

        return None

    cache[chave] = ponto

    if ponto.get("provider") == "nominatim":

        time.sleep(1)

    return ponto


def geocodificar_clientes_mapa(df_clientes, status_callback=None, progress_callback=None):

    cache = carregar_cache_geocoding()
    dados = []

    total = len(df_clientes)

    for indice, (_, linha) in enumerate(df_clientes.iterrows(), start=1):

        if status_callback:

            status_callback(
                f"Geocodificando {indice}/{total}: {linha['Cliente']}"
            )

        try:

            ponto = geocodificar_endereco(
                linha["Endereco"],
                cache
            )

        except requests.RequestException:

            ponto = None

        if ponto:

            registro = linha.to_dict()
            registro["Latitude"] = ponto["lat"]
            registro["Longitude"] = ponto["lon"]
            dados.append(registro)

        if progress_callback:

            progress_callback(
                indice / total
            )

    salvar_cache_geocoding(cache)

    return pd.DataFrame(dados)


def geocodificar_clientes_mapa_com_diagnostico(
    df_clientes,
    atualizar_geocoding=False,
    status_callback=None,
    progress_callback=None
):
    cache = carregar_cache_geocoding()
    dados = []
    nao_plotados = []

    total = len(df_clientes)

    for indice, (_, linha) in enumerate(df_clientes.iterrows(), start=1):

        if status_callback:

            status_callback(
                f"Geocodificando {indice}/{total}: {linha['Cliente']}"
            )

        endereco = str(
            linha.get("Endereco") or ""
        ).strip()
        ponto = None
        erro_geocoding = False

        if endereco:
            if atualizar_geocoding:
                cache.pop(
                    chave_geocoding(endereco),
                    None
                )

            try:
                ponto = geocodificar_endereco(
                    endereco,
                    cache
                )
            except requests.RequestException:
                erro_geocoding = True

        if ponto:
            registro = linha.to_dict()
            registro["Latitude"] = ponto["lat"]
            registro["Longitude"] = ponto["lon"]
            dados.append(registro)
        else:
            nao_plotados.append({
                "Tipo Item": "Cliente",
                "Site": linha.get("Site", ""),
                "Cliente": linha.get("Cliente", ""),
                "Assinatura": linha.get("Assinatura", ""),
                "Vínculo": "",
                "Motivo": (
                    "Sem endereço para geocodificar"
                    if not endereco
                    else (
                        "Falha na geocodificação do endereço"
                        if erro_geocoding
                        else "Endereço não localizado na geocodificação"
                    )
                ),
                "Endereco": endereco,
                "Latitude": "",
                "Longitude": ""
            })

        if progress_callback:

            progress_callback(
                indice / total
            )

    salvar_cache_geocoding(cache)

    return pd.DataFrame(dados), nao_plotados


def montar_clientes_mapa(site, incluir_filhos=True):

    dados = []

    sites_consulta = (
        sites_descendentes(site)
        if incluir_filhos
        else [site]
    )
    equipamentos_por_assinatura = equipamentos_por_assinatura_sites({
        site_atual.nome: site_atual
        for site_atual in sites_consulta
    })

    for site_atual in sites_consulta:

        for cliente in site_atual.clientes:

            endereco = endereco_cliente(cliente)

            if not endereco:

                continue

            setorial = getattr(cliente, "setorial", None) or "Direto"
            receita = getattr(cliente, "receita", 0)
            produto = getattr(cliente, "produto", "")
            assinatura = cliente.num_assinatura
            equipamento = equipamentos_por_assinatura.get(
                str(assinatura),
                ""
            )

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": assinatura,
                "Site": site_atual.nome,
                "Setorial": setorial,
                "Produto": produto,
                "Receita": receita,
                "Equipamento": equipamento,
                "Endereco": endereco,
                "CEP": getattr(cliente, "cep", ""),
                "Bairro": getattr(cliente, "bairro", ""),
                "Cidade": getattr(cliente, "cidade", ""),
                "Texto": f"{cliente.nome}\n{cliente.num_assinatura}",
                "Icone Setorial": setorial,
                "Tooltip": (
                    f"<b>{texto_html(cliente.nome)}</b><br/>"
                    f"Produto: {texto_html(produto)}<br/>"
                    f"Receita: {texto_html(formatar_moeda_mapa(receita))}"
                ),
                "Cor": cor_setorial(
                    site_atual.nome,
                    setorial
                )
            })

    return pd.DataFrame(dados)


def compilar_dados_mapa(
    sites_selecionados,
    sites_usados,
    incluir_clientes,
    limite_clientes,
    enlaces_sites=None,
    atualizar_geocoding_sites=False,
    atualizar_geocoding_clientes=False,
    status_sites_callback=None,
    status_clientes_callback=None,
    progress_clientes_callback=None
):
    limites_config = limites_mapa()
    limite_site_site_km = limites_config["site_site"]
    limite_site_cliente_km = limites_config["site_cliente"]

    chave = chave_cache_mapa(
        sites_usados,
        incluir_clientes,
        limite_clientes,
        enlaces_sites,
        limite_site_site_km,
        limite_site_cliente_km
    )
    cache = carregar_cache_mapa()

    if chave in cache:

        return cache[chave], True

    pontos_sites = []
    pontos_por_site = {}
    itens_nao_plotados = []
    cache_geocoding = carregar_cache_geocoding()
    total_sites = len(sites_usados)
    setorial_site = {
        nome_site: {
            "setorial": "Direto",
            "base_cor": nome_site
        }
        for nome_site in sites_usados
    }

    for site in sites_usados.values():

        for nome_setorial, sites_filhos in getattr(
            site,
            "sites_por_setorial",
            {}
        ).items():

            for site_filho in sites_filhos:

                if site_filho.nome in setorial_site:

                    setorial_site[site_filho.nome] = {
                        "setorial": nome_setorial or "Direto",
                        "base_cor": site.nome
                    }

    for indice, site in enumerate(sites_usados.values(), start=1):

        if status_sites_callback:

            status_sites_callback(
                f"Preparando sites {indice}/{total_sites}: {site.nome}"
            )

        ponto = ponto_site_mapa(
            site,
            cache_geocoding,
            atualizar_geocoding=atualizar_geocoding_sites
        )

        if ponto:
            info_setorial = setorial_site.get(
                site.nome,
                {
                    "setorial": "Direto",
                    "base_cor": site.nome
                }
            )
            ponto["Setorial"] = info_setorial["setorial"]
            ponto["Base Cor Setorial"] = info_setorial["base_cor"]
            ponto["Cor"] = cor_ponto_site(
                site.nome,
                info_setorial["base_cor"],
                info_setorial["setorial"]
            )
            ponto["Cor Suave"] = cor_suave_de_cor(
                ponto["Cor"]
            )
            ponto["Tooltip"] = (
                f"{ponto.get('Tooltip', '')}<br/>"
                f"Setorial: {texto_html(info_setorial['setorial'])}"
            )

            pontos_sites.append(ponto)
            pontos_por_site[site.nome] = ponto
        else:
            itens_nao_plotados.append(
                diagnostico_site_nao_plotado(
                    site,
                    cache_geocoding
                )
            )

    salvar_cache_geocoding(cache_geocoding)

    sites_excluidos_distancia = set()

    for site in sites_usados.values():

        pai = getattr(site, "pai", None)

        if not pai:

            continue

        ponto_site = pontos_por_site.get(site.nome)
        ponto_pai = pontos_por_site.get(pai.nome)

        if not ponto_site or not ponto_pai:

            continue

        distancia = arredondar_distancia(
            distancia_km(
                ponto_pai["Latitude"],
                ponto_pai["Longitude"],
                ponto_site["Latitude"],
                ponto_site["Longitude"]
            )
        )

        ponto_site["Distância Pai Km"] = distancia
        ponto_site["Site Pai"] = pai.nome

        if distancia > limite_site_site_km:

            sites_excluidos_distancia.add(site.nome)
            itens_nao_plotados.append({
                "Tipo Item": "Site",
                "Site": site.nome,
                "Cliente": "",
                "Assinatura": "",
                "Vínculo": f"{pai.nome} -> {site.nome}",
                "Motivo": (
                    "Site filho não plotado porque está a mais de "
                    f"{limite_site_site_km:.0f} km do site pai"
                ),
                "Endereco": ponto_site.get("Endereco", ""),
                "Latitude": ponto_site.get("Latitude", ""),
                "Longitude": ponto_site.get("Longitude", ""),
                "Distância Km": distancia,
                "Limite Km": limite_site_site_km
            })

    if sites_excluidos_distancia:

        pontos_sites = [
            ponto
            for ponto in pontos_sites
            if ponto.get("Site") not in sites_excluidos_distancia
        ]
        pontos_por_site = {
            site_nome: ponto
            for site_nome, ponto in pontos_por_site.items()
            if site_nome not in sites_excluidos_distancia
        }

    links_sites = []

    for site in sites_usados.values():

        pai = getattr(site, "pai", None)

        if not pai:

            continue

        if site.nome not in pontos_por_site or pai.nome not in pontos_por_site:

            itens_nao_plotados.append({
                "Tipo Item": "Vínculo site",
                "Site": site.nome,
                "Cliente": "",
                "Assinatura": "",
                "Vínculo": f"{pai.nome} -> {site.nome}",
                "Motivo": "Vínculo não desenhado porque site pai ou site filho não tem coordenada no mapa",
                "Endereco": "",
                "Latitude": "",
                "Longitude": ""
            })

            continue

        origem = pontos_por_site[pai.nome]
        destino = pontos_por_site[site.nome]
        info_setorial = setorial_site.get(
            site.nome,
            {
                "setorial": "Direto",
                "base_cor": pai.nome
            }
        )
        distancia = arredondar_distancia(
            distancia_km(
                origem["Latitude"],
                origem["Longitude"],
                destino["Latitude"],
                destino["Longitude"]
            )
        )
        links_sites.append({
            "Site Pai": pai.nome,
            "Site Filho": site.nome,
            "Setorial": info_setorial["setorial"],
            "Tipo Vínculo": "Hierarquia",
            "Origem": [origem["Longitude"], origem["Latitude"]],
            "Destino": [destino["Longitude"], destino["Latitude"]],
            "Ponto Rotulo": [
                (origem["Longitude"] + destino["Longitude"]) / 2,
                (origem["Latitude"] + destino["Latitude"]) / 2
            ],
            "Distância Km": distancia,
            "Rotulo Distancia": f"{distancia:.2f} km",
            "Tooltip": (
                f"<b>{texto_html(pai.nome)} -> {texto_html(site.nome)}</b><br/>"
                f"Setorial: {texto_html(info_setorial['setorial'])}<br/>"
                f"Distância: {distancia:.2f} km"
            ),
            "Cor": COR_LINHA_SITE
        })

    chaves_enlaces_snmpc = set()

    for enlace in enlaces_sites or []:
        site_origem_nome = str(enlace.get("Site Origem") or "").strip()
        site_destino_nome = str(enlace.get("Site Destino") or "").strip()

        if (
            not site_origem_nome
            or not site_destino_nome
            or site_origem_nome == site_destino_nome
        ):
            continue

        if site_origem_nome not in sites_usados or site_destino_nome not in sites_usados:
            continue

        chave_enlace = tuple(sorted([
            site_origem_nome,
            site_destino_nome
        ])) + (
            str(enlace.get("ID Link") or ""),
            str(enlace.get("Nome Link") or "")
        )

        if chave_enlace in chaves_enlaces_snmpc:
            continue

        chaves_enlaces_snmpc.add(chave_enlace)

        if site_origem_nome not in pontos_por_site or site_destino_nome not in pontos_por_site:
            itens_nao_plotados.append({
                "Tipo Item": "Enlace SNMPc",
                "Site": site_origem_nome,
                "Cliente": "",
                "Assinatura": "",
                "Vínculo": f"{site_origem_nome} -> {site_destino_nome}",
                "Motivo": "Enlace SNMPc não desenhado porque origem ou destino não tem coordenada no mapa",
                "Endereco": "",
                "Latitude": "",
                "Longitude": "",
                "Tipo Enlace": enlace.get("Tipo Enlace", ""),
                "Nome Link": enlace.get("Nome Link", "")
            })
            continue

        origem = pontos_por_site[site_origem_nome]
        destino = pontos_por_site[site_destino_nome]
        distancia = arredondar_distancia(
            distancia_km(
                origem["Latitude"],
                origem["Longitude"],
                destino["Latitude"],
                destino["Longitude"]
            )
        )
        tipo_enlace = enlace.get("Tipo Enlace") or "Site x Site"

        if tipo_enlace == "POP x POP":
            cor = COR_LINHA_POP_POP
        elif tipo_enlace == "POP x DC":
            cor = COR_LINHA_POP_DC
        else:
            cor = COR_LINHA_SNPMC_SITE

        links_sites.append({
            "Site Pai": site_origem_nome,
            "Site Filho": site_destino_nome,
            "Setorial": "SNMPc",
            "Tipo Vínculo": f"Enlace SNMPc - {tipo_enlace}",
            "Nome Link": enlace.get("Nome Link", ""),
            "Origem Endpoint": enlace.get("Origem Endpoint", ""),
            "Destino Endpoint": enlace.get("Destino Endpoint", ""),
            "ID Link": enlace.get("ID Link", ""),
            "Origem": [origem["Longitude"], origem["Latitude"]],
            "Destino": [destino["Longitude"], destino["Latitude"]],
            "Ponto Rotulo": [
                (origem["Longitude"] + destino["Longitude"]) / 2,
                (origem["Latitude"] + destino["Latitude"]) / 2
            ],
            "Distância Km": distancia,
            "Rotulo Distancia": f"{distancia:.2f} km",
            "Tooltip": (
                f"<b>{texto_html(site_origem_nome)} -> {texto_html(site_destino_nome)}</b><br/>"
                f"Tipo: {texto_html(tipo_enlace)}<br/>"
                f"Link: {texto_html(enlace.get('Nome Link', ''))}<br/>"
                f"Distância: {distancia:.2f} km"
            ),
            "Cor": cor
        })

    pontos_clientes = []
    links_clientes = []

    if incluir_clientes:

        df_clientes = montar_clientes_mapa_sites(
            sites_usados,
            limite_clientes
        )

        if not df_clientes.empty:

            df_clientes, clientes_nao_plotados = geocodificar_clientes_mapa_com_diagnostico(
                df_clientes,
                atualizar_geocoding=atualizar_geocoding_clientes,
                status_callback=status_clientes_callback,
                progress_callback=progress_clientes_callback
            )
            itens_nao_plotados.extend(clientes_nao_plotados)

            for registro in df_clientes.to_dict("records"):

                ponto_site = pontos_por_site.get(
                    registro.get("Site")
                )

                if ponto_site:

                    distancia = arredondar_distancia(
                        distancia_km(
                            ponto_site["Latitude"],
                            ponto_site["Longitude"],
                            registro.get("Latitude"),
                            registro.get("Longitude")
                        )
                    )

                    if distancia > limite_site_cliente_km:

                        itens_nao_plotados.append({
                            "Tipo Item": "Cliente",
                            "Site": registro.get("Site", ""),
                            "Cliente": registro.get("Cliente", ""),
                            "Assinatura": registro.get("Assinatura", ""),
                            "Vínculo": f"{registro.get('Site', '')} -> {registro.get('Cliente', '')}",
                            "Motivo": (
                                "Cliente não plotado porque está a mais de "
                                f"{limite_site_cliente_km:.0f} km do site pai"
                            ),
                            "Endereco": registro.get("Endereco", ""),
                            "Latitude": registro.get("Latitude", ""),
                            "Longitude": registro.get("Longitude", ""),
                            "Distância Km": distancia,
                            "Limite Km": limite_site_cliente_km
                        })

                        continue

                    registro["Distância Site Km"] = distancia
                    pontos_clientes.append(registro)
                    registro["Tooltip"] = (
                        f"<b>{texto_html(registro.get('Cliente'))}</b><br/>"
                        f"Produto: {texto_html(registro.get('Produto'))}<br/>"
                        f"Receita: {texto_html(formatar_moeda_mapa(registro.get('Receita')))}<br/>"
                        f"Distância: {distancia:.2f} km<br/>"
                        f"Setorial: {texto_html(registro.get('Setorial'))}<br/>"
                        f"Equipamento: {texto_html(registro.get('Equipamento'))}"
                    )
                    links_clientes.append({
                        "Site": registro.get("Site"),
                        "Cliente": registro.get("Cliente"),
                        "Assinatura": registro.get("Assinatura", ""),
                        "Setorial": registro.get("Setorial", "Direto"),
                        "Produto": registro.get("Produto", ""),
                        "Receita": registro.get("Receita", 0),
                        "Origem": [
                            ponto_site["Longitude"],
                            ponto_site["Latitude"]
                        ],
                        "Destino": [
                            registro.get("Longitude"),
                            registro.get("Latitude")
                        ],
                        "Ponto Rotulo": [
                            (
                                ponto_site["Longitude"]
                                + registro.get("Longitude")
                            ) / 2,
                            (
                                ponto_site["Latitude"]
                                + registro.get("Latitude")
                            ) / 2
                        ],
                        "Distância Km": distancia,
                        "Rotulo Distancia": f"{distancia:.2f} km",
                        "Tooltip": (
                            f"<b>{texto_html(registro.get('Site'))} -> "
                            f"{texto_html(registro.get('Cliente'))}</b><br/>"
                            f"Setorial: {texto_html(registro.get('Setorial'))}<br/>"
                            f"Distância: {distancia:.2f} km"
                        ),
                        "Cor": cor_linha_cliente_por_site(
                            ponto_site.get("Cor")
                        )
                    })
                else:
                    itens_nao_plotados.append({
                        "Tipo Item": "Vínculo cliente",
                        "Site": registro.get("Site", ""),
                        "Cliente": registro.get("Cliente", ""),
                        "Assinatura": registro.get("Assinatura", ""),
                        "Vínculo": f"{registro.get('Site', '')} -> {registro.get('Cliente', '')}",
                        "Motivo": "Vínculo não desenhado porque o site do cliente não tem coordenada no mapa",
                        "Endereco": registro.get("Endereco", ""),
                        "Latitude": registro.get("Latitude", ""),
                        "Longitude": registro.get("Longitude", "")
                    })

    pacote = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sites_selecionados": sorted(sites_selecionados.keys()),
        "sites": pontos_sites,
        "clientes": pontos_clientes,
        "links_clientes": links_clientes,
        "links_sites": links_sites,
        "nao_plotados": itens_nao_plotados,
        "limite_clientes": int(limite_clientes),
        "limite_site_site_km": limite_site_site_km,
        "limite_site_cliente_km": limite_site_cliente_km
    }

    cache[chave] = pacote
    salvar_cache_mapa(cache)

    return pacote, False


def dataframes_mapa(pacote):

    return (
        pd.DataFrame(pacote.get("sites", [])),
        pd.DataFrame(pacote.get("clientes", [])),
        pd.DataFrame(pacote.get("links_clientes", [])),
        pd.DataFrame(pacote.get("links_sites", [])),
        pd.DataFrame(pacote.get("nao_plotados", []))
    )


def mapbox_api_key():

    return map_config_value(
        "mapbox_api_key",
        [
            "MAPBOX_API_KEY",
            "MAPBOX_TOKEN"
        ]
    )


def maptiler_api_key():

    return map_config_value(
        "maptiler_api_key",
        [
            "MAPTILER_API_KEY",
            "MAPTILER_TOKEN"
        ]
    )


def provedor_mapa_satelite():

    return normalizar_provedor(
        map_config_value(
            "satellite_provider",
            [
                "MAP_SATELLITE_PROVIDER",
                "MAP_PROVIDER"
            ],
            DEFAULT_MAP_CONFIG["satellite_provider"]
        )
    )


def maptiler_satellite_style_id():

    return map_config_value(
        "maptiler_style_id",
        [
            "MAPTILER_SATELLITE_STYLE_ID"
        ],
        DEFAULT_MAP_CONFIG["maptiler_style_id"]
    )


def maptiler_satellite_style_url():

    token = maptiler_api_key()

    if not token:

        return ""

    style_id = quote_plus(maptiler_satellite_style_id())

    return (
        f"https://api.maptiler.com/maps/{style_id}/style.json"
        f"?key={quote_plus(token)}"
    )
