import unittest

from app.models.cliente import Cliente
from app.models.site import Site
from app.ui.views.support import montar_dados_agendamento


class SupportViewHelpersTest(unittest.TestCase):

    def site_com_cliente(self):
        site = Site("POP_A")
        cliente = Cliente(
            "Cliente A",
            100,
            "123",
            setorial="S1"
        )
        cliente.endereco_completo = "Rua A, 10"
        cliente.bairro = "Centro"
        cliente.cidade = "Belo Horizonte"
        cliente.produto = "NeoTotal 100M"
        site.clientes.append(
            cliente
        )
        site.clientes_estrutura.append({
            "assinatura": "123",
            "nome": "Cliente A",
            "predio": "P001",
            "setorial": "S1"
        })

        return site

    def test_agendamento_assinatura_com_cliente_predio_e_equipamento(self):
        site = self.site_com_cliente()
        dados, df_equipamentos = montar_dados_agendamento(
            {
                site.nome: site
            },
            [
                {
                    "Assinatura": "123",
                    "Site": "POP_A",
                    "Setorial": "S1",
                    "Icone": "ONU",
                    "Equipamento": "ONU Cliente",
                    "Endereco": "10.0.0.2",
                    "Parent": "SW Base",
                    "Arvore": "POP_A > SW Base > ONU Cliente",
                    "Status": "Normal",
                    "Predio": "P001"
                }
            ],
            "123"
        )

        self.assertEqual(
            dados["Nº da Assinatura"],
            "123"
        )
        self.assertEqual(
            dados["Nº do Código do Prédio"],
            "P001"
        )
        self.assertEqual(
            dados["Endereço"],
            "Rua A, 10"
        )
        self.assertEqual(
            dados["Equipamento Base"],
            "SW Base"
        )
        self.assertEqual(
            dados["Equipamento Cliente"],
            "ONU Cliente"
        )
        self.assertEqual(
            dados["Caminho até o POP"],
            "POP_A > SW Base > ONU Cliente"
        )
        self.assertEqual(
            len(df_equipamentos),
            1
        )
        self.assertEqual(
            df_equipamentos.iloc[0]["IP/Endereço"],
            "10.0.0.2"
        )

    def test_agendamento_assinatura_sem_equipamento(self):
        site = self.site_com_cliente()
        dados, df_equipamentos = montar_dados_agendamento(
            {
                site.nome: site
            },
            [],
            "123"
        )

        self.assertEqual(
            dados["Equipamento Cliente"],
            "Não localizado"
        )
        self.assertTrue(
            df_equipamentos.empty
        )

    def test_agendamento_assinatura_no_snmpc_sem_cliente_base(self):
        site = Site("POP_A")
        site.clientes_estrutura.append({
            "assinatura": "999",
            "nome": "Cliente SNMPc",
            "predio": "P999",
            "setorial": "S9"
        })

        dados, df_equipamentos = montar_dados_agendamento(
            {
                site.nome: site
            },
            [
                {
                    "Assinatura": "999",
                    "Equipamento": "Radio Cliente",
                    "Setorial": "S9",
                    "Predio": "P999"
                }
            ],
            "999"
        )

        self.assertEqual(
            dados["Nº do Código do Prédio"],
            "P999"
        )
        self.assertEqual(
            dados["Produto contratado"],
            "Não localizado"
        )
        self.assertEqual(
            len(df_equipamentos),
            1
        )

    def test_agendamento_assinatura_inexistente(self):
        dados, df_equipamentos = montar_dados_agendamento(
            {},
            [],
            "000"
        )

        self.assertEqual(
            dados["Nº da Assinatura"],
            "000"
        )
        self.assertEqual(
            dados["Endereço"],
            "Não localizado"
        )
        self.assertTrue(
            df_equipamentos.empty
        )

    def test_agendamento_multiplos_equipamentos(self):
        dados, df_equipamentos = montar_dados_agendamento(
            {},
            [
                {
                    "Assinatura": "123",
                    "Equipamento": "ONU A",
                    "Parent": "SW A"
                },
                {
                    "Assinatura": "123",
                    "Equipamento": "ONU B",
                    "Parent": "SW B"
                }
            ],
            "123"
        )

        self.assertEqual(
            dados["Equipamento Cliente"],
            "ONU A, ONU B"
        )
        self.assertEqual(
            dados["Equipamento Base"],
            "SW A, SW B"
        )
        self.assertEqual(
            len(df_equipamentos),
            2
        )


if __name__ == "__main__":
    unittest.main()
