import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

from app.services import feasibility_history as fh


class FeasibilityHistoryTest(unittest.TestCase):

    def make_workbook(self, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "PreVendas"
        headers = [
            "Cod Projeto",
            "Nome Projeto",
            "Tipo Projeto",
            "STATUS_PRE_VENDA",
            "Obs_Projeto",
            "Data Inicio",
            "PRODUTO",
            "VELOCIDADE PROD",
            "Vlr Mens Total",
            "Vlr Inst Total",
            "GC",
            "Possui Viabilidade",
            "Laudo RF Viab",
            "Justificativa RF Viab",
            "Viabilidade - Caminho",
            "Endereço",
            "Numero",
            "Bairro",
            "Cidade",
            "Estado",
            "Unnamed: 20",
        ]
        sheet.append(["Relatório"])
        sheet.append([])
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def sites(self):
        return {
            "AAA_POP_12345_IP": SimpleNamespace(
                nome="AAA_POP_12345_IP",
                codigo_topos="12345",
                abreviacao="AAA",
                nome_cadastro="Site Alfa",
                tipo="POP",
                status_cadastro="Ativo",
                clientes=[SimpleNamespace(receita=100.0)],
                custo=50.0,
            ),
            "BBB_BH_67890_IP": SimpleNamespace(
                nome="BBB_BH_67890_IP",
                codigo_topos="67890",
                abreviacao="BBB",
                nome_cadastro="Site Beta",
                tipo="BH",
                status_cadastro="Ativo",
                clientes=[],
                custo=20.0,
            ),
        }

    def row(self, **changes):
        row = {
            "Cod Projeto": "9001",
            "Nome Projeto": "Projeto teste",
            "Tipo Projeto": "Nova instalação",
            "STATUS_PRE_VENDA": "Em Andamento",
            "Data Inicio": "2026-07-01",
            "PRODUTO": "Internet",
            "VELOCIDADE PROD": "100 Mbps",
            "Vlr Mens Total": 500,
            "Vlr Inst Total": 1000,
            "GC": "Gerente A",
            "Possui Viabilidade": "SIM",
            "Laudo RF Viab": "Possível atendimento",
            "Justificativa RF Viab": "",
            "Viabilidade - Caminho": "AAA_POP_12345_IP",
            "Endereço": "Rua Teste",
            "Numero": "10",
            "Bairro": "Centro",
            "Cidade": "São Paulo",
            "Estado": "SP",
        }
        row.update(changes)
        return row

    def test_detects_header_and_preserves_identical_rows(self):
        data = self.make_workbook([self.row(), self.row()])
        records = fh.read_feasibility_excel(io.BytesIO(data), self.sites())
        self.assertEqual(len(records), 2)
        self.assertEqual(len({record["ID SGS"] for record in records}), 2)
        self.assertEqual([record["Ocorrência"] for record in records], [1, 2])
        self.assertNotIn("Unnamed: 20", records[0]["Dados Fonte"])

    def test_classification_rules(self):
        direct = {"Possui Viabilidade": "SIM", "Laudo RF Viab": "Possível atendimento"}
        conditional = {"Possui Viabilidade": "SIM", "Laudo RF Viab": "Possível atendimento com repetição"}
        negative = {"Possui Viabilidade": "SIM", "Laudo RF Viab": "Upgrade não viável"}
        pending = {"Possui Viabilidade": "NÃO", "Laudo RF Viab": ""}
        self.assertEqual(fh.classify_feasibility(direct), "Viável direto")
        self.assertEqual(fh.classify_feasibility(conditional), "Viável condicional")
        self.assertEqual(fh.classify_feasibility(negative), "Não viável")
        self.assertEqual(fh.classify_feasibility(pending), "Pendente")

    def test_parses_and_resolves_multiple_paths(self):
        candidates = fh.resolve_candidates(
            "AAA_S1 (AAA_POP_12345_IP) / SITE_67890",
            self.sites(),
        )
        self.assertEqual([item["Site"] for item in candidates], [
            "AAA_POP_12345_IP",
            "BBB_BH_67890_IP",
        ])
        self.assertEqual(candidates[0]["Setorial"], "AAA_S1")
        self.assertEqual(candidates[1]["Método"], "Código Aquiles")

    def test_reimport_does_not_duplicate_and_audits_change(self):
        original = self.make_workbook([self.row()])
        changed = self.make_workbook([self.row(**{"Obs_Projeto": "Nova observação"})])
        with tempfile.TemporaryDirectory() as directory:
            records_file = Path(directory) / "records.json"
            imports_file = Path(directory) / "imports.json"
            revisions_file = Path(directory) / "revisions.json"
            with patch.object(fh, "RECORDS_FILE", records_file), patch.object(
                fh, "IMPORTS_FILE", imports_file
            ), patch.object(fh, "REVISIONS_FILE", revisions_file):
                first = fh.preview_import(original, self.sites(), "one.xlsx", "tester")
                fh.save_import(first)
                second = fh.preview_import(original, self.sites(), "one.xlsx", "tester")
                self.assertEqual(second["batch"]["Inalterados"], 1)
                self.assertEqual(second["batch"]["Novos"], 0)
                third = fh.preview_import(changed, self.sites(), "two.xlsx", "tester")
                self.assertEqual(third["batch"]["Atualizados"], 1)
                self.assertEqual(len(third["revisions"]), 1)

    def test_site_ranking_counts_one_event_per_candidate(self):
        rows = [
            self.row(**{"Viabilidade - Caminho": "AAA_POP_12345_IP / BBB_BH_67890_IP"}),
            self.row(**{
                "Cod Projeto": "9002",
                "Laudo RF Viab": "Inviável",
                "Viabilidade - Caminho": "AAA_POP_12345_IP",
            }),
        ]
        records = fh.read_feasibility_excel(io.BytesIO(self.make_workbook(rows)), self.sites())
        ranking = fh.site_opportunity_ranking(fh.records_dataframe(records, self.sites()), self.sites())
        self.assertEqual(len(ranking), 2)
        self.assertTrue((ranking["Solicitações viáveis"] == 1).all())
        alfa = ranking[ranking["Nome SNMPc"] == "AAA_POP_12345_IP"].iloc[0]
        self.assertEqual(alfa["Clientes atuais"], 1)
        self.assertEqual(alfa["Receita atual"], 100.0)

    def test_records_dataframe_builds_site_indexes_once(self):
        records = fh.read_feasibility_excel(
            io.BytesIO(self.make_workbook([self.row(), self.row()])),
            self.sites(),
        )
        with patch.object(fh, "_site_indexes", wraps=fh._site_indexes) as indexes:
            frame = fh.records_dataframe(records, self.sites())
        self.assertEqual(indexes.call_count, 1)
        self.assertEqual(len(frame), 2)

    def test_records_dataframe_omits_heavy_source_by_default(self):
        records = fh.read_feasibility_excel(
            io.BytesIO(self.make_workbook([self.row()])),
            self.sites(),
        )
        light = fh.records_dataframe(records, self.sites())
        complete = fh.records_dataframe(records, self.sites(), include_source=True)
        self.assertNotIn("Dados Fonte", light.columns)
        self.assertNotIn("Sites Candidatos", light.columns)
        self.assertIn("Dados Fonte", complete.columns)

    def test_site_ranking_preserves_distinct_requests_for_same_project(self):
        records = fh.read_feasibility_excel(
            io.BytesIO(self.make_workbook([self.row(), self.row()])),
            self.sites(),
        )
        ranking = fh.site_opportunity_ranking(
            fh.records_dataframe(records, self.sites()),
            self.sites(),
        )
        self.assertEqual(int(ranking.iloc[0]["Solicitações viáveis"]), 2)

    def test_export_hides_proposal_values_without_permission(self):
        frame = pd.DataFrame([{
            "Projeto": "1",
            "Valor Mensal": 100.0,
            "Valor Instalação": 200.0,
            "Dados Fonte": {
                "Vlr Mens Total": 100.0,
                "Vlr Inst Total": 200.0,
                "Campo adicional": "Preservado",
            },
        }])
        exported = fh.export_records_excel(frame, include_proposal_values=False)
        result = pd.read_excel(io.BytesIO(exported))
        self.assertNotIn("Valor Mensal", result.columns)
        self.assertNotIn("Valor Instalação", result.columns)
        self.assertNotIn("Vlr Mens Total", result.columns)
        self.assertNotIn("Vlr Inst Total", result.columns)
        self.assertEqual(result.iloc[0]["Campo adicional"], "Preservado")


if __name__ == "__main__":
    unittest.main()
