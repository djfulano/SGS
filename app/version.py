from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_app_version():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()

    except FileNotFoundError:
        return "desconhecida"
