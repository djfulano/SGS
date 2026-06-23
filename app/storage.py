import json
import os
import tempfile
from pathlib import Path


def read_json(path, default, *, strict=False, error_factory=None):
    path = Path(path)

    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))

    except json.JSONDecodeError as error:
        if strict and error_factory:
            raise error_factory(path) from error

        return default


def write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
        os.chmod(path, 0o600)

    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

        raise
