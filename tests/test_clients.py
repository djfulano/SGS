import unittest
from unittest.mock import patch

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.services.clients import agrupar_clientes
from app.services.clients import equipamentos_cliente
from app.services.clients import filtrar_clientes
from app.services.clients import montar_base_clientes
from app.ui.views.clients import rotulo_cliente
from app.ui.views.clients import valor_resumo_cliente


class ClientsServiceTest(unittest.TestCase):

    def test_cliente_vinculado_aparece_com_site_e_setorial(self):
        site = Site("POP_A", "POP")
        site.codigo_topos = "100"
        site.microsiga = "900"
        site.nome_cadastro = "POP A"
        cliente = Cliente("Cliente A", 120, "123")
        cliente.produto = "NeoSoft 100"
        site.adicionar_cliente(cliente)

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_clientes(
                {"POP_A": site},
                [],
                clientes_base={}
            )

        self.assertEqual(df.loc[0, "Cliente"], "Cliente A")
        self.assertEqual(df.loc[0, "Site"], "POP_A")
        self.assertEqual(df.loc[0, "Setorial"], "Direto")
        self.assertEqual(df.loc[0, "Vínculo"], "Vinculado")

    def test_cliente_sem_vinculo_permanece_na_base(self):
        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_clientes(
                {},
                [],
                clientes_base={
                    "456": {
                        "Cliente": "Cliente Sem Vinculo",
                        "Receita": 80,
                        "Produto": "NeoTotal",
                        "Endereco": "Rua A"
                    }
                }
            )

        self.assertEqual(df.loc[0, "Vínculo"], "Sem vínculo")
        self.assertEqual(df.loc[0, "Assinatura"], "456")


    def test_cliente_vinculado_preserva_gerente_de_contas(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        cliente.produto = "NeoSoft 100"
        cliente.gerente_contas = "Maria Silva"
        site.adicionar_cliente(cliente)

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_clientes(
                {"POP_A": site},
                [],
                clientes_base={}
            )

        self.assertEqual(df.loc[0, "Gerente de contas"], "Maria Silva")

    def test_cliente_sem_vinculo_preserva_gerente_de_contas(self):
        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_clientes(
                {},
                [],
                clientes_base={
                    "456": {
                        "Cliente": "Cliente Sem Vinculo",
                        "Receita": 80,
                        "Produto": "NeoTotal",
                        "Gerente Contas": "Joao Souza",
                        "Endereco": "Rua A"
                    }
                }
            )

        self.assertEqual(df.loc[0, "Gerente de contas"], "Joao Souza")

    def test_busca_cliente_encontra_por_gerente_e_rotulo_usa_padrao_consulta(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente A",
                "Assinatura": "123",
                "Produto": "NeoSoft",
                "Gerente de contas": "Maria Silva",
                "Site": "POP_A"
            }
        ])

        filtrado = filtrar_clientes(df, "Maria")

        self.assertEqual(len(filtrado), 1)
        self.assertEqual(
            rotulo_cliente(filtrado.iloc[0].to_dict()),
            "Cliente A - 123 / NeoSoft - POP_A"
        )

    def test_valor_resumo_cliente_trata_vazio(self):
        self.assertEqual(
            valor_resumo_cliente({"Gerente de contas": ""}, "Gerente de contas"),
            "Não informado"
        )

    def test_cliente_com_equipamento_recebe_dados_enriquecidos(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        site.adicionar_cliente(cliente)
        equipamentos = [
            {
                "Assinatura": "123",
                "Icone": "AP",
                "Equipamento": "AP Cliente",
                "Status": "Ativo"
            }
        ]
        catalogo = pd.DataFrame([
            {
                "Ícone": "AP",
                "Nome": "Access Point",
                "Tipo": "WiFi",
                "Código": "EQ1",
                "Valor": 50
            }
        ])

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=catalogo
        ):
            df = montar_base_clientes(
                {"POP_A": site},
                equipamentos,
                clientes_base={}
            )
            df_equipamentos = equipamentos_cliente(
                "123",
                equipamentos
            )

        self.assertEqual(df.loc[0, "Qtd Equipamentos"], 1)
        self.assertEqual(df.loc[0, "Valor Equipamentos"], 50)
        self.assertEqual(df_equipamentos.loc[0, "Nome Equipamento"], "Access Point")

    def test_agregacao_por_produto_soma_receita(self):
        df = pd.DataFrame([
            {
                "Assinatura": "1",
                "Produto": "NeoSoft",
                "Receita": 100
            },
            {
                "Assinatura": "2",
                "Produto": "NeoSoft",
                "Receita": 150
            }
        ])

        agrupado = agrupar_clientes(
            df,
            "Produto"
        )

        self.assertEqual(agrupado.loc[0, "Clientes"], 2)
        self.assertEqual(agrupado.loc[0, "Receita"], 250)


if __name__ == "__main__":
    unittest.main()
