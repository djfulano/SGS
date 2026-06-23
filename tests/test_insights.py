import unittest

import pandas as pd

from app.services.insights import agrupar_clientes
from app.services.insights import agrupar_sites
from app.services.insights import aplicar_filtro_status_sites
from app.services.insights import clientes_sem_equipamento
from app.services.insights import clientes_sem_vinculo
from app.services.insights import sites_deficitarios
from app.services.insights import sites_sem_clientes


class InsightsServiceTest(unittest.TestCase):

    def test_exclui_sites_cancelados_por_padrao(self):
        df = pd.DataFrame([
            {
                "Site SNMPc": "SITE_ATIVO",
                "Status Cadastro": "Ativo"
            },
            {
                "Site SNMPc": "SITE_CANCELADO",
                "Status Cadastro": "Cancelado"
            }
        ])

        filtrado = aplicar_filtro_status_sites(
            df,
            apenas_ativos=True
        )

        self.assertEqual(
            list(filtrado["Site SNMPc"]),
            ["SITE_ATIVO"]
        )

    def test_identifica_sites_deficitarios(self):
        df = pd.DataFrame([
            {
                "Site SNMPc": "SITE_OK",
                "Resultado": 100
            },
            {
                "Site SNMPc": "SITE_RUIM",
                "Resultado": -50
            }
        ])

        deficitarios = sites_deficitarios(df)

        self.assertEqual(
            list(deficitarios["Site SNMPc"]),
            ["SITE_RUIM"]
        )

    def test_identifica_sites_sem_clientes(self):
        df = pd.DataFrame([
            {
                "Site SNMPc": "SITE_A",
                "Clientes Total": 0,
                "Custo": 100
            },
            {
                "Site SNMPc": "SITE_B",
                "Clientes Total": 2,
                "Custo": 50
            }
        ])

        sem_clientes = sites_sem_clientes(df)

        self.assertEqual(
            list(sem_clientes["Site SNMPc"]),
            ["SITE_A"]
        )

    def test_clientes_sem_vinculo_e_sem_equipamento(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente A",
                "Assinatura": "1",
                "Vínculo": "Sem vínculo",
                "Qtd Equipamentos": 0
            },
            {
                "Cliente": "Cliente B",
                "Assinatura": "2",
                "Vínculo": "Vinculado",
                "Qtd Equipamentos": 1
            }
        ])

        self.assertEqual(
            len(clientes_sem_vinculo(df)),
            1
        )
        self.assertEqual(
            len(clientes_sem_equipamento(df)),
            1
        )

    def test_agregacoes_somam_receita_e_custo(self):
        df_sites = pd.DataFrame([
            {
                "Cidade": "BH",
                "Site SNMPc": "S1",
                "Clientes Total": 2,
                "Receita Total": 300,
                "Custo": 100,
                "Resultado": 200
            },
            {
                "Cidade": "BH",
                "Site SNMPc": "S2",
                "Clientes Total": 1,
                "Receita Total": 100,
                "Custo": 120,
                "Resultado": -20
            }
        ])
        df_clientes = pd.DataFrame([
            {
                "Produto": "Internet",
                "Assinatura": "1",
                "Receita": 100,
                "Site": "S1"
            },
            {
                "Produto": "Internet",
                "Assinatura": "2",
                "Receita": 150,
                "Site": "S2"
            }
        ])

        sites = agrupar_sites(
            df_sites,
            "Cidade"
        )
        clientes = agrupar_clientes(
            df_clientes,
            "Produto"
        )

        self.assertEqual(
            sites.loc[0, "Receita"],
            400
        )
        self.assertEqual(
            sites.loc[0, "Custo"],
            220
        )
        self.assertEqual(
            clientes.loc[0, "Clientes"],
            2
        )
        self.assertEqual(
            clientes.loc[0, "Receita"],
            250
        )


if __name__ == "__main__":
    unittest.main()
