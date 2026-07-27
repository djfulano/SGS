import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.backup_service import DEFAULT_BACKUP_CONFIG
from app.services.backup_service import criar_backup
from app.services.backup_service import limpar_backups_antigos


def main():
    parser = argparse.ArgumentParser(description="Backup agendado do SGS")
    parser.add_argument(
        "--documents-only",
        action="store_true",
        help="Inclui somente os documentos dos sites.",
    )
    parser.add_argument(
        "--include-contracts",
        action="store_true",
        help="Inclui documentos junto ao backup completo.",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=14,
        help="Quantidade de backups mais recentes a preservar.",
    )
    args = parser.parse_args()

    if args.documents_only:
        config = {
            **DEFAULT_BACKUP_CONFIG,
            "include_imports": False,
            "include_config": False,
            "include_cache": False,
            "include_contracts": True,
            "include_database": False,
            "include_system_files": False,
        }
        reason = "agendado_documentos"
    else:
        config = {
            **DEFAULT_BACKUP_CONFIG,
            "include_imports": True,
            "include_config": True,
            "include_cache": False,
            "include_contracts": args.include_contracts,
            "include_database": True,
            "include_system_files": True,
        }
        reason = "agendado_sistema"

    result = criar_backup(
        config,
        usuario="systemd",
        motivo=reason,
        persistir_config=False,
    )
    result["removed"] = limpar_backups_antigos(
        retention=max(1, args.retention),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
