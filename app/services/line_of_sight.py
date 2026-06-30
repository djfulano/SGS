import math

import pandas as pd


RAIO_TERRA_KM = 6371.0


def valor_float(valor, padrao=0.0):
    try:
        if valor is None or pd.isna(valor):
            return float(padrao)
    except TypeError:
        pass

    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return float(padrao)


def coordenada_valida(latitude, longitude):
    latitude = valor_float(latitude)
    longitude = valor_float(longitude)

    return (
        latitude != 0
        and longitude != 0
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def distancia_km(latitude_origem, longitude_origem, latitude_destino, longitude_destino):
    lat1 = math.radians(valor_float(latitude_origem))
    lon1 = math.radians(valor_float(longitude_origem))
    lat2 = math.radians(valor_float(latitude_destino))
    lon2 = math.radians(valor_float(longitude_destino))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * RAIO_TERRA_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def interpolar_ponto(origem, destino, fracao):
    return {
        "Latitude": valor_float(origem.get("Latitude"))
        + (
            valor_float(destino.get("Latitude"))
            - valor_float(origem.get("Latitude"))
        )
        * fracao,
        "Longitude": valor_float(origem.get("Longitude"))
        + (
            valor_float(destino.get("Longitude"))
            - valor_float(origem.get("Longitude"))
        )
        * fracao
    }


def pontos_intermediarios(origem, destino, distancia_amostra_m=100):
    distancia_total_km = distancia_km(
        origem["Latitude"],
        origem["Longitude"],
        destino["Latitude"],
        destino["Longitude"]
    )
    distancia_amostra_m = max(valor_float(distancia_amostra_m, 100), 1)
    total = max(
        2,
        int(math.ceil((distancia_total_km * 1000) / distancia_amostra_m)) + 1
    )

    return [
        interpolar_ponto(
            origem,
            destino,
            indice / (total - 1)
        )
        for indice in range(total)
    ]


def curvatura_terra_m(distancia_origem_km, distancia_destino_km, fator_k=4 / 3):
    raio_efetivo_km = RAIO_TERRA_KM * fator_k
    return distancia_origem_km * distancia_destino_km / (2 * raio_efetivo_km) * 1000


def raio_fresnel_m(distancia_origem_km, distancia_destino_km, frequencia_ghz):
    frequencia_ghz = max(valor_float(frequencia_ghz, 5.8), 0.1)
    distancia_total_km = distancia_origem_km + distancia_destino_km

    if distancia_total_km <= 0:
        return 0.0

    return 17.32 * math.sqrt(
        distancia_origem_km
        * distancia_destino_km
        / (
            frequencia_ghz
            * distancia_total_km
        )
    )


def altura_final_ponto(ponto):
    return valor_float(ponto.get("Altitude")) + valor_float(ponto.get("Altura"))


def montar_perfil_visada(
    origem,
    destino,
    elevacoes=None,
    frequencia_ghz=5.8,
    fresnel_minimo=0.60,
    distancia_amostra_m=100,
    fator_k=4 / 3
):
    if not coordenada_valida(origem.get("Latitude"), origem.get("Longitude")):
        return pd.DataFrame()

    if not coordenada_valida(destino.get("Latitude"), destino.get("Longitude")):
        return pd.DataFrame()

    pontos = pontos_intermediarios(
        origem,
        destino,
        distancia_amostra_m=distancia_amostra_m
    )
    elevacoes = list(elevacoes or [])
    distancia_total_km = distancia_km(
        origem["Latitude"],
        origem["Longitude"],
        destino["Latitude"],
        destino["Longitude"]
    )
    altura_origem = altura_final_ponto(origem)
    altura_destino = altura_final_ponto(destino)
    registros = []

    for indice, ponto in enumerate(pontos):
        fracao = indice / (len(pontos) - 1) if len(pontos) > 1 else 0
        distancia_origem_km = distancia_total_km * fracao
        distancia_destino_km = max(distancia_total_km - distancia_origem_km, 0)
        altitude_terreno = (
            valor_float(elevacoes[indice])
            if indice < len(elevacoes)
            else 0.0
        )
        curvatura = curvatura_terra_m(
            distancia_origem_km,
            distancia_destino_km,
            fator_k=fator_k
        )
        linha_visada = altura_origem + (altura_destino - altura_origem) * fracao
        fresnel = raio_fresnel_m(
            distancia_origem_km,
            distancia_destino_km,
            frequencia_ghz
        )
        fresnel_exigido = fresnel * valor_float(fresnel_minimo, 0.60)
        obstaculo = altitude_terreno + curvatura
        margem = linha_visada - obstaculo - fresnel_exigido

        registros.append({
            "Ponto": indice + 1,
            "Latitude": ponto["Latitude"],
            "Longitude": ponto["Longitude"],
            "Distância km": distancia_origem_km,
            "Altitude Terreno m": altitude_terreno,
            "Curvatura Terra m": curvatura,
            "Linha Visada m": linha_visada,
            "Fresnel 1 m": fresnel,
            "Fresnel Exigido m": fresnel_exigido,
            "Margem m": margem
        })

    return pd.DataFrame(registros)


def classificar_visada(perfil, estimado=True):
    if perfil is None or perfil.empty:
        return "Dados insuficientes"

    menor_margem = float(perfil["Margem m"].min())

    if menor_margem < 0:
        return "Obstruída"

    if menor_margem <= 3:
        return "Parcial"

    return "Livre estimada" if estimado else "Livre"


def analisar_visada(
    origem,
    destino,
    elevacoes=None,
    estimado=True,
    frequencia_ghz=5.8,
    fresnel_minimo=0.60,
    distancia_amostra_m=100
):
    perfil = montar_perfil_visada(
        origem,
        destino,
        elevacoes=elevacoes,
        frequencia_ghz=frequencia_ghz,
        fresnel_minimo=fresnel_minimo,
        distancia_amostra_m=distancia_amostra_m
    )

    if perfil.empty:
        return {
            "Status": "Dados insuficientes",
            "Distância km": 0.0,
            "Menor margem m": 0.0,
            "Ponto crítico": {},
            "Estimado": True,
            "Perfil": perfil
        }

    ponto_critico = perfil.sort_values("Margem m").iloc[0].to_dict()

    return {
        "Status": classificar_visada(
            perfil,
            estimado=estimado
        ),
        "Distância km": float(perfil["Distância km"].max()),
        "Menor margem m": float(ponto_critico.get("Margem m") or 0),
        "Ponto crítico": ponto_critico,
        "Estimado": bool(estimado),
        "Perfil": perfil
    }
