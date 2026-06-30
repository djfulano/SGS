import os

from app.config import MAP_CONFIG_FILE
from app.storage import read_json
from app.storage import write_json_atomic


PROVEDORES_SATELITE = {
    "maptiler": "MapTiler",
    "mapbox": "Mapbox"
}
PROVEDORES_GEOCODING = {
    "maptiler": "MapTiler",
    "nominatim": "OpenStreetMap/Nominatim"
}

DEFAULT_MAP_CONFIG = {
    "satellite_provider": "maptiler",
    "geocoding_provider": "maptiler",
    "maptiler_api_key": "",
    "maptiler_style_id": "hybrid",
    "mapbox_api_key": "",
    "max_site_site_distance_km": 30.0,
    "max_site_client_distance_km": 30.0,
    "default_client_limit": 100,
    "elevation_provider": "open_elevation",
    "open_elevation_url": "https://api.open-elevation.com/api/v1/lookup",
    "line_of_sight_sample_distance_m": 100,
    "line_of_sight_frequency_ghz": 5.8,
    "line_of_sight_fresnel_clearance": 0.60,
    "elevation_timeout_seconds": 8
}


def normalizar_float_positivo(valor, padrao):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return float(padrao)

    if numero < 1:
        return float(padrao)

    return numero


def normalizar_int_positivo(valor, padrao):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return int(padrao)

    if numero < 1:
        return int(padrao)

    return numero


def normalizar_float_maior_que_zero(valor, padrao):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return float(padrao)

    if numero <= 0:
        return float(padrao)

    return numero


def normalizar_provedor(valor):

    provedor = str(valor or "").strip().lower()

    if provedor not in PROVEDORES_SATELITE:

        return DEFAULT_MAP_CONFIG["satellite_provider"]

    return provedor


def normalizar_provedor_geocoding(valor):

    provedor = str(valor or "").strip().lower()

    if provedor not in PROVEDORES_GEOCODING:

        return DEFAULT_MAP_CONFIG["geocoding_provider"]

    return provedor


def load_map_config(path=None):

    dados = read_json(
        path or MAP_CONFIG_FILE,
        {}
    )

    if not isinstance(dados, dict):

        dados = {}

    config = {
        **DEFAULT_MAP_CONFIG,
        **dados
    }
    config["satellite_provider"] = normalizar_provedor(
        config.get("satellite_provider")
    )
    config["geocoding_provider"] = normalizar_provedor_geocoding(
        config.get("geocoding_provider")
    )
    config["maptiler_style_id"] = (
        str(
            config.get("maptiler_style_id")
            or DEFAULT_MAP_CONFIG["maptiler_style_id"]
        ).strip()
        or DEFAULT_MAP_CONFIG["maptiler_style_id"]
    )

    for chave in ("maptiler_api_key", "mapbox_api_key"):

        config[chave] = str(
            config.get(chave)
            or ""
        ).strip()

    config["max_site_site_distance_km"] = normalizar_float_positivo(
        config.get("max_site_site_distance_km"),
        DEFAULT_MAP_CONFIG["max_site_site_distance_km"]
    )
    config["max_site_client_distance_km"] = normalizar_float_positivo(
        config.get("max_site_client_distance_km"),
        DEFAULT_MAP_CONFIG["max_site_client_distance_km"]
    )
    config["default_client_limit"] = normalizar_int_positivo(
        config.get("default_client_limit"),
        DEFAULT_MAP_CONFIG["default_client_limit"]
    )
    config["elevation_provider"] = str(
        config.get("elevation_provider")
        or DEFAULT_MAP_CONFIG["elevation_provider"]
    ).strip()
    config["open_elevation_url"] = str(
        config.get("open_elevation_url")
        or DEFAULT_MAP_CONFIG["open_elevation_url"]
    ).strip()
    config["line_of_sight_sample_distance_m"] = normalizar_float_positivo(
        config.get("line_of_sight_sample_distance_m"),
        DEFAULT_MAP_CONFIG["line_of_sight_sample_distance_m"]
    )
    config["line_of_sight_frequency_ghz"] = normalizar_float_positivo(
        config.get("line_of_sight_frequency_ghz"),
        DEFAULT_MAP_CONFIG["line_of_sight_frequency_ghz"]
    )
    config["line_of_sight_fresnel_clearance"] = normalizar_float_maior_que_zero(
        config.get("line_of_sight_fresnel_clearance")
        or DEFAULT_MAP_CONFIG["line_of_sight_fresnel_clearance"],
        DEFAULT_MAP_CONFIG["line_of_sight_fresnel_clearance"]
    )
    config["elevation_timeout_seconds"] = normalizar_int_positivo(
        config.get("elevation_timeout_seconds"),
        DEFAULT_MAP_CONFIG["elevation_timeout_seconds"]
    )

    return config


def save_map_config(config, path=None):

    config_atual = load_map_config(path)
    config_nova = {
        **config_atual,
        **(config or {})
    }
    config_nova["satellite_provider"] = normalizar_provedor(
        config_nova.get("satellite_provider")
    )
    config_nova["geocoding_provider"] = normalizar_provedor_geocoding(
        config_nova.get("geocoding_provider")
    )
    config_nova["maptiler_style_id"] = (
        str(
            config_nova.get("maptiler_style_id")
            or DEFAULT_MAP_CONFIG["maptiler_style_id"]
        ).strip()
        or DEFAULT_MAP_CONFIG["maptiler_style_id"]
    )

    for chave in ("maptiler_api_key", "mapbox_api_key"):

        config_nova[chave] = str(
            config_nova.get(chave)
            or ""
        ).strip()

    config_nova["max_site_site_distance_km"] = normalizar_float_positivo(
        config_nova.get("max_site_site_distance_km"),
        DEFAULT_MAP_CONFIG["max_site_site_distance_km"]
    )
    config_nova["max_site_client_distance_km"] = normalizar_float_positivo(
        config_nova.get("max_site_client_distance_km"),
        DEFAULT_MAP_CONFIG["max_site_client_distance_km"]
    )
    config_nova["default_client_limit"] = normalizar_int_positivo(
        config_nova.get("default_client_limit"),
        DEFAULT_MAP_CONFIG["default_client_limit"]
    )
    config_nova["elevation_provider"] = str(
        config_nova.get("elevation_provider")
        or DEFAULT_MAP_CONFIG["elevation_provider"]
    ).strip()
    config_nova["open_elevation_url"] = str(
        config_nova.get("open_elevation_url")
        or DEFAULT_MAP_CONFIG["open_elevation_url"]
    ).strip()
    config_nova["line_of_sight_sample_distance_m"] = normalizar_float_positivo(
        config_nova.get("line_of_sight_sample_distance_m"),
        DEFAULT_MAP_CONFIG["line_of_sight_sample_distance_m"]
    )
    config_nova["line_of_sight_frequency_ghz"] = normalizar_float_positivo(
        config_nova.get("line_of_sight_frequency_ghz"),
        DEFAULT_MAP_CONFIG["line_of_sight_frequency_ghz"]
    )
    config_nova["line_of_sight_fresnel_clearance"] = normalizar_float_maior_que_zero(
        config_nova.get("line_of_sight_fresnel_clearance")
        or DEFAULT_MAP_CONFIG["line_of_sight_fresnel_clearance"],
        DEFAULT_MAP_CONFIG["line_of_sight_fresnel_clearance"]
    )
    config_nova["elevation_timeout_seconds"] = normalizar_int_positivo(
        config_nova.get("elevation_timeout_seconds"),
        DEFAULT_MAP_CONFIG["elevation_timeout_seconds"]
    )

    write_json_atomic(
        path or MAP_CONFIG_FILE,
        config_nova
    )

    return config_nova


def map_config_value(config_key, env_names, default=""):

    config = load_map_config()
    valor = str(
        config.get(config_key)
        or ""
    ).strip()

    if valor:

        return valor

    for env_name in env_names:

        valor = os.getenv(env_name)

        if str(valor or "").strip():

            return str(valor).strip()

    return default
