import unittest
from unittest.mock import patch

import pandas as pd

from app.ui.components import tables


class TablesTest(unittest.TestCase):

    def tearDown(self):
        tables.configurar_componentes_tabela(
            lambda: True,
            lambda valor: valor,
            lambda _key, default: default,
            lambda _key, _value: None,
            lambda: True,
            lambda: True
        )

    def test_botao_copiar_usa_componente_html_quando_permitido(self):
        tables.configurar_componentes_tabela(
            lambda: True,
            lambda valor: valor,
            lambda _key, default: default,
            lambda _key, _value: None,
            lambda: True,
            lambda: True
        )

        with patch.object(tables.components, "html") as html:
            tables.mostrar_botao_copiar_texto(
                "A\tB\n1\t2\n",
                rotulo="Copiar tabela"
            )

        html.assert_called_once()
        argumentos = html.call_args.args[0]
        self.assertIn(
            "navigator.clipboard.writeText",
            argumentos
        )
        self.assertEqual(
            html.call_args.kwargs["height"],
            34
        )

    def test_botao_copiar_nao_renderiza_sem_permissao(self):
        tables.configurar_componentes_tabela(
            lambda: True,
            lambda valor: valor,
            lambda _key, default: default,
            lambda _key, _value: None,
            lambda: True,
            lambda: False
        )

        with patch.object(tables.components, "html") as html:
            tables.mostrar_botao_copiar_texto("texto")

        html.assert_not_called()

    def test_texto_para_copia_respeita_permissoes_de_valores(self):
        tables.configurar_componentes_tabela(
            lambda: False,
            lambda valor: f"R$ {valor:.2f}",
            lambda _key, default: default,
            lambda _key, _value: None,
            lambda: False,
            lambda: True
        )
        df = pd.DataFrame([
            {
                "Site": "POP_A",
                "Receita": 100.0,
                "Custo": 50.0
            }
        ])

        texto = tables.texto_dataframe_para_copia(df)

        self.assertEqual(
            texto,
            "Site\nPOP_A\n"
        )

    def test_texto_para_copia_formata_moeda_e_percentual(self):
        tables.configurar_componentes_tabela(
            lambda: True,
            lambda valor: f"R$ {valor:.2f}",
            lambda _key, default: default,
            lambda _key, _value: None,
            lambda: True,
            lambda: True
        )
        df = pd.DataFrame([
            {
                "Receita Considerada": 1000.0,
                "Custo": 900.0,
                "Resultado": 100.0,
                "Margem %": 0.10
            }
        ])

        texto = tables.texto_dataframe_para_copia(df)

        self.assertEqual(
            texto,
            "Receita Considerada\tCusto\tResultado\tMargem %\n"
            "R$ 1000.00\tR$ 900.00\tR$ 100.00\t10,0%\n"
        )

    def test_margem_e_percentual_nao_sao_colunas_monetarias(self):
        self.assertFalse(
            tables.eh_coluna_monetaria("Margem %")
        )
        self.assertTrue(
            tables.eh_coluna_percentual("Margem %")
        )


if __name__ == "__main__":
    unittest.main()
