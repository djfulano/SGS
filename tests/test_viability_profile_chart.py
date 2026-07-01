import unittest

import pandas as pd

from app.ui.views.viability import montar_grafico_perfil_visada
from app.ui.views.viability import preparar_dados_grafico_visada
from app.ui.views.viability import escala_y_grafico_visada
from app.ui.views.viability import suavizar_serie_terreno


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
        self.assertIn("Terreno Suavizado m", dados.columns)
        self.assertIn("Fresnel Inferior m", dados.columns)
        self.assertIn("Fresnel Superior m", dados.columns)
        self.assertEqual(dados.loc[1, "Terreno Ajustado m"], 815.02)
        self.assertEqual(dados.loc[1, "Fresnel Inferior m"], 831.0)
        self.assertEqual(dados.loc[1, "Fresnel Superior m"], 839.0)

    def test_suavizacao_reduz_degrau_sem_alterar_serie_real(self):
        serie = pd.Series([
            800,
            800,
            850,
            800,
            800
        ])
        suavizada = suavizar_serie_terreno(serie)

        self.assertEqual(list(serie), [800, 800, 850, 800, 800])
        self.assertLess(suavizada.iloc[2], 850)
        self.assertGreater(suavizada.iloc[2], 800)

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

    def test_grafico_nao_preenche_terreno_ate_zero(self):
        fig = montar_grafico_perfil_visada(perfil_exemplo())
        terreno = next(
            trace
            for trace in fig.data
            if trace.name == "Terreno + curvatura"
        )
        base = next(
            trace
            for trace in fig.data
            if trace.name == "Base visual"
        )

        self.assertEqual(terreno.fill, "tonexty")
        self.assertGreater(min(base.y), 0)
        self.assertEqual(terreno.line.shape, "spline")
        self.assertEqual(list(terreno.y), list(preparar_dados_grafico_visada(
            perfil_exemplo()
        )["Terreno Suavizado m"]))

    def test_escala_y_foca_intervalo_util_do_perfil(self):
        dados = preparar_dados_grafico_visada(perfil_exemplo())
        y_min, y_max, base = escala_y_grafico_visada(dados)

        self.assertGreater(y_min, 0)
        self.assertLess(y_min, dados["Terreno Ajustado m"].min())
        self.assertGreater(y_max, dados["Fresnel Superior m"].max())
        self.assertEqual(base, y_min)

    def test_escala_y_tem_amplitude_minima(self):
        perfil = pd.DataFrame({
            "Distância km": [0.0, 1.0],
            "Altitude Terreno m": [800.0, 801.0],
            "Curvatura Terra m": [0.0, 0.0],
            "Linha Visada m": [805.0, 806.0],
            "Fresnel Exigido m": [0.0, 1.0],
            "Margem m": [5.0, 4.0]
        })
        dados = preparar_dados_grafico_visada(perfil)
        y_min, y_max, _base = escala_y_grafico_visada(dados)

        self.assertGreaterEqual(y_max - y_min, 40.0)

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
