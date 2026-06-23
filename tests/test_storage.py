import json
import stat
import tempfile
import unittest
from pathlib import Path

from app.storage import read_json
from app.storage import write_json_atomic


class StorageTest(unittest.TestCase):

    def test_read_json_retorna_default_para_arquivo_ausente(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ausente.json"

            self.assertEqual(read_json(path, {"ok": True}), {"ok": True})

    def test_write_json_atomic_grava_json_formatado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dados.json"

            write_json_atomic(path, {"nome": "Teste"})

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"nome": "Teste"}
            )

            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode),
                0o600
            )


if __name__ == "__main__":
    unittest.main()
