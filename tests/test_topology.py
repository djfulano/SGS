import unittest

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.ui.views.topology import formatar_banda_mbps
from app.ui.views.topology import montar_metricas_banda_telecom_site
from app.ui.views.topology import montar_metricas_banda_telecom_sites
from app.ui.views.topology import normalizar_velocidade_mbps
from app.ui.views.topology import velocidade_telecom_produto_mbps


class TopologyBandwidthTest(unittest.TestCase):

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
