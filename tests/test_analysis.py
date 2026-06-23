import unittest

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.ui.views.analysis import classificar_site_deficitario
from app.ui.views.analysis import extrair_sites_resumo_selecionados
from app.ui.views.analysis import montar_clientes_custos_receita
from app.ui.views.analysis import montar_sites_deficitarios
from app.ui.views.analysis import sugerir_acao_site_deficitario


class AnalysisCostsRevenueTest(unittest.TestCase):

    def test_monta_clientes_associados_aos_sites_filtrados(self):
        site_a = Site("POP_A", "POP")
        site_b = Site("BH_B", "BH")
        cliente_a = Cliente("Cliente A", 120.5, "123")
        cliente_a.produto = "Internet"
        cliente_a.endereco_completo = "Rua A"
        cliente_a.bairro = "Centro"
        cliente_a.cidade = "Belo Horizonte"
        site_a.adicionar_cliente(
            cliente_a,
            setorial="S1"
        )
        site_b.adicionar_cliente(
            Cliente("Cliente B", 80, "456")
        )

        df_clientes = montar_clientes_custos_receita(
            {
                "POP_A": site_a,
                "BH_B": site_b
            },
            [
                "POP_A"
            ]
        )

        self.assertEqual(
            len(df_clientes),
            1
        )
        registro = df_clientes.iloc[0].to_dict()
        self.assertEqual(
            registro["Site"],
            "POP_A"
        )
        self.assertEqual(
            registro["Cliente"],
            "Cliente A"
        )
        self.assertEqual(
            registro["Assinatura"],
            "123"
        )
        self.assertEqual(
            registro["Produto"],
            "Internet"
        )
        self.assertEqual(
            registro["Receita"],
            120.5
        )
        self.assertEqual(
            registro["Setorial"],
            "S1"
        )
        self.assertEqual(
            registro["Vínculo"],
            "Direto"
        )

    def test_monta_clientes_associados_inclui_filhos_quando_solicitado(self):
        site_pai = Site("POP_A", "POP")
        site_filho = Site("BH_A", "BH")
        site_pai.adicionar_cliente(
            Cliente("Cliente Pai", 100, "111")
        )
        site_filho.adicionar_cliente(
            Cliente("Cliente Filho", 50, "222")
        )
        site_pai.adicionar_filho(site_filho)

        df_clientes = montar_clientes_custos_receita(
            {
                "POP_A": site_pai,
                "BH_A": site_filho
            },
            [
                "POP_A"
            ],
            incluir_filhos=True
        )

        self.assertEqual(
            set(df_clientes["Cliente"]),
            {
                "Cliente Pai",
                "Cliente Filho"
            }
        )
        self.assertEqual(
            set(df_clientes["Site"]),
            {
                "POP_A",
                "BH_A"
            }
        )
        vinculos = dict(
            zip(
                df_clientes["Cliente"],
                df_clientes["Vínculo"]
            )
        )
        self.assertEqual(
            vinculos,
            {
                "Cliente Pai": "Direto",
                "Cliente Filho": "Indireto"
            }
        )

    def test_extrai_sites_marcados_no_resumo_para_novo_filtro(self):
        df_resumo = pd.DataFrame([
            {
                "Selecionar": True,
                "Site escolhido": "POP_A"
            },
            {
                "Selecionar": False,
                "Site escolhido": "BH_B"
            },
            {
                "Selecionar": True,
                "Site escolhido": "  REP_C  "
            }
        ])

        self.assertEqual(
            extrair_sites_resumo_selecionados(df_resumo),
            [
                "POP_A",
                "REP_C"
            ]
        )

    def test_monta_apenas_sites_deficitarios_ativos_no_snmpc_com_clientes(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "DEFICITARIO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 300,
                "Receita Com Filhos": 300,
                "Custo": 1000
            },
            {
                "Site SNMPc": "CANCELADO",
                "Status Cadastro": "Cancelado",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 100,
                "Custo": 1000
            },
            {
                "Site SNMPc": "FORA_SNMP",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Nao",
                "Clientes Total": 2,
                "Receita Total": 100,
                "Custo": 1000
            },
            {
                "Site SNMPc": "SEM_CLIENTE",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 0,
                "Receita Total": 0,
                "Custo": 1000
            },
            {
                "Site SNMPc": "POSITIVO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 1200,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(df_sites)

        self.assertEqual(
            list(df_deficitarios["Site SNMPc"]),
            [
                "DEFICITARIO"
            ]
        )
        registro = df_deficitarios.iloc[0]
        self.assertEqual(
            registro["Prejuízo Mensal"],
            700
        )
        self.assertEqual(
            registro["Prejuízo Anual"],
            8400
        )
        self.assertEqual(
            registro["Custo por Cliente"],
            500
        )
        self.assertEqual(
            registro["Ticket Médio"],
            150
        )
        self.assertEqual(
            registro["Receita para Equilíbrio"],
            1000
        )
        self.assertEqual(
            registro["Gap Receita"],
            700
        )
        self.assertEqual(
            registro["Clientes Necessários para Equilíbrio"],
            5
        )

    def test_classifica_e_sugere_acao_para_site_deficitario(self):
        self.assertEqual(
            classificar_site_deficitario(
                700,
                -0.5
            ),
            "Crítico"
        )
        self.assertEqual(
            sugerir_acao_site_deficitario(
                prejuizo_mensal=700,
                margem=-0.5,
                clientes_total=2,
                custo_por_cliente=500,
                ticket_medio=150
            ),
            "Avaliar cancelamento ou migração"
        )

    def test_receita_com_filhos_pode_ser_usada_na_analise(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "SITE_A",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 100,
                "Receita Com Filhos": 700,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            receita_coluna="Receita Com Filhos"
        )

        self.assertEqual(
            float(df_deficitarios.iloc[0]["Receita Considerada"]),
            700
        )
        self.assertEqual(
            float(df_deficitarios.iloc[0]["Prejuízo Mensal"]),
            300
        )

    def test_parametros_operacionais_podem_incluir_excecoes(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "CANCELADO",
                "Status Cadastro": "Cancelado",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 100,
                "Custo": 1000
            },
            {
                "Site SNMPc": "FORA_SNMP",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Nao",
                "Clientes Total": 2,
                "Receita Total": 100,
                "Custo": 1000
            },
            {
                "Site SNMPc": "SEM_CLIENTE",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 0,
                "Receita Total": 0,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            somente_ativos=False,
            somente_no_snmpc=False,
            somente_com_clientes=False
        )

        self.assertEqual(
            set(df_deficitarios["Site SNMPc"]),
            {
                "CANCELADO",
                "FORA_SNMP",
                "SEM_CLIENTE"
            }
        )
        sem_cliente = df_deficitarios[
            df_deficitarios["Site SNMPc"] == "SEM_CLIENTE"
        ].iloc[0]
        self.assertEqual(
            sem_cliente["Custo por Cliente"],
            0
        )
        self.assertEqual(
            sem_cliente["Ticket Médio"],
            0
        )
        self.assertEqual(
            sem_cliente["Clientes Necessários para Equilíbrio"],
            0
        )

    def test_criterios_financeiros_controlam_entrada_na_lista(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "PREJUIZO_BAIXO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 10,
                "Receita Total": 950,
                "Custo": 1000
            },
            {
                "Site SNMPc": "PREJUIZO_ALTO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 200,
                "Custo": 1000
            },
            {
                "Site SNMPc": "QUASE_ZERO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 5,
                "Receita Total": 1030,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            resultado_maximo=100,
            prejuizo_minimo=100,
            margem_maxima=0,
            custo_por_cliente_minimo=300,
            max_clientes=3,
            clientes_equilibrio_minimo=4
        )

        self.assertEqual(
            list(df_deficitarios["Site SNMPc"]),
            [
                "PREJUIZO_ALTO"
            ]
        )

    def test_prejuizo_minimo_negativo_cria_faixa_por_resultado(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "ABAIXO_DA_FAIXA",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 300,
                "Custo": 1000
            },
            {
                "Site SNMPc": "PREJUIZO_PEQUENO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 700,
                "Custo": 1000
            },
            {
                "Site SNMPc": "EQUILIBRADO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 1000,
                "Custo": 1000
            },
            {
                "Site SNMPc": "LUCRO_PEQUENO",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 1300,
                "Custo": 1000
            },
            {
                "Site SNMPc": "ACIMA_DA_FAIXA",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 2,
                "Receita Total": 1700,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            resultado_maximo=500,
            prejuizo_minimo=-500,
            margem_maxima=1
        )

        self.assertEqual(
            list(df_deficitarios["Site SNMPc"]),
            [
                "PREJUIZO_PEQUENO",
                "EQUILIBRADO",
                "LUCRO_PEQUENO"
            ]
        )
        lucro_pequeno = df_deficitarios[
            df_deficitarios["Site SNMPc"] == "LUCRO_PEQUENO"
        ].iloc[0]
        self.assertEqual(
            lucro_pequeno["Resultado"],
            300
        )
        self.assertEqual(
            lucro_pequeno["Prejuízo Mensal"],
            0
        )

    def test_sites_positivos_com_baixa_margem_podem_entrar_na_analise(self):
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "POSITIVO_BAIXA_MARGEM",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 4,
                "Receita Total": 1050,
                "Custo": 1000
            },
            {
                "Site SNMPc": "POSITIVO_MARGEM_ALTA",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 4,
                "Receita Total": 1500,
                "Custo": 1000
            },
            {
                "Site SNMPc": "DEFICITARIO_FORA_FAIXA",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 4,
                "Receita Total": 200,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            resultado_minimo=-100,
            resultado_maximo=200,
            margem_maxima=0.10
        )

        self.assertEqual(
            list(df_deficitarios["Site SNMPc"]),
            [
                "POSITIVO_BAIXA_MARGEM"
            ]
        )
        registro = df_deficitarios.iloc[0]
        self.assertEqual(
            registro["Resultado"],
            50
        )
        self.assertAlmostEqual(
            registro["Margem %"],
            50 / 1050
        )
        self.assertEqual(
            registro["Prejuízo Mensal"],
            0
        )

    def test_sites_deficitarios_soma_filhos_por_padrao_quando_sites_informados(self):
        site_pai = Site("POP_A", "POP")
        site_pai.custo = 1000
        site_pai.adicionar_cliente(
            Cliente("Cliente Pai", 1200, "111")
        )
        site_filho = Site("BH_A", "BH")
        site_filho.custo = 500
        site_filho.adicionar_cliente(
            Cliente("Cliente Filho", 100, "222")
        )
        site_pai.adicionar_filho(site_filho)
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "POP_A",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 1,
                "Receita Total": 1200,
                "Receita Com Filhos": 1200,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            sites={
                "POP_A": site_pai,
                "BH_A": site_filho
            },
            resultado_maximo=0,
            margem_maxima=1
        )

        registro = df_deficitarios.iloc[0]
        self.assertEqual(
            registro["Site SNMPc"],
            "POP_A"
        )
        self.assertEqual(
            registro["Clientes Total"],
            2
        )
        self.assertEqual(
            registro["Receita Considerada"],
            1300
        )
        self.assertEqual(
            registro["Custo"],
            1500
        )
        self.assertEqual(
            registro["Resultado"],
            -200
        )
        self.assertEqual(
            registro["Custo por Cliente"],
            750
        )
        self.assertEqual(
            registro["Ticket Médio"],
            650
        )
        self.assertEqual(
            registro["Sites Filhos Considerados"],
            1
        )

    def test_sites_deficitarios_sem_filhos_mantem_calculo_individual(self):
        site_pai = Site("POP_A", "POP")
        site_pai.custo = 1000
        site_pai.adicionar_cliente(
            Cliente("Cliente Pai", 1200, "111")
        )
        site_filho = Site("BH_A", "BH")
        site_filho.custo = 500
        site_filho.adicionar_cliente(
            Cliente("Cliente Filho", 100, "222")
        )
        site_pai.adicionar_filho(site_filho)
        df_sites = pd.DataFrame([
            {
                "Site SNMPc": "POP_A",
                "Status Cadastro": "Ativo",
                "No SNMPc": "Sim",
                "Clientes Total": 1,
                "Receita Total": 1200,
                "Receita Com Filhos": 1300,
                "Custo": 1000
            }
        ])

        df_deficitarios = montar_sites_deficitarios(
            df_sites,
            sites={
                "POP_A": site_pai,
                "BH_A": site_filho
            },
            incluir_filhos=False,
            resultado_maximo=300,
            margem_maxima=1
        )

        registro = df_deficitarios.iloc[0]
        self.assertEqual(
            registro["Clientes Total"],
            1
        )
        self.assertEqual(
            registro["Receita Considerada"],
            1200
        )
        self.assertEqual(
            registro["Custo"],
            1000
        )
        self.assertEqual(
            registro["Resultado"],
            200
        )
        self.assertEqual(
            registro["Sites Filhos Considerados"],
            0
        )


if __name__ == "__main__":
    unittest.main()
