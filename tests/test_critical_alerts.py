import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.services import critical_alerts as alerts
from app.services import finance_service as finance


class CriticalAlertsTest(unittest.TestCase):

    def cadastro(self, **overrides):
        registro = {
            "CÓDIGO MICROSIGA": "123",
            "CÓDIGO AQUILES": "10",
            "SMNPC": "SITE_CRITICO",
            "NOME": "Site Crítico",
            "Status": "Ativo",
            "SITE CRÍTICO": "Sim",
            "DIA VENCIMENTO": 20,
        }
        registro.update(overrides)
        return pd.DataFrame([registro])

    def pagamento(self, **overrides):
        registro = {coluna: "" for coluna in finance.PAYMENT_COLUMNS}
        registro.update({
            "ID SGS": "P1",
            "Status": "Pendente",
            "Microsiga": "000123",
            "Site localizado": "Sim",
            "Nome SNMPc": "SITE_CRITICO",
            "Tipo de despesa": "RECORRENTE",
            "Data de vencimento": "2026-07-18",
            "Subtotal": 500.0,
        })
        registro.update(overrides)
        return registro

    def acordo(self, **overrides):
        registro = {coluna: "" for coluna in finance.AGREEMENT_COLUMNS}
        registro.update({
            "ID SGS": "A1",
            "Status": "Em pagamento",
            "Microsiga": "000999",
            "Site localizado": "Sim",
            "Nome Site": "Outro site",
            "Nome SNMPc": "OUTRO_SITE",
            "Favorecido": "Fornecedor",
            "Data de vencimento": "2026-07-25",
            "Valor Acordo": 900.0,
        })
        registro.update(overrides)
        return registro

    def test_proximo_vencimento_mensal_limita_dias_validos(self):
        self.assertEqual(
            alerts.proximo_vencimento_mensal(20, date(2026, 7, 10)),
            date(2026, 7, 20),
        )
        self.assertEqual(
            alerts.proximo_vencimento_mensal(20, date(2026, 7, 21)),
            date(2026, 8, 20),
        )
        self.assertIsNone(alerts.proximo_vencimento_mensal(29, date(2026, 7, 1)))

    def test_parcela_real_tem_prioridade_e_mantem_atraso(self):
        pagamentos = pd.DataFrame([self.pagamento()])
        resultado, diagnosticos = alerts.montar_alertas_sites_criticos(
            self.cadastro(),
            pagamentos,
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )
        self.assertTrue(diagnosticos.empty)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]["Vencimento"], "2026-07-18")
        self.assertEqual(resultado.iloc[0]["Dias"], -3)
        self.assertEqual(resultado.iloc[0]["Origem da data"], "Parcela financeira aberta")

    def test_dia_mensal_e_usado_sem_parcela_aberta(self):
        resultado, _ = alerts.montar_alertas_sites_criticos(
            self.cadastro(**{"DIA VENCIMENTO": 25}),
            pd.DataFrame(columns=finance.PAYMENT_COLUMNS),
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )
        self.assertEqual(resultado.iloc[0]["Vencimento"], "2026-07-25")
        self.assertEqual(resultado.iloc[0]["Situação"], "Vence em 4 dias")

    def test_site_critico_sem_vencimento_nao_alerta_mesmo_com_parcela(self):
        resultado, diagnosticos = alerts.montar_alertas_sites_criticos(
            self.cadastro(**{"DIA VENCIMENTO": ""}),
            pd.DataFrame([self.pagamento()]),
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )

        self.assertTrue(resultado.empty)
        self.assertEqual(len(diagnosticos), 1)
        self.assertEqual(
            diagnosticos.iloc[0]["Tipo"],
            "Site crítico sem vencimento padrão",
        )

    def test_site_nao_critico_com_vencimento_nao_alerta(self):
        resultado, diagnosticos = alerts.montar_alertas_sites_criticos(
            self.cadastro(**{"SITE CRÍTICO": "Não", "DIA VENCIMENTO": 20}),
            pd.DataFrame([self.pagamento()]),
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )

        self.assertTrue(resultado.empty)
        self.assertTrue(diagnosticos.empty)

    def test_ignora_site_inativo_nao_critico_e_pagamento_encerrado(self):
        cadastro = pd.concat([
            self.cadastro(Status="Cancelado"),
            self.cadastro(**{"CÓDIGO MICROSIGA": "124", "SITE CRÍTICO": "Não"}),
        ], ignore_index=True)
        pagamentos = pd.DataFrame([self.pagamento(Status="Pago")])
        resultado, _ = alerts.montar_alertas_sites_criticos(
            cadastro,
            pagamentos,
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )
        self.assertTrue(resultado.empty)

    def test_acordos_sao_separados_e_excluem_encerrados(self):
        acordos = pd.DataFrame([
            self.acordo(),
            self.acordo(**{"ID SGS": "A2", "Status": "Quitado"}),
            self.acordo(**{
                "ID SGS": "A3",
                "ID Pagamento": "PAGO",
                "Data de vencimento": "2026-07-24",
            }),
        ])
        pagamentos = pd.DataFrame([
            self.pagamento(**{"ID SGS": "PAGO", "Status": "Pago"}),
        ])
        resultado, diagnosticos = alerts.montar_alertas_acordos(
            acordos,
            pagamentos,
            hoje=date(2026, 7, 21),
            antecedencia=15,
        )
        self.assertTrue(diagnosticos.empty)
        self.assertEqual(list(resultado["ID SGS"]), ["A1"])
        self.assertEqual(resultado.iloc[0]["Dias"], 4)

    def test_configuracao_de_antecedencia_e_normalizada(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "alerts.json"
            alerts.save_alert_config({"alert_days": 999}, path)
            self.assertEqual(alerts.load_alert_config(path)["alert_days"], 90)

    def test_assinatura_muda_com_arquivo_ou_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pagamentos = Path(temp_dir) / "payments.json"
            acordos = Path(temp_dir) / "agreements.json"
            pagamentos.write_text("[]", encoding="utf-8")
            acordos.write_text("[]", encoding="utf-8")
            caminhos = [pagamentos, acordos]

            inicial = alerts.assinatura_fontes_alertas(
                date(2026, 7, 21),
                caminhos,
            )
            self.assertEqual(
                inicial,
                alerts.assinatura_fontes_alertas(
                    date(2026, 7, 21),
                    caminhos,
                ),
            )

            pagamentos.write_text('[{"novo": true}]', encoding="utf-8")
            alterada = alerts.assinatura_fontes_alertas(
                date(2026, 7, 21),
                caminhos,
            )
            self.assertNotEqual(inicial, alterada)
            self.assertNotEqual(
                alterada,
                alerts.assinatura_fontes_alertas(
                    date(2026, 7, 22),
                    caminhos,
                ),
            )

    def test_status_prepara_bases_financeiras_uma_vez(self):
        pagamentos = pd.DataFrame([self.pagamento()])
        acordos = pd.DataFrame([self.acordo()])

        with (
            patch.object(
                alerts,
                "preparar_pagamentos_exibicao",
                wraps=alerts.preparar_pagamentos_exibicao,
            ) as preparar_pagamentos,
            patch.object(
                alerts,
                "preparar_acordos_exibicao",
                wraps=alerts.preparar_acordos_exibicao,
            ) as preparar_acordos,
        ):
            resultado = alerts.status_alertas_criticos(
                self.cadastro(),
                pagamentos,
                acordos,
                hoje=date(2026, 7, 21),
                antecedencia=15,
            )

        self.assertEqual(preparar_pagamentos.call_count, 1)
        self.assertEqual(preparar_acordos.call_count, 1)
        self.assertEqual(resultado["total"], 2)


if __name__ == "__main__":
    unittest.main()
