import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.importers.txt_importer import detectar_tipo
from app.importers.txt_importer import extrair_assinatura
from app.importers.txt_importer import importar_estrutura_de_linhas
from app.importers.txt_importer import normalizar_nome_snmpc
from app.importers.excel_importer import ler_clientes_base

try:
    from app.services.data_loader import sistema_precisa_inicializacao
    from app.services.data_loader import status_inicializacao_dados
except ModuleNotFoundError:
    sistema_precisa_inicializacao = None
    status_inicializacao_dados = None

try:
    from app.importers.excel_importer import normalizar_assinatura
except ModuleNotFoundError:
    normalizar_assinatura = None

try:
    from app.importers.topos_importer import carregar_topos
    from app.importers.topos_importer import chave_site
    from app.importers.topos_importer import valor_coordenada
except ModuleNotFoundError:
    carregar_topos = None
    chave_site = None
    valor_coordenada = None


class ImportersTest(unittest.TestCase):

    @unittest.skipIf(status_inicializacao_dados is None, "pandas nao instalado")
    def test_status_inicializacao_detecta_arquivos_ausentes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            imports = base / "imports"
            imports.mkdir()

            with patch(
                "app.services.data_loader.CLIENTES_FILE",
                imports / "clientes.xlsx"
            ), patch(
                "app.importers.structure_importer.IMPORTS_DIR",
                imports
            ), patch(
                "app.importers.topos_importer.IMPORTS_DIR",
                imports
            ), patch(
                "app.importers.topos_importer.SITES_FILE",
                imports / "Sites.xlsx"
            ):
                status = status_inicializacao_dados()

            self.assertTrue(
                all(not item["existe"] for item in status)
            )

    @unittest.skipIf(sistema_precisa_inicializacao is None, "pandas nao instalado")
    def test_sistema_precisa_inicializacao_fica_falso_com_arquivos_obrigatorios(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            imports = base / "imports"
            imports.mkdir()
            (imports / "SNMPc.txt").write_text(
                "x",
                encoding="utf-8"
            )
            (imports / "Sites.xlsx").write_text(
                "x",
                encoding="utf-8"
            )
            (imports / "clientes.xlsx").write_text(
                "x",
                encoding="utf-8"
            )

            with patch(
                "app.services.data_loader.CLIENTES_FILE",
                imports / "clientes.xlsx"
            ), patch(
                "app.importers.structure_importer.IMPORTS_DIR",
                imports
            ), patch(
                "app.importers.topos_importer.IMPORTS_DIR",
                imports
            ), patch(
                "app.importers.topos_importer.SITES_FILE",
                imports / "Sites.xlsx"
            ):
                self.assertFalse(
                    sistema_precisa_inicializacao()
                )


    @unittest.skipIf(normalizar_assinatura is None, "pandas nao instalado")
    def test_ler_clientes_base_carrega_gerente_contas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo = Path(temp_dir) / "clientes.xlsx"
            df = pd.DataFrame([
                {
                    "NOME CLIENTE": "Cliente A",
                    "MENSALIDADE": 100,
                    "NUM ASSINATURA": "123",
                    "PRODUTO": "NeoSoft",
                    "Gerente Contas": "Maria Silva"
                }
            ])

            with pd.ExcelWriter(arquivo) as writer:
                df.to_excel(
                    writer,
                    index=False,
                    startrow=7
                )

            clientes = ler_clientes_base(arquivo)

        self.assertEqual(
            clientes["123"]["Gerente Contas"],
            "Maria Silva"
        )

    @unittest.skipIf(normalizar_assinatura is None, "pandas nao instalado")
    def test_normalizar_assinatura_mantem_apenas_digitos(self):
        self.assertEqual(normalizar_assinatura(" 12.345.678 "), "12345678")
        self.assertEqual(normalizar_assinatura(12345678.0), "12345678")

    def test_extrair_assinatura_no_final_do_nome(self):
        self.assertEqual(extrair_assinatura("CLIENTE ABC 12345678"), "12345678")
        self.assertIsNone(extrair_assinatura("CLIENTE 1234"))

    def test_detectar_tipo_ignora_setorial(self):
        self.assertEqual(detectar_tipo({"Name": "ABC_POP_1_IP"}), "POP")
        self.assertIsNone(detectar_tipo({"Name": "ABC_S1_1_IP"}))

    def test_normalizar_site_com_espaco_antes_do_sufixo_snmpc(self):
        self.assertEqual(
            normalizar_nome_snmpc("CVN_BH_113520 _IP"),
            "CVN_BH_113520_IP"
        )
        self.assertEqual(
            detectar_tipo({"Name": "CVN_BH_113520 _IP"}),
            "BH"
        )

    @unittest.skipIf(chave_site is None, "pandas nao instalado")
    def test_chave_site_normaliza_espaco_antes_do_sufixo_snmpc(self):
        self.assertEqual(
            chave_site("CVN_BH_113520 _IP"),
            "CVN_BH_113520_IP"
        )

    @unittest.skipIf(valor_coordenada is None, "pandas nao instalado")
    def test_valor_coordenada_preserva_ponto_decimal(self):
        self.assertEqual(valor_coordenada("-46.761751417"), -46.761751417)
        self.assertEqual(valor_coordenada("-46,761751417"), -46.761751417)
        self.assertAlmostEqual(
            valor_coordenada("-467617514.17"),
            -46.761751417
        )
        self.assertAlmostEqual(
            valor_coordenada("-2352196800000001", limite=90),
            -23.52196800000001
        )

    @unittest.skipIf(carregar_topos is None, "pandas nao instalado")
    def test_carregar_topos_preserva_tipo_cliente(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "Sites.xlsx"
            pd.DataFrame([
                {
                    "CÓDIGO AQUILES": "123",
                    "SNMPc": "CLI_CLIENTE_123_IP",
                    "TIPO": "Cliente",
                    "NOME": "Cliente interno"
                }
            ]).to_excel(
                caminho,
                index=False
            )

            df = carregar_topos(caminho)

        self.assertEqual(
            df.iloc[0]["Tipo Cadastro"],
            "CLIENTE"
        )

    def test_importar_estrutura_minima_com_cliente(self):
        linhas = [
            {
                "ID": "1",
                "Name": "ABC_POP_1_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "2",
                "Name": "CLIENTE ABC 12345678",
                "Type": "Subnet",
                "Parent": "1",
                "Address": "",
                "Description": ""
            }
        ]

        sites, assinaturas, equipamentos = importar_estrutura_de_linhas(linhas)

        self.assertIn("ABC_POP_1_IP", sites)
        self.assertIn("12345678", assinaturas)
        self.assertEqual(assinaturas["12345678"]["site"].nome, "ABC_POP_1_IP")
        self.assertEqual(equipamentos, [])

    def test_importar_estrutura_normaliza_site_com_espaco_antes_do_sufixo(self):
        linhas = [
            {
                "ID": "1",
                "Name": "CVN_BH_113520 _IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            }
        ]

        sites, assinaturas, equipamentos = importar_estrutura_de_linhas(linhas)

        self.assertIn("CVN_BH_113520_IP", sites)
        self.assertNotIn("CVN_BH_113520 _IP", sites)
        self.assertEqual(sites["CVN_BH_113520_IP"].tipo, "BH")
        self.assertEqual(assinaturas, {})
        self.assertEqual(equipamentos, [])

    def test_importar_estrutura_identifica_enlace_pop_pop(self):
        linhas = [
            {
                "ID": "1",
                "Name": "FUV_POP_108506_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "2",
                "Name": "SAN_POP_105452_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "3",
                "Name": "L2_FUV_SAN",
                "Type": "Network",
                "Parent": "1",
                "Address": "",
                "Icon": "auto.ico",
                "Status": "Normal-Green",
                "Links": "(FUV(1),SAN(2))"
            }
        ]

        sites, _assinaturas, _equipamentos, enlaces = importar_estrutura_de_linhas(
            linhas,
            retornar_enlaces=True
        )

        self.assertIn("FUV_POP_108506_IP", sites)
        self.assertIn("SAN_POP_105452_IP", sites)
        self.assertEqual(len(enlaces), 1)
        self.assertEqual(enlaces[0]["Tipo Enlace"], "POP x POP")
        self.assertEqual(enlaces[0]["Site Origem"], "FUV_POP_108506_IP")
        self.assertEqual(enlaces[0]["Site Destino"], "SAN_POP_105452_IP")

    def test_importar_estrutura_resolve_endpoint_por_ancestral(self):
        linhas = [
            {
                "ID": "1",
                "Name": "FUV_POP_108506_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "2",
                "Name": "AUS_POP_92309_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "10",
                "Name": "SW-FUV",
                "Type": "Device",
                "Parent": "1",
                "Address": "",
                "Icon": "switch.ico",
                "Status": "",
                "Description": ""
            },
            {
                "ID": "20",
                "Name": "SW-AUS",
                "Type": "Device",
                "Parent": "2",
                "Address": "",
                "Icon": "switch.ico",
                "Status": "",
                "Description": ""
            },
            {
                "ID": "30",
                "Name": "L2_FUV_AUS",
                "Type": "Network",
                "Parent": "1",
                "Address": "",
                "Icon": "auto.ico",
                "Status": "",
                "Links": "(SW-FUV(10),SW-AUS(20))"
            }
        ]

        _sites, _assinaturas, _equipamentos, enlaces = importar_estrutura_de_linhas(
            linhas,
            retornar_enlaces=True
        )

        self.assertEqual(len(enlaces), 1)
        self.assertEqual(enlaces[0]["Site Origem"], "FUV_POP_108506_IP")
        self.assertEqual(enlaces[0]["Site Destino"], "AUS_POP_92309_IP")

    def test_importar_estrutura_ignora_enlace_dentro_do_mesmo_site(self):
        linhas = [
            {
                "ID": "1",
                "Name": "FUV_POP_108506_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "10",
                "Name": "SW-FUV-A",
                "Type": "Device",
                "Parent": "1",
                "Address": "",
                "Icon": "switch.ico",
                "Status": "",
                "Description": ""
            },
            {
                "ID": "20",
                "Name": "SW-FUV-B",
                "Type": "Device",
                "Parent": "1",
                "Address": "",
                "Icon": "switch.ico",
                "Status": "",
                "Description": ""
            },
            {
                "ID": "30",
                "Name": "L2_INTERNO",
                "Type": "Network",
                "Parent": "1",
                "Address": "",
                "Icon": "auto.ico",
                "Status": "",
                "Links": "(SW-FUV-A(10),SW-FUV-B(20))"
            }
        ]

        _sites, _assinaturas, _equipamentos, enlaces = importar_estrutura_de_linhas(
            linhas,
            retornar_enlaces=True
        )

        self.assertEqual(enlaces, [])

    def test_importar_estrutura_identifica_enlace_pop_pop_por_dispositivo(self):
        linhas = [
            {
                "ID": "1",
                "Name": "FUV_POP_108506_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "2",
                "Name": "SAN_POP_105452_IP",
                "Type": "Subnet",
                "Parent": "(NULL)",
                "Address": "",
                "Description": ""
            },
            {
                "ID": "10",
                "Name": "OSPF-FUV_x_SAN-201.23.127.82",
                "Type": "Device",
                "Parent": "1",
                "Address": "201.23.127.81",
                "Icon": "router.ico",
                "Status": "",
                "Description": ""
            }
        ]

        _sites, _assinaturas, _equipamentos, enlaces = importar_estrutura_de_linhas(
            linhas,
            retornar_enlaces=True
        )

        self.assertEqual(len(enlaces), 1)
        self.assertEqual(enlaces[0]["Tipo Enlace"], "POP x POP")
        self.assertEqual(enlaces[0]["Site Origem"], "FUV_POP_108506_IP")
        self.assertEqual(enlaces[0]["Site Destino"], "SAN_POP_105452_IP")
        self.assertEqual(enlaces[0]["Origem Dados"], "Device")


if __name__ == "__main__":
    unittest.main()
