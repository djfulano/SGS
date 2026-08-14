import unittest

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.services.pre_sales import identificar_radio_principal
from app.services.pre_sales import formatar_quantidade_pre_venda
from app.services.pre_sales import listar_radios_infraestrutura_site
from app.services.pre_sales import montar_opcoes_sites_pre_venda
from app.services.pre_sales import montar_resumo_pre_venda
from app.ui.views.pre_sales import montar_texto_resumo_pre_venda


class PreSalesTest(unittest.TestCase):

    def test_resumo_considera_descendentes_sem_somar_vinculo_adicional(self):
        pai = Site("PAI_POP_100_IP", "POP")
        pai.status_cadastro = "Ativo"
        pai.custo = 100
        filho = Site("FILHO_BH_101_IP", "BH")
        filho.custo = 40
        pai.adicionar_filho(filho)

        cliente_pai = Cliente("Cliente Pai", 1000, "10000001")
        cliente_pai.produto = "Plano 100 Mbps"
        pai.adicionar_cliente(cliente_pai)
        cliente_filho = Cliente("Cliente Filho", 500, "10000002")
        cliente_filho.produto = "Plano 1 Gbps"
        filho.adicionar_cliente(cliente_filho)
        filho.adicionar_cliente_adicional(cliente_pai, setorial="FILHO_S1")

        catalogo_produtos = pd.DataFrame([
            {
                "Nome": "Plano 100 Mbps",
                "Tipo": "Telecom",
                "Velocidade": "100 Mbps",
            },
            {
                "Nome": "Plano 1 Gbps",
                "Tipo": "Telecom",
                "Velocidade": "1 Gbps",
            },
        ])
        resumo = montar_resumo_pre_venda(
            {
                "status_cadastro": "Ativo",
                "site_topologia": pai,
            },
            catalogo_produtos=catalogo_produtos,
            catalogo_equipamentos=pd.DataFrame(),
        )

        self.assertEqual(resumo["status"], "Ativo")
        self.assertEqual(resumo["sites_filhos"], 1)
        self.assertEqual(resumo["clientes_diretos"], 1)
        self.assertEqual(resumo["clientes_indiretos"], 1)
        self.assertEqual(resumo["clientes_total"], 2)
        self.assertEqual(resumo["receita_direta"], 1000)
        self.assertEqual(resumo["receita_indireta"], 500)
        self.assertEqual(resumo["receita_total"], 1500)
        self.assertEqual(resumo["custo_direto"], 100)
        self.assertEqual(resumo["custo_indireto"], 40)
        self.assertEqual(resumo["custo_total"], 140)
        self.assertEqual(resumo["maior_banda_mbps"], 1000)
        self.assertEqual(resumo["soma_banda_mbps"], 1100)
        self.assertEqual(resumo["produtos_100_mbps"], 2)

    def test_radio_principal_usa_enlace_com_pai_e_exclui_clientes(self):
        pai = Site("PAI_POP_100_IP", "POP")
        filho = Site("FILHO_BH_101_IP", "BH")
        pai.adicionar_filho(filho)
        pai.adicionar_site_setorial("PAI_S1", filho)
        filho.equipamentos = [
            {
                "Equipamento": "FILHO_BH-10.0.0.2",
                "Icone": "radio-principal.ico",
                "Setorial": "PAI_S1",
                "Assinatura": "",
            },
            {
                "Equipamento": "FILHO_S1-10.0.1.2",
                "Icone": "radio-setorial.ico",
                "Setorial": "FILHO_S1",
                "Assinatura": "",
            },
            {
                "Equipamento": "CLIENTE-10.0.1.3",
                "Icone": "radio-setorial.ico",
                "Setorial": "FILHO_S1",
                "Assinatura": "10000001",
            },
            {
                "Equipamento": "SWITCH-10.0.0.10",
                "Icone": "switch.ico",
                "Setorial": "Direto",
                "Assinatura": "",
            },
        ]
        catalogo = pd.DataFrame([
            {
                "Ícone": "radio-principal.ico",
                "Modelo": "PowerBeam 5AC",
                "Tipo": "Radio FA",
            },
            {
                "Ícone": "radio-setorial.ico",
                "Modelo": "",
                "Nome": "Rádio legado",
                "Tipo": "Rádio FE",
            },
            {
                "Ícone": "switch.ico",
                "Modelo": "Switch",
                "Tipo": "Switch",
            },
        ])

        radios = listar_radios_infraestrutura_site(filho, catalogo)

        self.assertEqual(len(radios), 2)
        self.assertEqual(radios[1]["nome"], "Rádio legado")
        self.assertEqual(
            identificar_radio_principal(filho, radios=radios),
            "PowerBeam 5AC",
        )
        self.assertEqual(
            identificar_radio_principal(pai, catalogo=catalogo),
            "Não localizado",
        )

    def test_site_existente_apenas_no_cadastro_permanece_disponivel(self):
        cadastro = pd.DataFrame([
            {
                "SMNPC": "CLIENTE_X_200_IP",
                "CÓDIGO AQUILES": "200",
                "NOME": "Cliente X",
                "CÓDIGO MICROSIGA": "900200",
                "Status": "Cancelado",
                "TIPO": "Cliente",
                "CONTRATO": "Antena",
                "QTDO": 2,
                "SITE CRÍTICO": "Sim",
                "TIPO CRITICIDADE": "Bloqueia",
                "RESTRIÇÃO": "SIM",
                "Detalhe": "Acesso somente acompanhado",
                "OBSERVAÇÃO:": "Agendar com antecedência",
                "LOCAÇÃO": "R$ 100,00",
                "ENERGIA": "20,00",
                "OUTROS": 5,
            }
        ])

        opcoes = montar_opcoes_sites_pre_venda({}, cadastro=cadastro)
        registro = next(iter(opcoes.values()))
        resumo = montar_resumo_pre_venda(registro)

        self.assertEqual(len(opcoes), 1)
        self.assertEqual(registro["tipo"], "Cliente")
        self.assertEqual(resumo["status"], "Cancelado")
        self.assertIsNone(resumo["site_pai"])
        self.assertEqual(resumo["tipo_contrato"], "Antena")
        self.assertEqual(resumo["quantidade"], 2)
        self.assertEqual(resumo["tipo_criticidade"], "Bloqueia")
        self.assertEqual(resumo["restricao"], "SIM")
        self.assertEqual(resumo["detalhe"], "Acesso somente acompanhado")
        self.assertEqual(resumo["observacao"], "Agendar com antecedência")
        self.assertEqual(resumo["clientes_total"], 0)
        self.assertEqual(resumo["custo_direto"], 125)
        self.assertEqual(resumo["custo_total"], 125)
        self.assertEqual(resumo["radio_principal"], "Não localizado")

    def test_site_pai_e_campos_vazios_sao_normalizados(self):
        pai = Site("PAI_POP_100_IP", "POP")
        pai.codigo_topos = "100"
        pai.nome_cadastro = "Site Pai"
        pai.microsiga = "900100"
        filho = Site("FILHO_BH_101_IP", "BH")
        pai.adicionar_filho(filho)

        resumo = montar_resumo_pre_venda(
            {
                "status_cadastro": "Ativo",
                "site_critico": True,
                "tipo_criticidade": "",
                "site_topologia": filho,
            },
            catalogo_produtos=pd.DataFrame(),
            catalogo_equipamentos=pd.DataFrame(),
        )

        self.assertEqual(resumo["site_pai"]["nome"], "PAI_POP_100_IP")
        self.assertEqual(resumo["site_pai"]["codigo_topos"], "100")
        self.assertEqual(resumo["tipo_criticidade"], "Crítico")
        self.assertEqual(resumo["tipo_contrato"], "Não informado")
        self.assertEqual(resumo["restricao"], "Não informado")
        self.assertEqual(resumo["detalhe"], "Não informado")
        self.assertEqual(resumo["observacao"], "Não informado")

    def test_quantidade_e_texto_copiado(self):
        self.assertEqual(formatar_quantidade_pre_venda(None), "Não informado")
        self.assertEqual(formatar_quantidade_pre_venda(0), "0")
        self.assertEqual(formatar_quantidade_pre_venda(3), "3")
        self.assertEqual(formatar_quantidade_pre_venda(2.5), "2,5")

        resumo = {
            "status": "Ativo",
            "tipo_contrato": "Mastro",
            "tipo_criticidade": "Não crítico",
            "restricao": "NÃO",
            "detalhe": "Detalhe operacional",
            "observacao": "Observação contratual",
            "clientes_total": 1,
            "sites_filhos": 0,
            "clientes_diretos": 1,
            "clientes_indiretos": 0,
            "produtos_100_mbps": 1,
            "radio_principal": "PowerBeam",
            "radios_instalados": 2,
        }
        valores = {
            "site_pai": "PAI - 100 / Site Pai - 900100",
            "quantidade": "2",
            "receita_total": "R$ 1.000,00",
            "receita_direta": "R$ 1.000,00",
            "receita_indireta": "R$ 0,00",
            "custo_direto": "R$ 100,00",
            "custo_indireto": "R$ 0,00",
            "custo_total": "R$ 100,00",
            "maior_banda": "100 Mbps",
            "soma_banda": "100 Mbps",
        }

        texto = montar_texto_resumo_pre_venda("FILHO", resumo, valores)

        self.assertIn("Site Pai\tPAI - 100 / Site Pai - 900100", texto)
        self.assertIn("Tipo de contrato\tMastro", texto)
        self.assertIn("Quantidade\t2", texto)
        self.assertIn("Tipo de Criticidade\tNão crítico", texto)
        self.assertIn("Restrição\tNÃO", texto)
        self.assertIn("Detalhe\tDetalhe operacional", texto)
        self.assertIn("Observação\tObservação contratual", texto)


if __name__ == "__main__":
    unittest.main()
