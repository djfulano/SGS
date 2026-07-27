import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.backup_service import inspecionar_backup


def main():
    parser = argparse.ArgumentParser(description="Valida um backup ZIP do SGS")
    parser.add_argument("backup", help="Caminho do arquivo ZIP")
    args = parser.parse_args()
    result = inspecionar_backup(args.backup)

    if not result["restauravel"]:
        raise SystemExit("Backup inválido ou sem fontes restauráveis.")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
