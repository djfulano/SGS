import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import requests

from app.services import feasibility_opportunities as fo


class FeasibilityOpportunitiesTest(unittest.TestCase):

    def test_batch_sizes_include_ten_thousand(self):
        self.assertEqual(fo.GEOCODING_BATCH_SIZES, (100, 500, 1000, 10000))

    def records(self):
        return [
            {"ID SGS": "1", "Endereço Completo": "Rua A, 10, São Paulo"},
            {"ID SGS": "2", "Endereço Completo": " Rua A, 10, Sao Paulo "},
            {"ID SGS": "3", "Endereço Completo": "Rua B, 20, São Paulo"},
        ]

    def site(self, **changes):
        data = {
            "nome": "AAA_POP_1_IP",
            "nome_cadastro": "Site Alfa",
            "status_cadastro": "Ativo",
            "tipo": "POP",
            "latitude": -23.0,
            "longitude": -46.0,
        }
        data.update(changes)
        return SimpleNamespace(**data)

    def test_synchronizes_unique_addresses_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geocoding.json"
            data, added = fo.synchronize_addresses(self.records(), path=path)
            self.assertEqual(added, 2)
            self.assertEqual(len(data["registros"]), 2)
            loaded = fo.load_geocoding(path)
            self.assertEqual(len(loaded["registros"]), 2)
            _data, added_again = fo.synchronize_addresses(self.records(), path=path)
            self.assertEqual(added_again, 0)

    def test_processes_each_unique_address_once_and_resumes(self):
        calls = []

        def geocode(address, cache):
            calls.append(address)
            return {"lat": -23.0, "lon": -46.0, "provider": "test"}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geocoding.json"
            with patch.object(fo, "carregar_cache_geocoding", return_value={}), patch.object(
                fo, "salvar_cache_geocoding"
            ):
                first = fo.process_geocoding_batch(
                    self.records(), limit=1, path=path, geocode=geocode
                )
                second = fo.process_geocoding_batch(
                    self.records(), limit=10, path=path, geocode=geocode
                )
            self.assertEqual(first["Processados"], 1)
            self.assertEqual(second["Processados"], 1)
            self.assertEqual(len(calls), 2)
            coverage = fo.geocoding_coverage(self.records(), fo.load_geocoding(path))
            self.assertEqual(coverage["Localizado"], 2)
            entries = fo.load_geocoding(path)["registros"].values()
            self.assertTrue(all(entry["Tentativas"] == 1 for entry in entries))

    def test_persists_not_found_and_error(self):
        outcomes = iter([None, RuntimeError("falha")])

        def geocode(_address, _cache):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geocoding.json"
            with patch.object(fo, "carregar_cache_geocoding", return_value={}), patch.object(
                fo, "salvar_cache_geocoding"
            ):
                result = fo.process_geocoding_batch(
                    self.records(), limit=10, path=path, geocode=geocode
                )
            self.assertEqual(result["Não localizados"], 1)
            self.assertEqual(result["Erros"], 1)
            statuses = {
                entry["Status"] for entry in fo.load_geocoding(path)["registros"].values()
            }
            self.assertEqual(statuses, {fo.STATUS_NOT_FOUND, fo.STATUS_ERROR})

    def test_interrupts_batch_and_keeps_pending_on_provider_error(self):
        def geocode(_address, _cache):
            response = requests.Response()
            response.status_code = 429
            raise requests.HTTPError("limite excedido", response=response)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geocoding.json"
            with patch.object(fo, "carregar_cache_geocoding", return_value={}), patch.object(
                fo, "salvar_cache_geocoding"
            ):
                result = fo.process_geocoding_batch(
                    self.records(), limit=10, path=path, geocode=geocode
                )
            self.assertTrue(result["Interrompido"])
            self.assertEqual(result["Processados"], 1)
            self.assertEqual(result["Restantes"], 2)
            statuses = {
                entry["Status"] for entry in fo.load_geocoding(path)["registros"].values()
            }
            self.assertEqual(statuses, {fo.STATUS_PENDING})

    def test_calculates_nearby_opportunities_and_origin(self):
        frame = pd.DataFrame([
            {
                "ID SGS": "1", "Projeto": "P1", "Data Início": "2026-01-01",
                "Endereço Completo": "Rua A", "Classificação": "Viável direto",
                "Sites localizados": "AAA_POP_1_IP", "Produtos": "Internet",
            },
            {
                "ID SGS": "2", "Projeto": "P2", "Data Início": "2026-01-02",
                "Endereço Completo": "Rua B", "Classificação": "Pendente",
                "Sites localizados": "BBB_POP_2_IP", "Produtos": "Internet",
            },
            {
                "ID SGS": "3", "Projeto": "P3", "Data Início": "2026-01-03",
                "Endereço Completo": "Rua C", "Classificação": "Não viável",
                "Sites localizados": "", "Produtos": "Internet",
            },
        ])
        data = {"versao": 1, "registros": {
            fo.address_key("Rua A"): {
                "Status": fo.STATUS_LOCATED, "Latitude": -23.0, "Longitude": -46.0
            },
            fo.address_key("Rua B"): {
                "Status": fo.STATUS_LOCATED, "Latitude": -23.01, "Longitude": -46.0
            },
            fo.address_key("Rua C"): {
                "Status": fo.STATUS_LOCATED, "Latitude": -24.0, "Longitude": -46.0
            },
        }}
        result = fo.opportunities_for_site(frame, self.site(), radius_km=5, data=data)
        self.assertEqual(result["ID SGS"].tolist(), ["1", "2"])
        origins = dict(zip(result["ID SGS"], result["Origem da oportunidade"]))
        self.assertEqual(origins["1"], "Já indicado")
        self.assertEqual(origins["2"], "Somente proximidade")
        summary = fo.opportunity_summary(result)
        self.assertEqual(summary["Solicitações"], 2)
        self.assertEqual(summary["Viáveis diretas"], 1)
        self.assertEqual(summary["Pendentes"], 1)

    def test_includes_original_site_without_coordinates(self):
        frame = pd.DataFrame([{
            "ID SGS": "1",
            "Projeto": "P1",
            "Data Início": "2026-01-01",
            "Endereço Completo": "Rua sem coordenada",
            "Classificação": "Viável direto",
            "Sites localizados": "AAA_POP_1_IP",
        }])
        data = {"versao": 1, "registros": {
            fo.address_key("Rua sem coordenada"): {
                "Status": fo.STATUS_PENDING,
                "Latitude": 0.0,
                "Longitude": 0.0,
            },
        }}
        result = fo.opportunities_for_site(frame, self.site(), radius_km=5, data=data)
        self.assertEqual(result["ID SGS"].tolist(), ["1"])
        self.assertEqual(result.iloc[0]["Origem da oportunidade"], "Já indicado")
        self.assertEqual(result.iloc[0]["Faixa de distância"], "Sem coordenada")
        self.assertTrue(pd.isna(result.iloc[0]["Distância km"]))

    def test_original_nearby_record_is_not_duplicated(self):
        frame = pd.DataFrame([{
            "ID SGS": "1",
            "Projeto": "P1",
            "Data Início": "2026-01-01",
            "Endereço Completo": "Rua A",
            "Classificação": "Viável direto",
            "Sites localizados": "AAA_POP_1_IP",
        }])
        data = {"versao": 1, "registros": {
            fo.address_key("Rua A"): {
                "Status": fo.STATUS_LOCATED,
                "Latitude": -23.0,
                "Longitude": -46.0,
            },
        }}
        result = fo.opportunities_for_site(frame, self.site(), radius_km=5, data=data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Origem da oportunidade"], "Já indicado")

    def test_aggregates_repeated_map_points(self):
        frame = pd.DataFrame([
            {
                "Projeto": "1", "Endereço Completo": "Rua A",
                "Latitude Viabilidade": -23.0, "Longitude Viabilidade": -46.0,
                "Distância km": 1.0, "Classificação": "Viável direto",
            },
            {
                "Projeto": "2", "Endereço Completo": "Rua A",
                "Latitude Viabilidade": -23.0, "Longitude Viabilidade": -46.0,
                "Distância km": 1.0, "Classificação": "Viável condicional",
            },
        ])
        grouped = fo.aggregate_map_points(frame)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(int(grouped.iloc[0]["Solicitações"]), 2)
        self.assertEqual(int(grouped.iloc[0]["Viáveis diretas"]), 1)
        self.assertEqual(int(grouped.iloc[0]["Condicionais"]), 1)

    def test_map_ignores_records_without_valid_coordinates(self):
        frame = pd.DataFrame([
            {
                "Projeto": "1", "Endereço Completo": "Rua A",
                "Latitude Viabilidade": -23.0, "Longitude Viabilidade": -46.0,
                "Status Geocodificação": fo.STATUS_LOCATED,
                "Distância km": 1.0, "Classificação": "Viável direto",
            },
            {
                "Projeto": "2", "Endereço Completo": "Rua B",
                "Latitude Viabilidade": 0.0, "Longitude Viabilidade": 0.0,
                "Status Geocodificação": fo.STATUS_PENDING,
                "Distância km": float("nan"), "Classificação": "Pendente",
            },
        ])
        grouped = fo.aggregate_map_points(frame)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped.iloc[0]["Endereço"], "Rua A")

    def test_eligible_sites_excludes_inactive_and_client_type(self):
        sites = {
            "active": self.site(),
            "inactive": self.site(nome="INATIVO", status_cadastro="Cancelado"),
            "client": self.site(nome="CLIENTE", tipo="Cliente"),
            "without_coordinates": self.site(nome="SEM_COORD", latitude=0),
        }
        self.assertEqual([site.nome for site in fo.eligible_sites(sites)], ["AAA_POP_1_IP"])


if __name__ == "__main__":
    unittest.main()
