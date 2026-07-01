import unittest

import pandas as pd

from app.ui.views.viability import montar_grafico_perfil_visada
from app.ui.views.viability import preparar_dados_grafico_visada


def perfil_exemplo():
    return pd.DataFrame({
        "Distância km": [0.0, 0.5, 1.0],
        "Altitude Terreno m": [800.0, 815.0, 810.0],
        "Curvatura Terra m": [0.0, 0.02, 0.0],
        "Linha Visada m": [830.0, 835.0, 840.0],
        "Fresnel Exigido m": [0.0, 4.0, 0.0],
        "Margem m": [30.0, 15.98, 30.0]
    })


class ViabilityProfileChartTest(unittest.TestCase):

    def test_prepara_dados_grafico_preserva_metricas(self):
        dados = preparar_dados_grafico_visada(perfil_exemplo())

        self.assertIn("Terreno Ajustado m", dados.columns)
        self.assertIn("Fresnel Inferior m", dados.columns)
        self.assertIn("Fresnel Superior m", dados.columns)
        self.assertEqual(dados.loc[1, "Terreno Ajustado m"], 815.02)
        self.assertEqual(dados.loc[1, "Fresnel Inferior m"], 831.0)
        self.assertEqual(dados.loc[1, "Fresnel Superior m"], 839.0)

    def test_grafico_contem_tracos_principais(self):
        fig = montar_grafico_perfil_visada(
            perfil_exemplo(),
            site="SITE_TESTE",
            status="Livre"
        )
        nomes = {trace.name for trace in fig.data}

        self.assertIn("Terreno + curvatura", nomes)
        self.assertIn("Linha de visada", nomes)
        self.assertIn("Fresnel exigido", nomes)
        self.assertIn("Ponto crítico", nomes)

    def test_ponto_critico_usa_menor_margem(self):
        fig = montar_grafico_perfil_visada(perfil_exemplo())
        ponto_critico = next(
            trace
            for trace in fig.data
            if trace.name == "Ponto crítico"
        )

        self.assertEqual(list(ponto_critico.x), [0.5])
        self.assertEqual(list(ponto_critico.y), [815.02])

    def test_perfil_vazio_gera_figura_segura(self):
        fig = montar_grafico_perfil_visada(pd.DataFrame())

        self.assertEqual(len(fig.data), 0)
        self.assertEqual(fig.layout.title.text, "Perfil de visada indisponível")


if __name__ == "__main__":
    unittest.main()
