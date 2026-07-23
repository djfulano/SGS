import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from app.ui.components.site_selector import SITE_SEARCH_PLACEHOLDER
from app.ui.components.site_selector import rotulo_busca_site
from app.ui.components.site_selector import selecionar_site_pesquisavel


class SiteSelectorTest(unittest.TestCase):

    def test_rotulo_dataframe_contem_todos_os_campos_pesquisaveis(self):
        registro = pd.Series({
            "Site SNMPc": "POP_A_100_IP",
            "Codigo": 100.0,
            "Nome Cadastro": "Site Alfa",
            "Microsiga": 200.0,
        })

        self.assertEqual(
            rotulo_busca_site(registro),
            "POP_A_100_IP - 100 / Site Alfa - 200",
        )

    def test_rotulo_aceita_registro_financeiro(self):
        registro = {
            "nome": "POP_B_101_IP",
            "codigo_topos": "101",
            "nome_cadastro": "Site Beta",
            "microsiga": "000201",
        }

        self.assertEqual(
            rotulo_busca_site(registro),
            "POP_B_101_IP - 101 / Site Beta - 000201",
        )

    def test_rotulo_aceita_objeto_site(self):
        site = SimpleNamespace(
            nome="POP_C_102_IP",
            codigo_topos="102",
            nome_cadastro="Site Gama",
            microsiga="000202",
        )

        self.assertEqual(
            rotulo_busca_site(site),
            "POP_C_102_IP - 102 / Site Gama - 000202",
        )

    def test_seletor_nao_escolhe_primeiro_site_automaticamente(self):
        with patch(
            "app.ui.components.site_selector.st.selectbox",
            return_value=None,
        ) as selectbox:
            resultado = selecionar_site_pesquisavel(
                ["POP_A"],
                {"POP_A": "POP_A - 100 / Site A - 200"},
                key="teste_site",
            )

        self.assertIsNone(resultado)
        argumentos = selectbox.call_args
        self.assertEqual(argumentos.kwargs["index"], None)
        self.assertEqual(
            argumentos.kwargs["placeholder"],
            SITE_SEARCH_PLACEHOLDER,
        )
        self.assertEqual(
            argumentos.kwargs["format_func"]("POP_A"),
            "POP_A - 100 / Site A - 200",
        )


if __name__ == "__main__":
    unittest.main()
