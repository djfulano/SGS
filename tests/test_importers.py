import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.models.site import Site
from app.importers.txt_importer import detectar_tipo
from app.importers.txt_importer import extrair_assinatura
from app.importers.txt_importer import importar_estrutura
from app.importers.txt_importer import importar_estrutura_de_linhas
from app.importers.txt_importer import normalizar_nome_snmpc
from app.importers.excel_importer import ler_clientes_base
from app.importers.excel_importer import importar_clientes

try:
    from app.services.data_loader import aplicar_cadastro_topos
    from app.services.data_loader import consolidar_sites_duplicados_cadastro
    from app.services.data_loader import sistema_precisa_inicializacao
    from app.services.data_loader import status_inicializacao_dados
except ModuleNotFoundError:
    aplicar_cadastro_topos = None
    consolidar_sites_duplicados_cadastro = None
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

    @unittest.skipIf(carregar_topos is None, "pandas nao instalado")
    def test_carregar_topos_preserva_alerta_critico(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "Sites.xlsx"
            pd.DataFrame([{
                "CÓDIGO AQUILES": "123",
                "SNMPc": "SITE_CRITICO_123_IP",
                "TIPO": "POP",
                "NOME": "Site crítico",
                "SITE CRÍTICO": "Sim",
                "TIPO CRITICIDADE": "Bloqueia",
                "DIA VENCIMENTO": 18,
            }]).to_excel(caminho, index=False)

            df = carregar_topos(caminho)

        self.assertEqual(df.iloc[0]["Site Critico"], "Sim")
        self.assertEqual(df.iloc[0]["Tipo Criticidade"], "Bloqueia")
        self.assertEqual(df.iloc[0]["Dia Vencimento"], 18)

    @unittest.skipIf(carregar_topos is None, "pandas nao instalado")
    def test_carregar_topos_soma_locacao_energia_e_outros(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "Sites.xlsx"
            pd.DataFrame([{
                "CÓDIGO AQUILES": "123",
                "SNMPc": "SITE_CUSTOS_123_IP",
                "LOCAÇÃO": "R$ 1.000,00",
                "ENERGIA": "R$ 250,00",
                "OUTROS": "R$ 50,00",
                "CNPJ/CPF": "12.345.678/0001-90",
                "TIPO PGTO": "PIX",
                "CHAVE PIX": "financeiro@example.com",
                "BANCO": "Banco Teste",
                "CÓDIGO BANCO": "001",
                "AGÊNCIA": "1234",
                "CONTA CORRENTE": "98765-0",
                "MULTA": "2%",
                "JUROS": "1% a.m.",
            }]).to_excel(caminho, index=False)

            df = carregar_topos(caminho)

        self.assertEqual(df.iloc[0]["Locacao"], 1000)
        self.assertEqual(df.iloc[0]["Energia"], 250)
        self.assertEqual(df.iloc[0]["Outros Custos"], 50)
        self.assertEqual(df.iloc[0]["Custo"], 1300)
        self.assertEqual(df.iloc[0]["CNPJ CPF"], "12.345.678/0001-90")
        self.assertEqual(df.iloc[0]["Tipo Pagamento"], "PIX")
        self.assertEqual(df.iloc[0]["Pix"], "financeiro@example.com")
        self.assertEqual(df.iloc[0]["Banco"], "Banco Teste")
        self.assertEqual(df.iloc[0]["Codigo Banco"], "001")
        self.assertEqual(df.iloc[0]["Agencia"], "1234")
        self.assertEqual(df.iloc[0]["Conta Corrente"], "98765-0")
        self.assertEqual(df.iloc[0]["Multa"], "2%")
        self.assertEqual(df.iloc[0]["Juros"], "1% a.m.")

    @unittest.skipIf(carregar_topos is None, "pandas nao instalado")
    def test_carregar_topos_trata_custo_legado_como_locacao(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "Sites.xlsx"
            pd.DataFrame([{
                "CÓDIGO AQUILES": "123",
                "SNMPc": "SITE_CUSTO_LEGADO_123_IP",
                "CUSTO": 900,
            }]).to_excel(caminho, index=False)

            df = carregar_topos(caminho)

        self.assertEqual(df.iloc[0]["Locacao"], 900)
        self.assertEqual(df.iloc[0]["Custo"], 900)

    @unittest.skipIf(carregar_topos is None, "pandas nao instalado")
    def test_carregar_topos_aceita_alias_vencimento_e_descarta_dia_invalido(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "Sites.xlsx"
            pd.DataFrame([
                {
                    "CÓDIGO AQUILES": "123",
                    "SNMPc": "SITE_A",
                    "VENCIMENTO": 18,
                },
                {
                    "CÓDIGO AQUILES": "124",
                    "SNMPc": "SITE_B",
                    "VENCIMENTO": 29,
                },
            ]).to_excel(caminho, index=False)

            df = carregar_topos(caminho)

        self.assertEqual(df.iloc[0]["Dia Vencimento"], 18)
        self.assertEqual(df.iloc[1]["Dia Vencimento"], 0)

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

    def test_importar_estrutura_aceita_campos_vazios_validos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "SNMPc.txt"
            caminho.write_text(
                "Name,Type,Address,ID,Description,Parent,Status\n"
                '"ABC_POP_1_IP","Subnet","","1","","(NULL)",""\n',
                encoding="latin1"
            )

            sites, assinaturas, equipamentos = importar_estrutura(caminho)

        self.assertIn("ABC_POP_1_IP", sites)
        self.assertEqual(assinaturas, {})
        self.assertEqual(equipamentos, [])

    def test_importar_estrutura_recusa_linha_com_colunas_ausentes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "SNMPc.txt"
            caminho.write_text(
                "Name,Type,Address,ID,Status\n"
                '"ETH1","Network","","203359"\n',
                encoding="latin1"
            )

            with self.assertRaisesRegex(
                ValueError,
                r"Arquivo SNMPc incompleto ou inválido.*ETH1.*colunas ausentes"
            ):
                importar_estrutura(caminho)

    def test_importar_estrutura_recusa_linha_com_colunas_extras(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "SNMPc.txt"
            caminho.write_text(
                "Name,Type,ID\n"
                '"ETH1","Network","203359","EXTRA"\n',
                encoding="latin1"
            )

            with self.assertRaisesRegex(
                ValueError,
                r"Arquivo SNMPc incompleto ou inválido.*ETH1.*acima do cabeçalho"
            ):
                importar_estrutura(caminho)

    def test_importar_estrutura_recusa_aspas_sem_fechamento(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "SNMPc.txt"
            caminho.write_text(
                "Name,Type,Address,ID,Status\n"
                '"ETH1","Network","","203359","Normal',
                encoding="latin1"
            )

            with self.assertRaisesRegex(
                ValueError,
                r"Arquivo SNMPc incompleto ou inválido.*ETH1.*unexpected end of data"
            ):
                importar_estrutura(caminho)

    @unittest.skipIf(
        consolidar_sites_duplicados_cadastro is None,
        "pandas nao instalado"
    )
    def test_consolida_container_snmpc_pelo_nome_oficial_do_cadastro(self):
        linhas = [
            {
                "ID": "1", "Name": "WINDSOR_POP_94500_IP",
                "Type": "Subnet", "Parent": "(NULL)",
                "Address": "", "Description": ""
            },
            {
                "ID": "2", "Name": "WIN_POP_94500_IP",
                "Type": "Subnet", "Parent": "1",
                "Address": "", "Description": ""
            },
            {
                "ID": "3", "Name": "WIN_S1", "Type": "Subnet",
                "Parent": "2", "Address": "", "Description": ""
            },
            {
                "ID": "4", "Name": "CLIENTE_WIN_12345678",
                "Type": "Subnet", "Parent": "3",
                "Address": "", "Description": ""
            },
            {
                "ID": "5", "Name": "RADIO_WIN", "Type": "Device",
                "Parent": "2", "Address": "10.0.0.1",
                "Icon": "radio.ico", "Description": ""
            }
        ]
        sites, assinaturas, equipamentos, enlaces = importar_estrutura_de_linhas(
            linhas,
            retornar_enlaces=True
        )
        cadastro = pd.DataFrame([{
            "Codigo": "94500",
            "SNMPc": "WIN_POP_94500_IP",
            "Nome Cadastro": "CASTELO DE WINDSOR"
        }])

        aplicar_cadastro_topos(sites, cadastro)
        sites = consolidar_sites_duplicados_cadastro(
            sites,
            assinaturas,
            equipamentos,
            enlaces
        )

        self.assertEqual(list(sites), ["WIN_POP_94500_IP"])
        self.assertEqual(assinaturas["12345678"]["site"], sites["WIN_POP_94500_IP"])
        self.assertEqual(equipamentos[0]["Site"], "WIN_POP_94500_IP")
        self.assertEqual(equipamentos[0]["Arvore"].split(" > ")[0], "WIN_POP_94500_IP")
        self.assertIsNone(sites["WIN_POP_94500_IP"].pai)

    @unittest.skipIf(
        consolidar_sites_duplicados_cadastro is None,
        "pandas nao instalado"
    )
    def test_nao_consolida_codigo_sem_nome_snmpc_oficial_unico(self):
        primeiro = Site("ABC_POP_123_IP", "POP")
        segundo = Site("XYZ_POP_123_IP", "POP")

        for site in [primeiro, segundo]:
            site.codigo_topos = "123"
            site.cadastro_topos = {"Codigo": "123", "SNMPc": "OUTRO_POP_123_IP"}

        sites = consolidar_sites_duplicados_cadastro({
            primeiro.nome: primeiro,
            segundo.nome: segundo
        })

        self.assertEqual(set(sites), {primeiro.nome, segundo.nome})

    def test_importar_cliente_com_goto_em_outro_site(self):
        linhas = [
            {
                "ID": "1", "Name": "BEL_POP_1_IP", "Type": "Subnet",
                "Parent": "(NULL)", "Address": "", "Description": ""
            },
            {
                "ID": "2", "Name": "FUV_POP_2_IP", "Type": "Subnet",
                "Parent": "(NULL)", "Address": "", "Description": ""
            },
            {
                "ID": "10", "Name": "BEL_S10", "Type": "Subnet",
                "Parent": "1", "Address": "", "Description": ""
            },
            {
                "ID": "20", "Name": "FUV_S6", "Type": "Subnet",
                "Parent": "2", "Address": "", "Description": ""
            },
            {
                "ID": "100", "Name": "DAVO_ITAQUERA_10986201",
                "Type": "Subnet", "Parent": "10", "Address": "",
                "Description": ""
            },
            {
                "ID": "101", "Name": "DAVO_ITAQUERA_10986201",
                "Type": "Goto", "Parent": "20",
                "Address": "DAVO_ITAQUERA_10986201", "Description": ""
            },
            {
                "ID": "102", "Name": "DAVO_ITAQUERA_10986201",
                "Type": "Goto", "Parent": "20",
                "Address": "DAVO_ITAQUERA_10986201", "Description": ""
            }
        ]

        sites, assinaturas, _equipamentos = importar_estrutura_de_linhas(linhas)
        vinculos = assinaturas["10986201"]["vinculos"]

        self.assertEqual(len(vinculos), 2)
        self.assertEqual(
            [(item["site"].nome, item["setorial"], item["tipo"]) for item in vinculos],
            [
                ("BEL_POP_1_IP", "BEL_S10", "Principal"),
                ("FUV_POP_2_IP", "FUV_S6", "Adicional")
            ]
        )
        self.assertIn("10986201", sites["BEL_POP_1_IP"].assinaturas)
        self.assertIn("10986201", sites["FUV_POP_2_IP"].assinaturas)

    def test_planilha_cria_cliente_principal_e_adicional_sem_duplicar_receita(self):
        principal = Site("BEL_POP_1_IP", "POP")
        adicional = Site("FUV_POP_2_IP", "POP")
        assinaturas = {
            "10986201": {
                "site": principal,
                "setorial": "BEL_S10",
                "tipo": "Principal",
                "vinculos": [
                    {
                        "site": principal,
                        "setorial": "BEL_S10",
                        "tipo": "Principal"
                    },
                    {
                        "site": adicional,
                        "setorial": "FUV_S6",
                        "tipo": "Adicional"
                    }
                ]
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo = Path(temp_dir) / "clientes.xlsx"
            pd.DataFrame([{
                "NOME CLIENTE": "DAVO ITAQUERA",
                "MENSALIDADE": 900,
                "NUM ASSINATURA": "10986201",
                "PRODUTO": "NeoSoft"
            }]).to_excel(arquivo, index=False, startrow=7)

            with patch("app.importers.excel_importer.registrar_log_sistema"):
                importar_clientes(arquivo, assinaturas)

        self.assertEqual(len(principal.clientes), 1)
        self.assertEqual(len(adicional.clientes), 0)
        self.assertEqual(len(adicional.clientes_adicionais), 1)
        self.assertEqual(principal.calcular_receita(), 900)
        self.assertEqual(adicional.calcular_receita(), 0)

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
