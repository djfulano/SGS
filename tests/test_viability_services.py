import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.client_viability import dados_cliente_viabilidade
from app.services.client_viability import salvar_dados_cliente_viabilidade
from app.services.elevation_service import elevacoes_pontos


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


if __name__ == "__main__":
    unittest.main()
