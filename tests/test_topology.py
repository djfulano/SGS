import unittest
from unittest.mock import patch

import pandas as pd

import app.ui.views.topology as topology_view
from app.models.cliente import Cliente
from app.models.site import Site
from app.ui.views.topology import formatar_banda_mbps
from app.ui.views.topology import contar_sites_ativos_resumo
from app.ui.views.topology import montar_tabela_sites_usados
from app.ui.views.topology import montar_metricas_banda_telecom_site
from app.ui.views.topology import montar_metricas_banda_telecom_sites
from app.ui.views.topology import montar_resumo_sites
from app.ui.views.topology import montar_clientes_sites_usados
from app.ui.views.topology import normalizar_velocidade_mbps
from app.ui.views.topology import velocidade_telecom_produto_mbps
from app.ui.components.site_selector import rotulo_busca_site
from app.services.site_metrics import custo_indireto_site
from app.services.site_metrics import custo_site
from app.services.site_metrics import custo_total_site
from app.services.site_metrics import montar_escopo_sites
from app.services.site_metrics import montar_resumo_selecao_sites


class TopologyBandwidthTest(unittest.TestCase):

    def test_rotulo_busca_topologia_exibe_identificadores_do_site(self):
        site = Site("ALPES_D_ITALIA_BH_104708_IP", "BH")
        site.codigo_topos = "104708"
        site.nome_cadastro = "ALPES D' ITALIA"
        site.microsiga = "91687"

        self.assertEqual(
            rotulo_busca_site(site),
            "ALPES_D_ITALIA_BH_104708_IP - 104708 / "
            "ALPES D' ITALIA - 91687",
        )

    def test_cliente_adicional_aparece_sem_duplicar_financeiro(self):
        principal = Site("BEL_POP_1_IP", "POP")
        adicional = Site("FUV_POP_2_IP", "POP")
        cliente = Cliente("DAVO ITAQUERA", 900, "10986201")
        cliente.gerente_contas = "Maria Silva"
        principal.adicionar_cliente(cliente, setorial="BEL_S10")
        adicional.adicionar_cliente_adicional(cliente, setorial="FUV_S6")

        df = montar_clientes_sites_usados(
            {principal.nome: principal, adicional.nome: adicional},
            {principal.nome: principal, adicional.nome: adicional}
        )

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["Vínculo"]), {"Principal", "Adicional"})
        self.assertEqual(set(df["Gerente de Contas"]), {"Maria Silva"})
        self.assertEqual(principal.calcular_receita(), 900)
        self.assertEqual(adicional.calcular_receita(), 0)
        self.assertEqual(len(principal.clientes), 1)
        self.assertEqual(len(adicional.clientes), 0)

    def catalogo_vazio(self):
        return pd.DataFrame(
            columns=[
                "Nome",
                "Tipo",
                "Grupo",
                "Família",
                "Velocidade",
                "Variação"
            ]
        )

    def cliente_com_produto(self, assinatura, produto):
        cliente = Cliente(
            f"Cliente {assinatura}",
            100,
            assinatura
        )
        cliente.produto = produto
        return cliente

    def test_resumo_sites_inclui_custo(self):
        site = Site("POP_A", "POP")
        site.custo = 1234.56
        site.nome_cadastro = "POP A Cadastro"
        site.status_cadastro = "Ativo"

        df_resumo = montar_resumo_sites({
            "POP_A": site
        })

        self.assertEqual(
            df_resumo.loc[0, "Custo"],
            1234.56
        )
        self.assertEqual(
            df_resumo.loc[0, "Custo Direto"],
            1234.56
        )
        self.assertEqual(
            df_resumo.loc[0, "Custo Indireto"],
            0
        )
        self.assertEqual(
            df_resumo.loc[0, "Custo Total"],
            1234.56
        )
        self.assertEqual(
            df_resumo.loc[0, "Nome"],
            "POP A Cadastro"
        )
        self.assertEqual(
            df_resumo.loc[0, "Status Cadastro"],
            "Ativo"
        )

    def test_conta_apenas_sites_ativos_no_resumo_principal(self):
        df_resumo = pd.DataFrame([
            {"Site": "POP_A", "Status Cadastro": "Ativo"},
            {"Site": "POP_B", "Status Cadastro": " ativo "},
            {"Site": "POP_C", "Status Cadastro": "ATIVO"},
            {"Site": "POP_D", "Status Cadastro": "Cancelado"},
            {"Site": "POP_E", "Status Cadastro": ""},
            {"Site": "POP_F", "Status Cadastro": None}
        ])

        self.assertEqual(
            contar_sites_ativos_resumo(df_resumo),
            3
        )

    def test_conta_sites_ativos_sem_alterar_demais_metricas(self):
        ativo = Site("POP_ATIVO", "POP")
        ativo.status_cadastro = "Ativo"
        ativo.custo = 50
        ativo.adicionar_cliente(
            self.cliente_com_produto(
                "1001",
                "NeoSoft 100 Mbps"
            )
        )

        cancelado = Site("POP_CANCELADO", "POP")
        cancelado.status_cadastro = "Cancelado"
        cancelado.custo = 70
        cancelado.adicionar_cliente(
            self.cliente_com_produto(
                "1002",
                "NeoTotal 1 Gbps"
            )
        )

        df_resumo = montar_resumo_sites({
            "POP_ATIVO": ativo,
            "POP_CANCELADO": cancelado
        })

        self.assertEqual(
            contar_sites_ativos_resumo(df_resumo),
            1
        )
        self.assertEqual(
            df_resumo["Clientes Total"].sum(),
            2
        )
        self.assertEqual(
            df_resumo["Receita Total"].sum(),
            200
        )
        self.assertEqual(
            df_resumo["Custo"].sum(),
            120
        )

    def test_custos_direto_indireto_e_total_multinivel(self):
        pai = Site("POP_A", "POP")
        filho = Site("BH_A", "BH")
        neto = Site("REP_A", "REP")
        pai.custo = 100
        filho.custo = 40
        neto.custo = 10
        pai.adicionar_filho(filho)
        filho.adicionar_filho(neto)

        self.assertEqual(custo_site(pai), 100)
        self.assertEqual(custo_indireto_site(pai), 50)
        self.assertEqual(custo_total_site(pai), 150)

    def test_tabela_sites_usados_respeita_incluir_filhos(self):
        pai = Site("POP_A", "POP")
        filho = Site("BH_A", "BH")
        pai.custo = 100
        filho.custo = 40
        pai.adicionar_filho(filho)

        sem_filhos = montar_tabela_sites_usados(
            {pai.nome: pai},
            incluir_filhos=False
        ).iloc[0]
        com_filhos = montar_tabela_sites_usados(
            {pai.nome: pai, filho.nome: filho},
            incluir_filhos=True
        )
        linha_pai = com_filhos[
            com_filhos["Site"] == pai.nome
        ].iloc[0]

        self.assertEqual(sem_filhos["Custo Direto"], 100)
        self.assertEqual(sem_filhos["Custo Indireto"], 0)
        self.assertEqual(sem_filhos["Custo Total"], 100)
        self.assertEqual(linha_pai["Custo Indireto"], 40)
        self.assertEqual(linha_pai["Custo Total"], 140)

    def test_resumo_nao_duplica_custo_com_pai_e_filho_selecionados(self):
        pai = Site("POP_A", "POP")
        filho = Site("BH_A", "BH")
        pai.custo = 100
        filho.custo = 40
        pai.adicionar_filho(filho)

        selecionados, usados = montar_escopo_sites(
            [pai, filho],
            incluir_filhos=True
        )
        resumo = montar_resumo_selecao_sites(
            selecionados,
            usados
        )

        self.assertEqual(resumo["custo_direto"], 140)
        self.assertEqual(resumo["custo_indireto"], 0)
        self.assertEqual(resumo["custo_total"], 140)

    def test_formatacao_de_custo_respeita_permissao(self):
        usuario_logado_anterior = topology_view._usuario_logado
        formatador_anterior = topology_view._formatar_moeda
        topology_view._usuario_logado = lambda: {"profile": "Teste"}
        topology_view._formatar_moeda = lambda valor: f"R$ {valor:.2f}"

        try:
            with patch.object(
                topology_view,
                "has_permission",
                return_value=False
            ):
                self.assertEqual(
                    topology_view.formatar_custo(100),
                    "Restrito"
                )

            with patch.object(
                topology_view,
                "has_permission",
                return_value=True
            ):
                self.assertEqual(
                    topology_view.formatar_custo(100),
                    "R$ 100.00"
                )
        finally:
            topology_view._usuario_logado = usuario_logado_anterior
            topology_view._formatar_moeda = formatador_anterior

    def test_normaliza_velocidades_em_mbps(self):
        self.assertEqual(
            normalizar_velocidade_mbps("NeoSoft 100 Mbps"),
            100
        )
        self.assertEqual(
            normalizar_velocidade_mbps("NeoTotal 1 Gbps"),
            1000
        )
        self.assertEqual(
            normalizar_velocidade_mbps("VPN 200M"),
            200
        )

    def test_velocidade_telecom_ignora_sva(self):
        self.assertIsNone(
            velocidade_telecom_produto_mbps(
                "NEOFIREWALL FN 60F UTM",
                self.catalogo_vazio()
            )
        )

    def test_velocidade_usa_catalogo_quando_produto_tem_nome_customizado(self):
        catalogo = pd.DataFrame([
            {
                "Nome": "Plano Especial Corporativo",
                "Tipo": "Telecom",
                "Grupo": "Internet",
                "Família": "NeoTotal",
                "Velocidade": "500M",
                "Variação": ""
            }
        ])

        self.assertEqual(
            velocidade_telecom_produto_mbps(
                "Plano Especial Corporativo",
                catalogo
            ),
            500
        )

    def test_metricas_somam_clientes_diretos_e_filhos(self):
        site = Site("POP_TESTE", "POP")
        filho = Site("BH_TESTE", "BH")
        site.adicionar_filho(filho)

        site.adicionar_cliente(
            self.cliente_com_produto(
                "1001",
                "NeoSoft 100 Mbps"
            )
        )
        filho.adicionar_cliente(
            self.cliente_com_produto(
                "1002",
                "NeoTotal 1 Gbps"
            )
        )
        filho.adicionar_cliente(
            self.cliente_com_produto(
                "1003",
                "NeoWifi 300"
            )
        )

        metricas = montar_metricas_banda_telecom_site(
            site,
            self.catalogo_vazio()
        )

        self.assertEqual(
            metricas["maior_mbps"],
            1000
        )
        self.assertEqual(
            metricas["soma_mbps"],
            1100
        )
        self.assertEqual(
            metricas["acima_100_mbps"],
            2
        )

    def test_metricas_de_sites_usados_respeitam_escopo_recebido(self):
        site = Site("POP_TESTE", "POP")
        filho = Site("BH_TESTE", "BH")
        site.adicionar_filho(filho)

        site.adicionar_cliente(
            self.cliente_com_produto(
                "1001",
                "NeoSoft 100 Mbps"
            )
        )
        filho.adicionar_cliente(
            self.cliente_com_produto(
                "1002",
                "NeoTotal 1 Gbps"
            )
        )
        filho.adicionar_cliente(
            self.cliente_com_produto(
                "1003",
                "NEOFIREWALL FN 60F UTM"
            )
        )

        metricas_sem_filho = montar_metricas_banda_telecom_sites(
            [site],
            self.catalogo_vazio()
        )
        metricas_com_filho = montar_metricas_banda_telecom_sites(
            [
                site,
                filho
            ],
            self.catalogo_vazio()
        )

        self.assertEqual(
            metricas_sem_filho["maior_mbps"],
            100
        )
        self.assertEqual(
            metricas_sem_filho["soma_mbps"],
            100
        )
        self.assertEqual(
            metricas_sem_filho["acima_100_mbps"],
            1
        )
        self.assertEqual(
            metricas_com_filho["maior_mbps"],
            1000
        )
        self.assertEqual(
            metricas_com_filho["soma_mbps"],
            1100
        )
        self.assertEqual(
            metricas_com_filho["acima_100_mbps"],
            2
        )

    def test_formata_banda(self):
        self.assertEqual(
            formatar_banda_mbps(0),
            "0 Mbps"
        )
        self.assertEqual(
            formatar_banda_mbps(100),
            "100 Mbps"
        )
        self.assertEqual(
            formatar_banda_mbps(1500),
            "1,5 Gbps"
        )


if __name__ == "__main__":
    unittest.main()
