import unittest
from unittest.mock import patch

from app.data_history import build_snapshot
from app.data_history import ensure_history_initialized
from app.data_history import indexar_sites_por_predio
from app.data_history import site_renomeado_por_predio
from app.models.site import Site


class DataHistoryTest(unittest.TestCase):

    def test_detecta_renomeacao_por_predio(self):
        new_sites = {
            "VMM_BH_110623_IP": {
                "Predio": "110623"
            }
        }

        self.assertTrue(
            site_renomeado_por_predio(
                "VMM_REP_110623_IP",
                {
                    "Predio": "110623"
                },
                indexar_sites_por_predio(new_sites)
            )
        )

    def test_nao_detecta_renomeacao_sem_predio(self):
        self.assertFalse(
            site_renomeado_por_predio(
                "SITE_ANTIGO",
                {
                    "Predio": ""
                },
                {}
            )
        )

    def test_snapshot_inclui_clientes_da_base_sem_vinculo(self):
        snapshot = build_snapshot(
            {},
            active_clients_base={
                "123": {
                    "Cliente": "Cliente sem site",
                    "Assinatura": "123"
                }
            }
        )

        self.assertIn(
            "123",
            snapshot["active_clients"]
        )

    def test_descarta_cancelados_antigos_sem_snapshot(self):
        site = Site(
            "SITE_A",
            "POP"
        )
        history = {
            "active_sites": {
                "SITE_A": {
                    "Site": "SITE_A"
                }
            },
            "active_clients": {},
            "removed_sites": {},
            "cancelled_clients": {
                "999": {
                    "Cliente": "Legado",
                    "Assinatura": "999"
                }
            },
            "last_import": "2026-06-03"
        }

        with patch(
            "app.data_history.load_history",
            return_value=history
        ), patch(
            "app.data_history.save_history"
        ) as save_history:
            atualizado = ensure_history_initialized(
                {
                    "SITE_A": site
                },
                active_clients_base={
                    "123": {
                        "Cliente": "Atual",
                        "Assinatura": "123"
                    }
                }
            )

        self.assertEqual(
            atualizado["cancelled_clients"],
            {}
        )
        self.assertNotIn(
            "legacy_cancelled_clients",
            atualizado
        )
        self.assertIn(
            "123",
            atualizado["active_clients"]
        )
        save_history.assert_called_once()


if __name__ == "__main__":
    unittest.main()
