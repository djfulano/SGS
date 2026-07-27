import json
import tempfile
import threading
import unittest
from pathlib import Path

from app.storage import DataFileError
from app.storage import read_json
from app.storage import update_json_atomic
from app.storage import write_json_atomic


class StorageTest(unittest.TestCase):

    def test_strict_read_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"
            path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(DataFileError):
                read_json(path, {}, strict=True)

    def test_authoritative_write_preserves_previous_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"
            write_json_atomic(path, {"version": 1}, backup_previous=True)
            write_json_atomic(path, {"version": 2}, backup_previous=True)

            current = read_json(path, {})
            backup = read_json(path.with_name("data.json.bak"), {})

        self.assertEqual(current, {"version": 2})
        self.assertEqual(backup, {"version": 1})

    def test_concurrent_updates_do_not_lose_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"
            write_json_atomic(path, {"count": 0})

            def increment():
                for _index in range(20):
                    update_json_atomic(
                        path,
                        {"count": 0},
                        lambda data: {
                            **data,
                            "count": data["count"] + 1,
                        },
                    )

            threads = [threading.Thread(target=increment) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            result = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(result["count"], 100)


if __name__ == "__main__":
    unittest.main()
