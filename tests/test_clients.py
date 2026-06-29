import unittest
from unittest.mock import patch

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.services.clients import agrupar_clientes
from app.services.clients import equipamentos_cliente
from app.services.clients import filtrar_clientes
from app.services.clients import filtrar_clientes_consulta
from app.services.clients import montar_base_consulta_clientes
from app.services.clients import montar_base_clientes
from app.ui.views.clients import preparar_busca_clientes
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

    def test_base_consulta_clientes_e_leve_e_mantem_setorial(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        cliente.produto = "NeoSoft 100"
        cliente.gerente_contas = "Maria Silva"
        site.adicionar_cliente(
            cliente,
            setorial="POP_S1"
        )
        equipamentos = [
            {
                "Assinatura": "123",
                "Icone": "AP",
                "Equipamento": "AP Cliente",
                "Endereco": "10.0.0.2"
            }
        ]

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                equipamentos,
                clientes_base={}
            )

        self.assertEqual(df.loc[0, "Setorial"], "POP_S1")
        self.assertEqual(df.loc[0, "Gerente de contas"], "Maria Silva")
        self.assertEqual(df.loc[0, "Site"], "POP_A")
        self.assertEqual(
            df.loc[0, "Equipamentos"],
            "Equipamento: AP | IP: 10.0.0.2"
        )
        self.assertNotIn("Site Completo", df.columns)
        self.assertNotIn("Tipo Produto", df.columns)

    def test_base_consulta_clientes_usa_nome_cadastrado_e_ip_do_equipamento(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        site.adicionar_cliente(cliente)
        equipamentos = [
            {
                "Assinatura": "123",
                "Icone": "AP",
                "Equipamento": "AP Cliente",
                "Endereco": "10.0.0.2"
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
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                equipamentos,
                clientes_base={}
            )

        self.assertEqual(
            df.loc[0, "Equipamentos"],
            "Equipamento: Access Point | IP: 10.0.0.2"
        )

    def test_base_consulta_clientes_sem_nome_cadastrado_usa_icone(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        site.adicionar_cliente(cliente)
        equipamentos = [
            {
                "Assinatura": "123",
                "Icone": "ONU",
                "Equipamento": "ONU Cliente",
                "Endereco": "10.0.0.3"
            }
        ]

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                equipamentos,
                clientes_base={}
            )

        self.assertEqual(
            df.loc[0, "Equipamentos"],
            "Equipamento: ONU | IP: 10.0.0.3"
        )

    def test_base_consulta_clientes_sem_ip_exibe_nao_informado(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        site.adicionar_cliente(cliente)
        equipamentos = [
            {
                "Assinatura": "123",
                "Icone": "ONU",
                "Equipamento": "ONU Cliente"
            }
        ]

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                equipamentos,
                clientes_base={}
            )

        self.assertEqual(
            df.loc[0, "Equipamentos"],
            "Equipamento: ONU | IP: Não informado"
        )

    def test_base_consulta_clientes_inclui_goto_snmpc(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("17 TABELIAO DE NOTAS DA CAPITAL", 120, "15503202")
        site.clientes_estrutura.append({
            "assinatura": "15503202",
            "nome": "17_TABELIAO_NOTAS_15503202"
        })
        site.adicionar_cliente(cliente)

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                [],
                clientes_base={}
            )

        self.assertEqual(
            df.loc[0, "GoTo SNMPc"],
            "17_TABELIAO_NOTAS_15503202"
        )

    def test_base_consulta_clientes_sem_goto_snmpc_retorna_vazio(self):
        site = Site("POP_A", "POP")
        cliente = Cliente("Cliente A", 120, "123")
        site.adicionar_cliente(cliente)

        with patch(
            "app.services.clients.load_equipment_catalog",
            return_value=pd.DataFrame()
        ):
            df = montar_base_consulta_clientes(
                {"POP_A": site},
                [],
                clientes_base={}
            )

        self.assertEqual(df.loc[0, "GoTo SNMPc"], "")

    def test_filtro_consulta_ignora_setorial_e_campos_pesados(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente A",
                "Assinatura": "123",
                "Produto": "NeoSoft",
                "Gerente de contas": "Maria Silva",
                "Site": "POP_A",
                "Setorial": "SETORIAL_BUSCA",
                "Site Completo": "SITE_COMPLETO_BUSCA",
                "Cidade": "CIDADE_BUSCA",
                "Endereço": "ENDERECO_BUSCA"
            }
        ])

        self.assertEqual(len(filtrar_clientes_consulta(df, "Maria")), 1)
        self.assertEqual(len(filtrar_clientes_consulta(df, "123")), 1)
        self.assertEqual(len(filtrar_clientes_consulta(df, "NeoSoft")), 1)
        self.assertEqual(len(filtrar_clientes_consulta(df, "POP_A")), 1)
        self.assertEqual(len(filtrar_clientes_consulta(df, "SETORIAL_BUSCA")), 0)
        self.assertEqual(len(filtrar_clientes_consulta(df, "SITE_COMPLETO_BUSCA")), 0)
        self.assertEqual(len(filtrar_clientes_consulta(df, "CIDADE_BUSCA")), 0)
        self.assertEqual(len(filtrar_clientes_consulta(df, "ENDERECO_BUSCA")), 0)

    def test_prepara_busca_clientes_precalcula_rotulos_e_registros(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente A",
                "Assinatura": "123",
                "Produto": "NeoSoft",
                "Site": "POP_A"
            }
        ])

        opcoes, rotulos, registros = preparar_busca_clientes(df)

        self.assertEqual(opcoes, ["", "123"])
        self.assertEqual(rotulos["123"], "Cliente A - 123 / NeoSoft - POP_A")
        self.assertEqual(registros["123"]["Cliente"], "Cliente A")

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
