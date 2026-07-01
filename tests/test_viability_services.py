import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.client_viability import dados_cliente_viabilidade
from app.services.client_viability import salvar_dados_cliente_viabilidade
from app.services.elevation_service import elevacoes_pontos
from app.ui.views.viability import analisar_ponto_para_site
from app.ui.views.viability import ponto_migracao_cliente


class ViabilityServicesTest(unittest.TestCase):

    def test_salva_e_carrega_dados_tecnicos_cliente(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "client_viability.json"

            salvar_dados_cliente_viabilidade(
                "123",
                latitude=-23.1,
                longitude=-46.1,
                altitude=800,
                altura=12,
                usuario="teste",
                path=path
            )
            dados = dados_cliente_viabilidade(
                "123",
                path=path
            )

        self.assertEqual(dados["latitude"], -23.1)
        self.assertEqual(dados["longitude"], -46.1)
        self.assertEqual(dados["altitude"], 800)
        self.assertEqual(dados["altura"], 12)
        self.assertEqual(dados["updated_by"], "teste")

    def test_elevacao_usa_cache_sem_chamar_provedor(self):
        pontos = [
            {
                "Latitude": -23.123456,
                "Longitude": -46.123456
            }
        ]
        cache = {
            "-23.12346,-46.12346": 801
        }

        with patch(
            "app.services.elevation_service.consultar_open_elevation"
        ) as consulta, patch(
            "app.services.elevation_service.salvar_cache_elevacao"
        ):
            elevacoes, estimado = elevacoes_pontos(
                pontos,
                config={
                    "elevation_provider": "open_elevation"
                },
                cache=cache
            )

        consulta.assert_not_called()
        self.assertFalse(estimado)
        self.assertEqual(elevacoes, [801.0])

    def test_ponto_migracao_zera_altitude_para_open_elevation(self):
        ponto = {
            "Latitude": -23.1,
            "Longitude": -46.1,
            "Altitude": 900,
            "Altura": 5
        }
        resultado = ponto_migracao_cliente(
            ponto,
            -23.2,
            -46.2,
            12
        )

        self.assertEqual(resultado["Latitude"], -23.2)
        self.assertEqual(resultado["Longitude"], -46.2)
        self.assertEqual(resultado["Altitude"], 0)
        self.assertEqual(resultado["Altura"], 12)

    def test_analise_preenche_altitude_origem_por_elevacao(self):
        origem = {
            "Latitude": -23.0,
            "Longitude": -46.0,
            "Altitude": 0,
            "Altura": 10
        }
        destino = {
            "Latitude": -23.01,
            "Longitude": -46.01,
            "Altitude": 0,
            "Altura": 20
        }

        with patch(
            "app.ui.views.viability.pontos_intermediarios",
            return_value=[
                {
                    "Latitude": -23.0,
                    "Longitude": -46.0
                },
                {
                    "Latitude": -23.01,
                    "Longitude": -46.01
                }
            ]
        ), patch(
            "app.ui.views.viability.elevacoes_pontos",
            return_value=([
                800,
                820
            ], False)
        ), patch(
            "app.ui.views.viability.carregar_cache_elevacao",
            return_value={}
        ):
            analise = analisar_ponto_para_site(
                origem,
                destino,
                {
                    "line_of_sight_sample_distance_m": 100,
                    "line_of_sight_frequency_ghz": 5.8,
                    "line_of_sight_fresnel_clearance": 0.60
                }
            )

        perfil = analise["Perfil"]
        self.assertEqual(perfil.iloc[0]["Linha Visada m"], 810)
        self.assertEqual(perfil.iloc[-1]["Linha Visada m"], 840)


if __name__ == "__main__":
    unittest.main()
