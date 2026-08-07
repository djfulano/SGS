import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.services import site_cancellation_service as service


def financial_history(*_args, **_kwargs):
    return {
        "microsiga": "000123",
        "valor_em_atraso": 100.0,
        "parcelas_vencidas": 1,
        "valor_futuro": 200.0,
        "parcelas_futuras": 2,
        "valor_acordos_abertos": 300.0,
        "quantidade_acordos_abertos": 1,
        "vencidas": pd.DataFrame([{"ID SGS": "P1", "Subtotal": 100.0}]),
        "futuras": pd.DataFrame(),
        "acordos_abertos": pd.DataFrame(),
    }


class SiteCancellationServiceTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "processes.json"
        self.root = Site("ROOT_POP", "POP")
        self.root.codigo_topos = "100"
        self.root.microsiga = "123"
        self.root.nome_cadastro = "Site raiz"
        self.root.status_cadastro = "Ativo"
        self.root.custo = 1000.0
        self.child = Site("CHILD_BH", "BH")
        self.child.codigo_topos = "101"
        self.child.microsiga = "124"
        self.child.nome_cadastro = "Site filho"
        self.child.status_cadastro = "Ativo"
        self.root.adicionar_filho(self.child)

        client_a = Cliente("Cliente A", 500, "111")
        client_a.produto = "Internet 100M"
        self.root.adicionar_cliente(client_a, "ROOT_S1")
        client_b = Cliente("Cliente B", 700, "222")
        self.child.adicionar_cliente(client_b, "CHILD_S1")
        self.child.adicionar_cliente_adicional(client_a, "CHILD_S2")
        self.sites = {self.root.nome: self.root, self.child.nome: self.child}
        self.equipments = [
            {"Site": "ROOT_POP", "Assinatura": "111", "Icone": "AP", "Equipamento": "AP-A", "Endereco": "10.0.0.1", "Arvore": "ROOT_POP > AP-A"},
            {"Site": "CHILD_BH", "Assinatura": "222", "Icone": "ONU", "Equipamento": "ONU-B", "Endereco": "10.0.0.2", "Arvore": "CHILD_BH > ONU-B"},
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def create(self, scope="Somente site"):
        with patch.object(service, "historico_financeiro_site", side_effect=financial_history):
            return service.create_cancellation_process(
                self.root,
                self.sites,
                self.equipments,
                scope=scope,
                reason="Redução de custos",
                priority="Alta",
                planned_date=date(2026, 9, 1),
                responsible="operador",
                team="Operações",
                user="master",
                path=self.path,
            )

    def test_create_direct_scope(self):
        process = self.create()
        self.assertEqual(process["site"]["aquiles"], "100")
        self.assertEqual([item["signature"] for item in process["clients"]], ["111"])
        self.assertEqual(len(process["equipments"]), 1)
        self.assertEqual(process["financial"]["overdue_value"], 100.0)
        self.assertEqual(len(process["phases"]), 6)

    def test_tree_scope_deduplicates_clients_and_includes_children(self):
        process = self.create("Site e descendentes")
        self.assertEqual({item["signature"] for item in process["clients"]}, {"111", "222"})
        self.assertEqual(len(process["child_sites"]), 1)
        self.assertEqual(len(process["equipments"]), 2)
        client_a = next(item for item in process["clients"] if item["signature"] == "111")
        self.assertEqual(len(client_a["affected_links"]), 2)

    def test_only_one_active_process_per_site(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "processo ativo"):
            self.create()

    def test_only_active_site_can_open_process(self):
        self.root.status_cadastro = "Cancelado"
        with self.assertRaisesRegex(ValueError, "Somente sites ativos"):
            self.create()

    def test_study_result_is_persisted_and_audited(self):
        process = self.create()
        updated = service.save_migration_study(
            process["id"], "111",
            [{"Site": "OTHER_POP", "Status": "Livre", "Distância km": 2.0}],
            "Migrável", "", user="engenheiro", path=self.path,
        )
        client = updated["clients"][0]
        self.assertEqual(client["study_status"], "Migrável")
        self.assertEqual(client["stage"], "Estudo concluído")
        self.assertEqual(updated["migration_batch"]["processed"], 1)
        self.assertEqual(updated["history"][-1]["event"], "migration_study_saved")

    def test_reconciliation_preserves_missing_and_adds_new(self):
        process = self.create()
        self.root.clientes.clear()
        self.root.adicionar_cliente(Cliente("Cliente C", 900, "333"))
        reconciled = service.reconcile_process(
            process["id"], self.sites, self.equipments,
            user="operador", path=self.path,
        )
        clients = {item["signature"]: item for item in reconciled["clients"]}
        self.assertEqual(clients["111"]["current_state"], "Ausente da base atual")
        self.assertEqual(clients["333"]["current_state"], "Atual")

    def test_completion_with_pending_items_requires_justification(self):
        process = self.create()
        with patch.object(service, "_cancel_site_registry"):
            with self.assertRaisesRegex(ValueError, "justificativa"):
                service.complete_process(process["id"], justification="", user="gestor", path=self.path)
            completed = service.complete_process(
                process["id"], justification="Aprovado com pendências", user="gestor", path=self.path
            )
        self.assertEqual(completed["status"], "Concluído")
        reopened = service.reopen_process(
            process["id"], justification="Nova pendência", user="gestor", path=self.path
        )
        self.assertEqual(reopened["status"], "Em andamento")
        self.assertEqual(reopened["history"][-1]["event"], "process_reopened")

    def test_reopen_blocks_second_active_process_for_same_site(self):
        first = self.create()
        with patch.object(service, "_cancel_site_registry"):
            service.complete_process(
                first["id"], justification="Aprovado", user="gestor", path=self.path
            )
        second = self.create()
        self.assertNotEqual(first["id"], second["id"])
        with self.assertRaisesRegex(ValueError, "outro processo ativo"):
            service.reopen_process(
                first["id"], justification="Reabrir", user="gestor", path=self.path
            )

    def test_cancel_registry_sets_only_main_site_status(self):
        process = self.create()
        registry = pd.DataFrame([{
            column: "" for column in service.SITE_REGISTRY_COLUMNS
        }])
        registry.at[0, "CÓDIGO AQUILES"] = "100"
        registry.at[0, "SMNPC"] = "ROOT_POP"
        registry.at[0, "Status"] = "Ativo"
        with patch.object(service, "load_site_registry", return_value=registry), patch.object(
            service, "upsert_site"
        ) as upsert:
            service._cancel_site_registry(process)
        record = upsert.call_args.args[0]
        self.assertEqual(record["Status"], "Cancelado")
        self.assertEqual(upsert.call_args.kwargs["original_code"], "100")

    def test_agenda_metrics_email_and_excel(self):
        process = self.create()
        service.update_phase(
            process["id"], "planejamento",
            {"due_date": "2026-08-01", "status": "Em andamento"},
            user="operador", path=self.path,
        )
        current = service.get_cancellation_process(process["id"], self.path)
        agenda = service.agenda_items([current], today=date(2026, 8, 7))
        self.assertEqual(agenda[0]["situation"], "Atrasado")
        metrics = service.process_metrics([current], today=date(2026, 8, 7))
        self.assertEqual(metrics["overdue_activities"], 1)
        self.assertIn("Cliente A", service.cancellation_email_text(current))
        self.assertTrue(service.export_cancellation_excel(current).startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
