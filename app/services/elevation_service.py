import requests

from app.config import ELEVATION_CACHE_FILE
from app.services.map_settings import load_map_config
from app.storage import read_json
from app.storage import write_json_atomic


def chave_elevacao(latitude, longitude):
    return f"{float(latitude):.5f},{float(longitude):.5f}"


def carregar_cache_elevacao(path=None):
    dados = read_json(
        path or ELEVATION_CACHE_FILE,
        {}
    )
    return dados if isinstance(dados, dict) else {}


def salvar_cache_elevacao(cache, path=None):
    write_json_atomic(
        path or ELEVATION_CACHE_FILE,
        cache or {}
    )


def consultar_open_elevation(pontos, config=None):
    config = config or load_map_config()
    url = config.get("open_elevation_url")
    timeout = int(config.get("elevation_timeout_seconds") or 8)
    locations = [
        {
            "latitude": float(ponto["Latitude"]),
            "longitude": float(ponto["Longitude"])
        }
        for ponto in pontos
    ]

    resposta = requests.post(
        url,
        json={
            "locations": locations
        },
        timeout=timeout
    )
    resposta.raise_for_status()
    dados = resposta.json()

    return [
        float(resultado.get("elevation") or 0)
        for resultado in dados.get("results", [])
    ]


def elevacoes_pontos(pontos, config=None, cache=None):
    config = config or load_map_config()
    cache = cache if cache is not None else carregar_cache_elevacao()
    elevacoes = []
    faltantes = []
    indices_faltantes = []

    for indice, ponto in enumerate(pontos):
        chave = chave_elevacao(
            ponto["Latitude"],
            ponto["Longitude"]
        )

        if chave in cache:
            elevacoes.append(float(cache[chave]))
        else:
            elevacoes.append(0.0)
            faltantes.append(ponto)
            indices_faltantes.append(indice)

    estimado = False

    if faltantes and config.get("elevation_provider") == "open_elevation":
        try:
            elevacoes_faltantes = consultar_open_elevation(
                faltantes,
                config=config
            )
            for indice_lista, elevacao in zip(indices_faltantes, elevacoes_faltantes):
                elevacoes[indice_lista] = float(elevacao)
                cache[
                    chave_elevacao(
                        pontos[indice_lista]["Latitude"],
                        pontos[indice_lista]["Longitude"]
                    )
                ] = float(elevacao)
        except requests.RequestException:
            estimado = True
    elif faltantes:
        estimado = True

    salvar_cache_elevacao(cache)

    return elevacoes, estimado
