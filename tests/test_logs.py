import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.logs import carregar_log
from app.logs import registrar_log


class LogsTest(unittest.TestCase):

    def test_log_is_flushed_and_readable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "system.jsonl"
            registrar_log(path, "teste", usuario="ana", detalhes={"ok": True})
            records = carregar_log(path)

        self.assertEqual(records[0]["evento"], "teste")
        self.assertEqual(records[0]["detalhes"], {"ok": True})

    def test_log_rotates_and_keeps_current_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "system.jsonl"
            path.write_text("x" * 20, encoding="utf-8")
            with patch("app.logs.LOG_MAX_BYTES", 10):
                registrar_log(path, "apos_rotacao")

            records = carregar_log(path)
            rotated = path.with_name("system.jsonl.1")
            rotated_exists = rotated.exists()

        self.assertTrue(rotated_exists)
        self.assertEqual(records[0]["evento"], "apos_rotacao")


if __name__ == "__main__":
    unittest.main()
