import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.services.system_diagnostics import executar_diagnostico
from app.services.system_diagnostics import verificar_backup
from app.services.system_diagnostics import verificar_jsons
from app.services.system_diagnostics import verificar_sqlite


class SystemDiagnosticsTest(unittest.TestCase):

    def test_detects_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.json"
            path.write_text("{invalid", encoding="utf-8")
            result = verificar_jsons([path])

        self.assertEqual(result[0]["Status"], "Erro")

    def test_sqlite_quick_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rede.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE teste (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            result = verificar_sqlite(path)

        self.assertEqual(result[0]["Status"], "OK")
        self.assertIn("quick_check=ok", result[0]["Detalhe"])

    def test_backup_missing_is_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = verificar_backup(
                Path(temp_dir) / "backups",
                now=datetime(2026, 1, 1),
            )

        self.assertEqual(result[0]["Status"], "Atenção")

    def test_full_diagnostic_reports_required_file_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            valid_json = base / "data.json"
            valid_json.write_text("{}", encoding="utf-8")
            database = base / "rede.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE teste (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            requirements = base / "requirements.txt"
            requirements.write_text("", encoding="utf-8")
            result = executar_diagnostico(
                base_dir=base,
                json_paths=[valid_json],
                database_path=database,
                required=[("SNMPc", base / "SNMPc.txt")],
                backup_dir=base / "backups",
                requirements_path=requirements,
            )

        statuses = {
            (item["Categoria"], item["Item"]): item["Status"]
            for item in result["itens"]
        }
        self.assertEqual(statuses[("Dados", "SNMPc")], "Ausente")


if __name__ == "__main__":
    unittest.main()
