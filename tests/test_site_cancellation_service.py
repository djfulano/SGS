from copy import deepcopy
from datetime import date
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.models.cliente import Cliente
from app.models.site import Site
from app.services import site_cancellation_service as service
from app.ui.views import site_cancellation as cancellation_ui


class SiteCancellationServiceTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "processes.json"

        self.root = Site("ROOT_POP", "POP")
        self.root.codigo_topos = "100"
        self.root.microsiga = "123"
        self.root.nome_cadastro = "Site raiz"
        self.root.status_cadastro = "Ativo"
        self.root.latitude = -23.5000
        self.root.longitude = -46.6000

        self.child = Site("CHILD_BH", "BH")
        self.child.codigo_topos = "101"
        self.child.microsiga = "124"
        self.child.nome_cadastro = "Site filho"
        self.child.status_cadastro = "Ativo"
        self.child.latitude = -23.5100
        self.child.longitude = -46.6000
        self.root.adicionar_filho(self.child)

        self.nearby = Site("OTHER_POP", "POP")
        self.nearby.codigo_topos = "102"
        self.nearby.microsiga = "125"
        self.nearby.nome_cadastro = "Site candidato"
        self.nearby.status_cadastro = "Ativo"
        self.nearby.latitude = -23.5200
        self.nearby.longitude = -46.6000

        client_a = Cliente("Cliente A", 500, "111")
        client_a.produto = "Internet 100M"
        client_a.gerente_contas = "Gerente A"
        client_a.latitude = -23.5000
        client_a.longitude = -46.6000
        self.root.adicionar_cliente(client_a, "ROOT_S1")

        client_b = Cliente("Cliente B", 700, "222")
        client_b.produto = "Internet 200M"
        client_b.gerente_contas = "Gerente B"
        client_b.latitude = -23.5100
        client_b.longitude = -46.6000
        self.child.adicionar_cliente(client_b, "CHILD_S1")
        self.child.adicionar_cliente_adicional(client_a, "CHILD_S2")

        self.sites = {
            self.root.nome: self.root,
            self.child.nome: self.child,
            self.nearby.nome: self.nearby,
        }
        self.equipments = [
            {
                "Site": "ROOT_POP",
                "Assinatura": "111",
                "Icone": "AP",
                "Equipamento": "AP-A",
                "Endereco": "10.0.0.1",
                "Arvore": "ROOT_POP > AP-A",
            },
            {
                "Site": "CHILD_BH",
                "Assinatura": "222",
                "Icone": "ONU",
                "Equipamento": "ONU-B",
                "Endereco": "10.0.0.2",
                "Arvore": "CHILD_BH > ONU-B",
            },
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def create(self, scope="Somente site"):
        with patch.object(
            service, "carregar_clientes_viabilidade", return_value={}
        ), patch.object(
            service, "carregar_cache_geocoding", return_value={}
        ):
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

    def test_legacy_schema_is_deleted_once_without_backup(self):
        self.path.write_text(json.dumps({
            "schema_version": 1,
            "processes": {"old": {"id": "old", "status": "Em andamento"}},
        }), encoding="utf-8")
        backup = self.path.with_name("processes.json.bak")
        backup.write_text("legacy", encoding="utf-8")
        with patch.object(service, "registrar_log_sistema") as log:
            data = service.load_cancellation_processes(self.path)
            second = service.load_cancellation_processes(self.path)
        self.assertEqual(data, {"schema_version": 2, "processes": {}})
        self.assertEqual(second, data)
        self.assertFalse(backup.exists())
        self.assertEqual(log.call_count, 1)
        self.assertEqual(
            log.call_args.kwargs["detalhes"]["processos_removidos"],
            1,
        )

    def test_create_direct_scope_uses_simplified_schema(self):
        process = self.create()
        self.assertEqual(process["status"], "Aberto")
        self.assertEqual(process["site"]["aquiles"], "100")
        self.assertEqual([item["signature"] for item in process["clients"]], ["111"])
        self.assertEqual(process["clients"][0]["equipments"][0]["name"], "AP-A")
        self.assertEqual(
            [item["name"] for item in process["site_activities"]],
            ["Enviar distrato", "Aguardar prazo de aviso", "Retirar equipamentos"],
        )
        self.assertEqual(
            [item["site"] for item in process["clients"][0]["candidate_sites"]],
            ["CHILD_BH", "OTHER_POP"],
        )
        for removed in [
            "phases", "tickets", "links", "financial", "child_sites",
            "extra_tasks", "migration_batch", "equipments",
        ]:
            self.assertNotIn(removed, process)

    def test_tree_scope_deduplicates_clients_and_excludes_scope_candidates(self):
        process = self.create("Site e descendentes")
        self.assertEqual(
            {item["signature"] for item in process["clients"]},
            {"111", "222"},
        )
        client_a = next(item for item in process["clients"] if item["signature"] == "111")
        self.assertEqual(len(client_a["affected_links"]), 2)
        self.assertEqual(
            [item["site"] for item in client_a["candidate_sites"]],
            ["OTHER_POP"],
        )

    def test_only_one_open_process_per_site(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "processo ativo"):
            self.create()

    def test_only_active_site_can_open_process(self):
        self.root.status_cadastro = "Cancelado"
        with self.assertRaisesRegex(ValueError, "Somente sites ativos"):
            self.create()

    def test_missing_client_coordinates_do_not_break_candidate_calculation(self):
        clients = [{
            "signature": "999",
            "address": "",
            "latitude": 0,
            "longitude": 0,
            "current_links": [],
        }]
        result = service.calculate_client_distance_candidates(
            clients,
            self.sites,
            geocoding_cache={},
        )
        self.assertEqual(result[0]["candidate_status"], "Sem coordenadas")
        self.assertEqual(result[0]["candidate_sites"], [])

    def test_candidates_can_be_recalculated(self):
        process = self.create()

        def remove_candidates(item):
            item["clients"][0]["candidate_sites"] = []
            item["clients"][0]["candidate_calculated_at"] = ""

        service.update_cancellation_process(
            process["id"],
            remove_candidates,
            event="test_candidates_removed",
            user="teste",
            path=self.path,
        )
        with patch.object(service, "carregar_cache_geocoding", return_value={}):
            updated = service.recalculate_process_distance_candidates(
                process["id"], self.sites, user="operador", path=self.path
            )
        self.assertTrue(updated["clients"][0]["candidate_calculated_at"])
        self.assertTrue(updated["clients"][0]["candidate_sites"])
        self.assertEqual(updated["history"][-1]["event"], "distance_candidates_recalculated")

    def test_client_update_keeps_single_status_and_is_audited(self):
        process = self.create()
        updated = service.update_client(
            process["id"],
            "111",
            {
                "status": "Migrado",
                "destination_site": "OTHER_POP",
                "notes": "Atividade concluída",
            },
            user="operador",
            path=self.path,
        )
        client = updated["clients"][0]
        self.assertEqual(service.client_process_status(client), "Migrado")
        self.assertEqual(client["destination_site"], "OTHER_POP")
        self.assertEqual(client["updated_by"], "operador")
        self.assertEqual(updated["history"][-1]["event"], "client_updated")
        self.assertNotIn("final_result", client)

    def test_invalid_client_status_is_rejected(self):
        process = self.create()
        with self.assertRaisesRegex(ValueError, "Status do cliente inválido"):
            service.update_client(
                process["id"],
                "111",
                {"status": "Inventado"},
                user="operador",
                path=self.path,
            )

    def test_site_activity_is_updated_and_used_by_completion_check(self):
        process = self.create()
        updated = service.update_site_activity(
            process["id"],
            "send_termination",
            {
                "status": "Concluído",
                "responsible": "juridico",
                "due_date": "2026-08-20",
                "notes": "Distrato enviado",
            },
            user="operador",
            path=self.path,
        )
        activity = next(
            item for item in updated["site_activities"]
            if item["id"] == "send_termination"
        )
        self.assertEqual(activity["status"], "Concluído")
        self.assertTrue(activity["completed_at"])
        self.assertIn(
            "2 atividade(s) do site pendente(s)",
            service.completion_pending_items(updated),
        )

    def test_completion_with_pending_items_requires_justification(self):
        process = self.create()
        with patch.object(service, "_cancel_site_registry"):
            with self.assertRaisesRegex(ValueError, "justificativa"):
                service.complete_process(
                    process["id"], justification="", user="gestor", path=self.path
                )
            completed = service.complete_process(
                process["id"],
                justification="Aprovado com pendências",
                user="gestor",
                path=self.path,
            )
        self.assertEqual(completed["status"], "Concluído")
        with self.assertRaisesRegex(ValueError, "não podem ser alterados"):
            service.update_client(
                process["id"],
                "111",
                {"status": "Migrado"},
                user="operador",
                path=self.path,
            )

    def test_cancel_preserves_data_and_releases_site_for_new_process(self):
        process = self.create()
        with patch.object(service, "_cancel_site_registry") as registry:
            canceled = service.cancel_process(
                process["id"],
                reason="Processo aberto incorretamente",
                user="gestor",
                path=self.path,
            )
        registry.assert_not_called()
        self.assertEqual(canceled["status"], "Cancelado")
        self.assertEqual(canceled["clients"], process["clients"])
        replacement = self.create()
        self.assertNotEqual(replacement["id"], process["id"])

    def test_cancel_requires_reason_and_rejects_completed_process(self):
        process = self.create()
        with self.assertRaisesRegex(ValueError, "justificativa"):
            service.cancel_process(
                process["id"], reason="", user="gestor", path=self.path
            )
        with patch.object(service, "_cancel_site_registry"):
            completed = service.complete_process(
                process["id"],
                justification="Concluir com pendências",
                user="gestor",
                path=self.path,
            )
        with self.assertRaisesRegex(ValueError, "concluídos"):
            service.cancel_process(
                completed["id"],
                reason="Tentativa tardia",
                user="gestor",
                path=self.path,
            )

    def test_cancel_registry_sets_only_main_site_status(self):
        process = self.create()
        registry = pd.DataFrame([{
            column: "" for column in service.SITE_REGISTRY_COLUMNS
        }])
        registry.at[0, "CÓDIGO AQUILES"] = "100"
        registry.at[0, "SMNPC"] = "ROOT_POP"
        registry.at[0, "Status"] = "Ativo"
        with patch.object(
            service, "load_site_registry", return_value=registry
        ), patch.object(service, "upsert_site") as upsert:
            service._cancel_site_registry(process)
        record = upsert.call_args.args[0]
        self.assertEqual(record["Status"], "Cancelado")
        self.assertEqual(upsert.call_args.kwargs["original_code"], "100")

    def test_process_filters_use_three_simplified_statuses(self):
        processes = [
            {"status": "Aberto"},
            {"status": "Concluído"},
            {"status": "Cancelado"},
        ]
        self.assertEqual(len(service.filter_processes_by_scope(processes, "Abertos")), 1)
        self.assertEqual(len(service.filter_processes_by_scope(processes, "Concluídos")), 1)
        self.assertEqual(len(service.filter_processes_by_scope(processes, "Cancelados")), 1)
        self.assertEqual(len(service.filter_processes_by_scope(processes, "Todos")), 3)

    def test_summary_deduplicates_signature_using_latest_activity(self):
        first = self.create()
        second = deepcopy(first)
        second["id"] = "second"
        second["site"] = {**second["site"], "aquiles": "200", "site_name": "SECOND_POP"}
        first["clients"][0]["status"] = "Cancelado"
        first["clients"][0]["updated_at"] = "2026-08-01T10:00:00"
        second["clients"][0]["status"] = "Migrado"
        second["clients"][0]["updated_at"] = "2026-08-02T10:00:00"
        metrics = service.process_metrics([first, second], today=date(2026, 8, 7))
        self.assertEqual(metrics["processes"], 2)
        self.assertEqual(metrics["sites"], 2)
        self.assertEqual(metrics["clients"], 1)
        self.assertEqual(metrics["results"]["Migrados"]["count"], 1)
        self.assertEqual(metrics["results"]["Migrados"]["revenue"], 500.0)
        self.assertEqual(metrics["results"]["Cancelados"]["count"], 0)

    def test_summary_groups_results_and_counts_overdue_site_activities(self):
        process = self.create()
        process["clients"][0]["status"] = "Cancelamento em andamento"
        process["site_activities"][0]["status"] = "Em andamento"
        process["site_activities"][0]["due_date"] = "2026-08-01"
        metrics = service.process_metrics([process], today=date(2026, 8, 7))
        self.assertEqual(metrics["results"]["Em andamento"]["count"], 0)
        self.assertEqual(
            metrics["results"]["Cancelamentos em andamento"]["count"],
            1,
        )
        self.assertEqual(
            metrics["results"]["Cancelamentos em andamento"]["revenue"],
            500.0,
        )
        self.assertEqual(metrics["activity_statuses"]["Em andamento"], 1)
        self.assertEqual(metrics["activity_statuses"]["Não iniciado"], 2)
        self.assertEqual(metrics["overdue_activities"], 1)

    def test_destination_options_prioritize_candidates_and_keep_legacy_value(self):
        process = self.create()
        client_site = Site("CLIENT_SITE", "Cliente")
        client_site.codigo_topos = "103"
        client_site.status_cadastro = "Ativo"
        sites = {**self.sites, client_site.nome: client_site}
        client = process["clients"][0]
        options, labels = cancellation_ui._destination_site_options(
            process,
            sites,
            "LEGACY_SITE",
            client,
        )
        self.assertEqual(options[0], "")
        self.assertEqual(options[1:3], ["CHILD_BH", "OTHER_POP"])
        self.assertNotIn("ROOT_POP", options)
        self.assertNotIn("CLIENT_SITE", options)
        self.assertIn("LEGACY_SITE", options)
        self.assertIn("101", labels["CHILD_BH"])
        self.assertIn("km", labels["CHILD_BH"])


if __name__ == "__main__":
    unittest.main()
