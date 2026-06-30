import unittest

import pandas as pd

from app.ui.views.tools import aplicar_filtros_equipamentos
from app.ui.views.tools import filtrar_enlaces_clientes_cancelados
from app.ui.views.tools import filtrar_equipamentos_cancelados
from app.ui.views.tools import marcar_status_cliente_equipamentos
from app.ui.views.tools import montar_enlaces_cliente
from app.ui.views.tools import normalizar_selecao_filtro
from app.ui.views.tools import opcoes_filtro_equipamentos


class ToolsViewHelpersTest(unittest.TestCase):

    def test_status_cliente_equipamentos(self):
        df = pd.DataFrame([
            {
                "Assinatura": "",
                "Icone": "ROUTER"
            },
            {
                "Assinatura": "100",
                "Icone": "ONU"
            },
            {
                "Assinatura": "200",
                "Icone": "ONU"
            }
        ])

        marcado = marcar_status_cliente_equipamentos(
            df,
            {"100"}
        )

        self.assertEqual(
            marcado["Status Cliente"].tolist(),
            [
                "Infraestrutura",
                "Ativo",
                "Cancelado"
            ]
        )

    def test_filtro_enlaces_cancelados_remove_infraestrutura_e_sites(self):
        df_equipamentos = pd.DataFrame([
            {
                "Site": "SITE_A",
                "Setorial": "S1",
                "Icone": "RADIO",
                "Assinatura": "",
                "Cliente Estrutura": "",
                "Status Cliente": "Infraestrutura"
            },
            {
                "Site": "SITE_A",
                "Setorial": "S1",
                "Icone": "RADIO",
                "Assinatura": "100",
                "Cliente Estrutura": "Cliente Ativo",
                "Status Cliente": "Ativo"
            },
            {
                "Site": "SITE_A",
                "Setorial": "S1",
                "Icone": "RADIO",
                "Assinatura": "200",
                "Cliente Estrutura": "Cliente Cancelado",
                "Status Cliente": "Cancelado"
            }
        ])
        df_enlaces = montar_enlaces_cliente(
            df_equipamentos
        )
        df_outros = pd.DataFrame([
            {
                "Tipo Enlace": "Site Pai x Filho",
                "Status Cliente": "Infraestrutura",
                "Assinatura": ""
            },
            {
                "Tipo Enlace": "POP x POP",
                "Status Cliente": "Infraestrutura",
                "Assinatura": ""
            }
        ])
        df_filtrado = filtrar_enlaces_clientes_cancelados(
            pd.concat(
                [
                    df_enlaces,
                    df_outros
                ],
                ignore_index=True
            )
        )

        self.assertEqual(
            len(df_filtrado),
            1
        )
        self.assertEqual(
            df_filtrado.iloc[0]["Tipo Enlace"],
            "Site x Cliente"
        )
        self.assertEqual(
            df_filtrado.iloc[0]["Status Cliente"],
            "Cancelado"
        )
        self.assertEqual(
            df_filtrado.iloc[0]["Assinatura"],
            "200"
        )

    def test_filtro_equipamentos_cancelados(self):
        df = pd.DataFrame([
            {
                "Equipamento": "Infra",
                "Status Cliente": "Infraestrutura"
            },
            {
                "Equipamento": "Ativo",
                "Status Cliente": "Ativo"
            },
            {
                "Equipamento": "Cancelado",
                "Status Cliente": "Cancelado"
            }
        ])

        filtrado = filtrar_equipamentos_cancelados(
            df
        )

        self.assertEqual(
            filtrado["Equipamento"].tolist(),
            ["Cancelado"]
        )

    def test_opcoes_filtro_equipamentos_considera_outros_filtros(self):
        df = pd.DataFrame([
            {
                "Icone": "AP",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UAP",
                "Tipo Base": "WiFi"
            },
            {
                "Icone": "SW",
                "Fabricante Base": "Cisco",
                "Modelo Base": "Catalyst",
                "Tipo Base": "Switch"
            },
            {
                "Icone": "ONU",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UFiber",
                "Tipo Base": "Fibra"
            }
        ])

        opcoes = opcoes_filtro_equipamentos(
            df,
            "Modelo Base",
            {
                "Fabricante Base": ["Ubiquiti"]
            }
        )

        self.assertEqual(
            opcoes,
            [
                "UAP",
                "UFiber"
            ]
        )

    def test_opcoes_filtro_equipamentos_ignora_propria_coluna(self):
        df = pd.DataFrame([
            {
                "Icone": "AP",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UAP",
                "Tipo Base": "WiFi"
            },
            {
                "Icone": "ONU",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UFiber",
                "Tipo Base": "Fibra"
            }
        ])

        opcoes = opcoes_filtro_equipamentos(
            df,
            "Modelo Base",
            {
                "Fabricante Base": ["Ubiquiti"],
                "Modelo Base": ["UAP"]
            }
        )

        self.assertEqual(
            opcoes,
            [
                "UAP",
                "UFiber"
            ]
        )

    def test_aplicar_filtros_equipamentos_combina_filtros(self):
        df = pd.DataFrame([
            {
                "Icone": "AP",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UAP",
                "Tipo Base": "WiFi"
            },
            {
                "Icone": "ONU",
                "Fabricante Base": "Ubiquiti",
                "Modelo Base": "UFiber",
                "Tipo Base": "Fibra"
            },
            {
                "Icone": "SW",
                "Fabricante Base": "Cisco",
                "Modelo Base": "Catalyst",
                "Tipo Base": "Switch"
            }
        ])

        filtrado = aplicar_filtros_equipamentos(
            df,
            {
                "Fabricante Base": ["Ubiquiti"],
                "Tipo Base": ["Fibra"]
            }
        )

        self.assertEqual(
            filtrado["Icone"].tolist(),
            ["ONU"]
        )

    def test_normalizar_selecao_filtro_remove_invalidos(self):
        self.assertEqual(
            normalizar_selecao_filtro(
                [
                    "UAP",
                    "Invalido"
                ],
                [
                    "UAP",
                    "UFiber"
                ]
            ),
            ["UAP"]
        )


if __name__ == "__main__":
    unittest.main()
