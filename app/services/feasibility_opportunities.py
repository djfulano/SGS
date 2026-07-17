from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.services.feasibility_history import FEASIBILITY_HISTORY_DIR
from app.services.map_service import carregar_cache_geocoding
from app.services.map_service import chave_geocoding
from app.services.map_service import geocodificar_endereco
from app.services.map_service import salvar_cache_geocoding
from app.services.site_registry_service import site_pode_atender_outros_enderecos
from app.storage import read_json
from app.storage import write_json_atomic


GEOCODING_FILE = FEASIBILITY_HISTORY_DIR / "geocoding.json"
GEOCODING_VERSION = 1

STATUS_PENDING = "Pendente"
STATUS_LOCATED = "Localizado"
STATUS_NOT_FOUND = "Não localizado"
STATUS_ERROR = "Erro"


def normalize_address(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).casefold()


def address_key(value):
    normalized = normalize_address(value)
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def load_geocoding(path=None):
    data = read_json(path or GEOCODING_FILE, {})
    if not isinstance(data, dict):
        data = {}
    if "registros" not in data:
        data = {"versao": GEOCODING_VERSION, "registros": {}}
    data.setdefault("versao", GEOCODING_VERSION)
    data.setdefault("registros", {})
    return data


def save_geocoding(data, path=None):
    write_json_atomic(path or GEOCODING_FILE, data)


def synchronize_addresses(records, data=None, path=None, persist=True):
    data = data or load_geocoding(path)
    entries = data.setdefault("registros", {})
    added = 0
    for record in records or []:
        address = str(record.get("Endereço Completo") or "").strip()
        key = address_key(address)
        if not key or key in entries:
            continue
        entries[key] = {
            "Endereço": address,
            "Latitude": 0.0,
            "Longitude": 0.0,
            "Provedor": "",
            "Status": STATUS_PENDING,
            "Geocodificado em": "",
            "Tentativas": 0,
            "Erro": "",
        }
        added += 1
    if persist and added:
        save_geocoding(data, path)
    return data, added


def geocoding_coverage(records, data=None):
    data = data or load_geocoding()
    entries = data.get("registros", {})
    unique_keys = {
        address_key(record.get("Endereço Completo"))
        for record in records or []
        if address_key(record.get("Endereço Completo"))
    }
    counts = {
        STATUS_PENDING: 0,
        STATUS_LOCATED: 0,
        STATUS_NOT_FOUND: 0,
        STATUS_ERROR: 0,
    }
    for key in unique_keys:
        status = (entries.get(key) or {}).get("Status", STATUS_PENDING)
        counts[status if status in counts else STATUS_PENDING] += 1
    return {
        "Total": len(unique_keys),
        **counts,
        "Cobertura %": (
            (counts[STATUS_LOCATED] / len(unique_keys) * 100)
            if unique_keys else 0.0
        ),
    }


def reset_geocoding_statuses(statuses, path=None):
    data = load_geocoding(path)
    changed = 0
    for entry in data.get("registros", {}).values():
        if entry.get("Status") in set(statuses or []):
            entry["Status"] = STATUS_PENDING
            changed += 1
    if changed:
        save_geocoding(data, path)
    return changed


def process_geocoding_batch(
    records,
    limit=500,
    retry_statuses=None,
    path=None,
    geocode=None,
    persist_every=100,
    progress_callback=None,
):
    data, _added = synchronize_addresses(records, path=path, persist=True)
    entries = data["registros"]
    statuses = {STATUS_PENDING}
    statuses.update(retry_statuses or [])
    pending = [
        (key, entry)
        for key, entry in entries.items()
        if entry.get("Status", STATUS_PENDING) in statuses
    ][:max(1, int(limit))]
    shared_cache = carregar_cache_geocoding()
    geocode = geocode or geocodificar_endereco
    processed = located = not_found = errors = 0

    for index, (key, entry) in enumerate(pending, start=1):
        address = entry.get("Endereço", "")
        if entry.get("Status") in {STATUS_NOT_FOUND, STATUS_ERROR}:
            shared_cache.pop(chave_geocoding(address), None)
        entry["Tentativas"] = int(entry.get("Tentativas") or 0) + 1
        entry["Geocodificado em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry["Erro"] = ""
        try:
            point = geocode(address, shared_cache)
            if point:
                entry.update({
                    "Latitude": float(point["lat"]),
                    "Longitude": float(point["lon"]),
                    "Provedor": str(point.get("provider") or ""),
                    "Status": STATUS_LOCATED,
                })
                located += 1
            else:
                entry.update({
                    "Latitude": 0.0,
                    "Longitude": 0.0,
                    "Status": STATUS_NOT_FOUND,
                })
                not_found += 1
        except Exception as error:
            entry.update({
                "Latitude": 0.0,
                "Longitude": 0.0,
                "Status": STATUS_ERROR,
                "Erro": str(error),
            })
            errors += 1
        processed += 1
        if index % max(1, int(persist_every)) == 0:
            save_geocoding(data, path)
            salvar_cache_geocoding(shared_cache)
        if progress_callback:
            progress_callback(index, len(pending), entry)

    save_geocoding(data, path)
    salvar_cache_geocoding(shared_cache)
    return {
        "Processados": processed,
        "Localizados": located,
        "Não localizados": not_found,
        "Erros": errors,
        "Restantes": max(0, len([
            entry for entry in entries.values()
            if entry.get("Status", STATUS_PENDING) == STATUS_PENDING
        ])),
    }


def eligible_sites(sites):
    result = []
    for site in (sites or {}).values():
        status = str(getattr(site, "status_cadastro", "") or "").strip().casefold()
        if status != "ativo" or not site_pode_atender_outros_enderecos(site):
            continue
        latitude = float(getattr(site, "latitude", 0) or 0)
        longitude = float(getattr(site, "longitude", 0) or 0)
        if latitude == 0 or longitude == 0:
            continue
        result.append(site)
    return sorted(result, key=lambda site: (
        str(getattr(site, "nome_cadastro", "") or "").casefold(),
        str(getattr(site, "nome", "") or "").casefold(),
    ))


def enrich_with_geocoding(df, data=None):
    result = df.copy()
    data = data or load_geocoding()
    entries = data.get("registros", {})
    keys = result.get("Endereço Completo", pd.Series(index=result.index, dtype=str)).map(
        address_key
    )
    result["Chave Geocodificação"] = keys
    for column, source, default in [
        ("Latitude Viabilidade", "Latitude", 0.0),
        ("Longitude Viabilidade", "Longitude", 0.0),
        ("Status Geocodificação", "Status", STATUS_PENDING),
    ]:
        result[column] = keys.map(
            lambda key: (entries.get(key) or {}).get(source, default)
        )
    return result


def _haversine_distances(latitude, longitude, target_latitude, target_longitude):
    earth_radius_km = 6371.0088
    latitudes = np.radians(pd.to_numeric(latitude, errors="coerce").to_numpy(dtype=float))
    longitudes = np.radians(pd.to_numeric(longitude, errors="coerce").to_numpy(dtype=float))
    target_lat = math.radians(float(target_latitude))
    target_lon = math.radians(float(target_longitude))
    delta_lat = latitudes - target_lat
    delta_lon = longitudes - target_lon
    value = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(target_lat) * np.cos(latitudes) * np.sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * np.arctan2(np.sqrt(value), np.sqrt(1 - value))


def opportunities_for_site(df, site, radius_km=5.0, data=None):
    enriched = enrich_with_geocoding(df, data=data)
    located = enriched[
        enriched["Status Geocodificação"].eq(STATUS_LOCATED)
    ].copy()
    if located.empty:
        return located
    located["Distância km"] = _haversine_distances(
        located["Latitude Viabilidade"],
        located["Longitude Viabilidade"],
        getattr(site, "latitude", 0),
        getattr(site, "longitude", 0),
    )
    located = located[located["Distância km"] <= float(radius_km)].copy()
    site_name = str(getattr(site, "nome", "") or "")
    pattern = rf"(?:^|;)\s*{re.escape(site_name)}\s*(?:;|$)"
    already_listed = located.get(
        "Sites localizados", pd.Series(index=located.index, dtype=str)
    ).fillna("").astype(str).str.contains(pattern, case=False, regex=True, na=False)
    located["Origem da oportunidade"] = np.where(
        already_listed,
        "Já indicado",
        "Somente proximidade",
    )
    located["Faixa de distância"] = pd.cut(
        located["Distância km"],
        bins=[-0.001, 2, 5, 10, 30],
        labels=["0-2 km", "2-5 km", "5-10 km", "10-30 km"],
        include_lowest=True,
    ).astype(str)
    return located.sort_values(["Distância km", "Data Início", "Projeto"])


def opportunity_summary(df):
    classifications = df.get("Classificação", pd.Series(index=df.index, dtype=str))
    origins = df.get("Origem da oportunidade", pd.Series(index=df.index, dtype=str))
    return {
        "Solicitações": len(df),
        "Projetos distintos": int(df["Projeto"].nunique()) if "Projeto" in df else 0,
        "Já indicadas": int(origins.eq("Já indicado").sum()),
        "Somente proximidade": int(origins.eq("Somente proximidade").sum()),
        "Viáveis diretas": int(classifications.eq("Viável direto").sum()),
        "Condicionais": int(classifications.eq("Viável condicional").sum()),
        "Não viáveis": int(classifications.eq("Não viável").sum()),
        "Pendentes": int(classifications.eq("Pendente").sum()),
    }


def aggregate_map_points(df):
    columns = [
        "Latitude",
        "Longitude",
        "Endereço",
        "Distância km",
        "Solicitações",
        "Viáveis diretas",
        "Condicionais",
        "Não viáveis",
        "Pendentes",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    source = df.copy()
    source["Endereço"] = source["Endereço Completo"].fillna("").astype(str)
    source["Latitude"] = pd.to_numeric(source["Latitude Viabilidade"], errors="coerce")
    source["Longitude"] = pd.to_numeric(source["Longitude Viabilidade"], errors="coerce")
    grouped = source.groupby(
        ["Latitude", "Longitude", "Endereço"], as_index=False
    ).agg(**{
        "Distância km": ("Distância km", "min"),
        "Solicitações": ("Projeto", "size"),
    })
    for classification, column in [
        ("Viável direto", "Viáveis diretas"),
        ("Viável condicional", "Condicionais"),
        ("Não viável", "Não viáveis"),
        ("Pendente", "Pendentes"),
    ]:
        counts = source[source["Classificação"].eq(classification)].groupby(
            ["Latitude", "Longitude", "Endereço"]
        ).size().rename(column).reset_index()
        grouped = grouped.merge(
            counts,
            on=["Latitude", "Longitude", "Endereço"],
            how="left",
        )
        grouped[column] = grouped[column].fillna(0).astype(int)
    return grouped[columns]
