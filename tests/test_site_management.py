import unittest

import pandas as pd

from app.ui.views.site_management import opcoes_cadastradas_site


class SiteManagementTest(unittest.TestCase):

    def test_opcoes_cadastradas_site_mantem_vazio_primeiro(self):
        df = pd.DataFrame({
            "Status": [
                "Ativo",
                "Cancelado"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "Status",
            "",
            extras=[
                "Ativo"
            ]
        )

        self.assertEqual(
            opcoes[0],
            ""
        )
        self.assertEqual(
            opcoes.count("Ativo"),
            1
        )

    def test_opcoes_cadastradas_site_inclui_extras_e_valor_atual(self):
        df = pd.DataFrame({
            "Relacionamento": [
                "Restrito",
                "Sem histórico"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "Relacionamento",
            "Valor novo",
            extras=[
                "Sem histórico"
            ]
        )

        self.assertIn(
            "Sem histórico",
            opcoes
        )
        self.assertIn(
            "Valor novo",
            opcoes
        )
        self.assertEqual(
            opcoes[0],
            ""
        )

    def test_opcoes_cadastradas_site_tipo_inclui_cliente(self):
        df = pd.DataFrame({
            "TIPO": [
                "POP",
                "BH"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "TIPO",
            "",
            extras=[
                "Cliente",
                "POP",
                "BH",
                "REP",
                "DC",
                "SITE"
            ]
        )

        self.assertIn(
            "Cliente",
            opcoes
        )
        self.assertEqual(
            opcoes[0],
            ""
        )


if __name__ == "__main__":
    unittest.main()
