import fcntl
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


class DataFileError(RuntimeError):
    pass


class FileLockTimeout(TimeoutError):
    pass


def _lock_path(path):
    path = Path(path)
    return path.parent / f".{path.name}.lock"


@contextmanager
def file_lock(path, timeout=10):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    lock_file = lock_path.open("a+")
    os.chmod(lock_path, 0o600)
    deadline = time.monotonic() + float(timeout)

    try:
        while True:
            try:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise FileLockTimeout(
                        f"Tempo esgotado aguardando acesso a {path}."
                    )
                time.sleep(0.05)

        yield
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def read_json(path, default, *, strict=False, error_factory=None):
    path = Path(path)

    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        if strict:
            if error_factory:
                raise error_factory(path) from error
            raise DataFileError(f"Arquivo JSON inválido: {path}") from error

        return default


def read_json_authoritative(path, default, *, error_factory=None):
    return read_json(
        path,
        default,
        strict=True,
        error_factory=error_factory,
    )


def _fsync_directory(directory):
    descriptor = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic_unlocked(path, data, *, backup_previous=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    backup_path = path.with_name(f"{path.name}.bak")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # Validate the exact representation before replacing authoritative data.
        with open(temp_name, encoding="utf-8") as temp_file:
            json.load(temp_file)

        os.chmod(temp_name, 0o600)

        if backup_previous and path.exists():
            backup_temp = backup_path.with_name(f".{backup_path.name}.tmp")
            shutil.copy2(path, backup_temp)
            os.chmod(backup_temp, 0o600)
            os.replace(backup_temp, backup_path)

        os.replace(temp_name, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def write_json_atomic(
    path,
    data,
    *,
    backup_previous=False,
    timeout=10,
):
    with file_lock(path, timeout=timeout):
        _write_json_atomic_unlocked(
            path,
            data,
            backup_previous=backup_previous,
        )


def update_json_atomic(
    path,
    default,
    updater,
    *,
    authoritative=True,
    backup_previous=True,
    timeout=10,
):
    path = Path(path)

    with file_lock(path, timeout=timeout):
        current = read_json(
            path,
            default,
            strict=authoritative,
        )
        updated = updater(current)

        if updated is None:
            updated = current

        _write_json_atomic_unlocked(
            path,
            updated,
            backup_previous=backup_previous,
        )

    return updated
