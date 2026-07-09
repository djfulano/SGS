import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook

from app.services import finance_service as fs


class FinanceServiceTest(unittest.TestCase):

    def criar_planilha(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Fechamento 2016 a 2025"
        headers = [
            "Ano", "Prioridade", "CNPJ/CPF", "Tipo", "PIX", "Banco", "Cód", "Agência",
            "C/Corrente", "Multa", "Juros", "Mês", "Nome", "Fornecedor", "Microsiga",
            "Produto", "C.C", "RC NOVA", "OC NOVA ", "OC Primário", "OC Secundário",
            "Vencto", "Energia", "Outros", "Locação", "Subtotal", "Descrição"
        ]
        for col, header in enumerate(headers, start=1):
            ws.cell(row=6, column=col, value=header)
        row = [
            2026, "Prioridade", "00.000.000/0001-00", "TED", "", "ITAU", "341", "1234",
            "12345-6", 0.02, 0.01, 46023, "SITE TESTE", "FORNECEDOR TESTE", 92159,
            "", "", "RC1", "OCN", "OCP", "OCS", 18, 100, 20, 1000, 1120, "Pagamento teste"
        ]
        for col, value in enumerate(row, start=1):
            ws.cell(row=7, column=col, value=value)
        row_antigo = row.copy()
        row_antigo[0] = 2025
        row_antigo[12] = "SITE ANTIGO"
        row_antigo[13] = "FORNECEDOR ANTIGO"
        row_antigo[25] = 999
        for col, value in enumerate(row_antigo, start=1):
            ws.cell(row=8, column=col, value=value)

        ws2 = wb.create_sheet("Acordos")
        headers2 = ["", "Obs", "Mês", "Acordo", "Nome", "Resp", "Aprovado Sindico", "PAGO", "Microsiga", "Acordo2", "Descrição", "", "", "", "", "", "Multa + Juros"]
        for col, header in enumerate(headers2, start=1):
            ws2.cell(row=9, column=col, value=header)
        row2 = ["", "Obs teste", 46023, "Documento", "SITE TESTE", "Financeiro", "SIM", "", 92159, 500, "Acordo teste", "", "", "", "", "", 50]
        for col, value in enumerate(row2, start=1):
            ws2.cell(row=10, column=col, value=value)
        row2_antigo = row2.copy()
        row2_antigo[2] = 45658
        row2_antigo[4] = "ACORDO ANTIGO"
        for col, value in enumerate(row2_antigo, start=1):
            ws2.cell(row=11, column=col, value=value)

        ws3 = wb.create_sheet("Acordos Gráficos")
        ws3["A1"] = "Ignorar"

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsm")
        wb.save(temp.name)
        temp.close()
        return Path(temp.name)

    def test_importa_pagamentos_e_acordos_com_vinculo(self):
        path = self.criar_planilha()
        sites = {
            "SITE_SNMP": SimpleNamespace(
                microsiga="092159",
                codigo_topos="654321",
                nome="SITE_SNMP",
                nome_cadastro="SITE CADASTRO",
            )
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            payments = Path(temp_dir) / "payments.json"
            agreements = Path(temp_dir) / "agreements.json"
            with patch.object(fs, "PAYMENTS_FILE", payments), patch.object(fs, "AGREEMENTS_FILE", agreements):
                resultado = fs.importar_planilha_financeira(path, sites=sites, salvar=True, usuario="teste")
                self.assertEqual(resultado["resumo"]["pagamentos"]["importados"], 1)
                self.assertEqual(resultado["resumo"]["acordos"]["importados"], 1)
                self.assertEqual(resultado["resumo"]["pagamentos"]["com_site"], 1)
                self.assertEqual(resultado["resumo"]["pagamentos"]["sem_site"], 0)
                self.assertNotIn("SITE ANTIGO", set(resultado["pagamentos"]["Nome"]))
                self.assertNotIn("ACORDO ANTIGO", set(resultado["acordos"]["Nome"]))
                self.assertEqual(resultado["pagamentos"].iloc[0]["Nome SNMPc"], "SITE_SNMP")
                self.assertEqual(resultado["pagamentos"].iloc[0]["Microsiga"], "092159")
                self.assertEqual(resultado["pagamentos"].iloc[0]["OC NOVA"], "OCN")
                self.assertEqual(resultado["pagamentos"].iloc[0]["Subtotal"], 1120.0)
                self.assertEqual(resultado["acordos"].iloc[0]["Status"], "Aprovado")
                self.assertEqual(resultado["acordos"].iloc[0]["Valor Acordo"], 500.0)

                segunda = fs.importar_planilha_financeira(path, sites=sites, salvar=False, usuario="teste")
                self.assertEqual(segunda["resumo"]["pagamentos"]["novos"], 0)
                self.assertGreaterEqual(segunda["resumo"]["pagamentos"]["duplicados"], 1)

    def test_status_pagamento_vencido_derivado(self):
        row = {"Status": "Pendente", "Data de vencimento": "2026-01-01"}
        self.assertEqual(fs.status_pagamento_exibicao(row), "Vencido")
        row_pago = {"Status": "Pago", "Data de vencimento": "2026-01-01"}
        self.assertEqual(fs.status_pagamento_exibicao(row_pago), "Pago")


if __name__ == "__main__":
    unittest.main()
