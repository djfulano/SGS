import unittest

import pandas as pd

from app.services.line_of_sight import analisar_visada
from app.services.line_of_sight import montar_perfil_visada


class LineOfSightTest(unittest.TestCase):

    def ponto(self, latitude, longitude, altitude=0, altura=0):
        return {
            "Latitude": latitude,
            "Longitude": longitude,
            "Altitude": altitude,
            "Altura": altura
        }

    def test_visada_livre_sem_obstaculo(self):
        origem = self.ponto(-23.0, -46.0, altitude=800, altura=30)
        destino = self.ponto(-23.01, -46.01, altitude=800, altura=30)

        analise = analisar_visada(
            origem,
            destino,
            elevacoes=[800, 800],
            estimado=False,
            distancia_amostra_m=2000
        )

        self.assertEqual(
            analise["Status"],
            "Livre"
        )

    def test_visada_obstruida_por_relevo(self):
        origem = self.ponto(-23.0, -46.0, altitude=800, altura=10)
        destino = self.ponto(-23.02, -46.02, altitude=800, altura=10)

        perfil = montar_perfil_visada(
            origem,
            destino,
            elevacoes=[800, 900, 800],
            distancia_amostra_m=1500
        )
        analise = analisar_visada(
            origem,
            destino,
            elevacoes=perfil["Altitude Terreno m"].tolist(),
            estimado=False,
            distancia_amostra_m=1500
        )

        self.assertEqual(
            analise["Status"],
            "Obstruída"
        )

    def test_dados_insuficientes_sem_coordenada(self):
        analise = analisar_visada(
            self.ponto(0, 0),
            self.ponto(-23.0, -46.0)
        )

        self.assertEqual(
            analise["Status"],
            "Dados insuficientes"
        )


if __name__ == "__main__":
    unittest.main()
