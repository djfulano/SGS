import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.system_diagnostics import executar_diagnostico


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico operacional do SGS")
    parser.add_argument("--json", action="store_true", help="Exibe o resultado em JSON")
    args = parser.parse_args()
    result = executar_diagnostico()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["itens"]:
            print(
                f"[{item['Status']}] {item['Categoria']} - "
                f"{item['Item']}: {item['Detalhe']}"
            )

    return 0 if result["saudavel"] else 1


if __name__ == "__main__":
    sys.exit(main())
