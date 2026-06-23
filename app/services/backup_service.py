import json
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED
from zipfile import ZipFile

from app.config import BACKUP_CONFIG_FILE
from app.config import BACKUP_DIR
from app.config import CACHE_DIR
from app.config import CONFIG_DIR
from app.config import CONTRACTS_DIR
from app.config import IMPORTS_DIR
from app.storage import read_json
from app.storage import write_json_atomic
from app.version import get_app_version


FREQUENCIAS_BACKUP = {
    "Diário": timedelta(days=1),
    "Semanal": timedelta(days=7),
    "Mensal": timedelta(days=30)
}

DEFAULT_BACKUP_CONFIG = {
    "enabled": False,
    "frequency": "Diário",
    "backup_dir": str(BACKUP_DIR),
    "retention": 10,
    "include_imports": True,
    "include_config": True,
    "include_cache": False,
    "include_contracts": False,
    "include_database": True,
    "include_system_files": True,
    "last_backup_at": "",
    "last_backup_file": ""
}


def load_backup_config(path=None):
    path = path or BACKUP_CONFIG_FILE
    config = read_json(
        path,
        {}
    )

    return {
        **DEFAULT_BACKUP_CONFIG,
        **config
    }


def save_backup_config(config, path=None):
    path = path or BACKUP_CONFIG_FILE
    config_save = {
        **DEFAULT_BACKUP_CONFIG,
        **(config or {})
    }

    config_save["retention"] = max(
        1,
        int(config_save.get("retention") or DEFAULT_BACKUP_CONFIG["retention"])
    )

    if config_save.get("frequency") not in FREQUENCIAS_BACKUP:
        config_save["frequency"] = DEFAULT_BACKUP_CONFIG["frequency"]

    write_json_atomic(
        path,
        config_save
    )

    return config_save


def _caminho_relativo(caminho, base):
    caminho = Path(caminho)

    try:
        return caminho.resolve().relative_to(base.resolve())
    except ValueError:
        return Path(caminho.name)


def _deve_ignorar(caminho, destino_backup):
    try:
        caminho.resolve().relative_to(destino_backup.resolve())
        return True
    except ValueError:
        return False


def _adicionar_arquivo(zip_file, caminho, base, destino_backup):
    caminho = Path(caminho)

    if not caminho.exists() or _deve_ignorar(caminho, destino_backup):
        return 0

    zip_file.write(
        caminho,
        _caminho_relativo(
            caminho,
            base
        )
    )

    return 1


def _adicionar_diretorio(zip_file, caminho, base, destino_backup):
    caminho = Path(caminho)

    if not caminho.exists() or _deve_ignorar(caminho, destino_backup):
        return 0

    total = 0

    for arquivo in caminho.rglob("*"):
        if not arquivo.is_file() or _deve_ignorar(arquivo, destino_backup):
            continue

        total += _adicionar_arquivo(
            zip_file,
            arquivo,
            base,
            destino_backup
        )

    return total


def _fontes_backup(config, base):
    fontes = []

    if config.get("include_imports"):
        fontes.append(("imports", "Arquivos importados", "diretorio", IMPORTS_DIR))

    if config.get("include_config"):
        fontes.append(("config", "Configurações e logs", "diretorio", CONFIG_DIR))

    if config.get("include_cache"):
        fontes.append(("cache", "Cache", "diretorio", CACHE_DIR))

    if config.get("include_contracts"):
        fontes.append(("contracts", "Documentos dos sites", "diretorio", CONTRACTS_DIR))

    if config.get("include_database"):
        fontes.append(("database", "Banco SQLite", "arquivo", base / "rede.db"))

    if config.get("include_system_files"):
        for nome in [
            "VERSION",
            "CHANGELOG.md",
            "docker-compose.yml",
            "docs/USO.md"
        ]:
            fontes.append(("system_files", "Arquivos de versão e documentação", "arquivo", base / nome))

    return fontes


def _inventariar_arquivo(caminho, destino_backup):
    caminho = Path(caminho)

    if not caminho.exists() or not caminho.is_file() or _deve_ignorar(
        caminho,
        destino_backup
    ):
        return 0, 0

    return 1, caminho.stat().st_size


def _inventariar_diretorio(caminho, destino_backup):
    caminho = Path(caminho)

    if not caminho.exists() or not caminho.is_dir() or _deve_ignorar(
        caminho,
        destino_backup
    ):
        return 0, 0

    arquivos = 0
    tamanho = 0

    for arquivo in caminho.rglob("*"):
        if not arquivo.is_file() or _deve_ignorar(arquivo, destino_backup):
            continue

        arquivos += 1
        tamanho += arquivo.stat().st_size

    return arquivos, tamanho


def formatar_tamanho_bytes(tamanho):
    tamanho = float(tamanho or 0)

    for unidade in ["B", "KB", "MB", "GB", "TB"]:
        if tamanho < 1024 or unidade == "TB":
            return f"{tamanho:.1f} {unidade}"

        tamanho /= 1024

    return f"{tamanho:.1f} TB"


def calcular_fontes_backup(config=None, base_dir=None):
    config = {
        **DEFAULT_BACKUP_CONFIG,
        **(config or load_backup_config())
    }
    base = Path(base_dir or ".").resolve()
    destino_backup = Path(
        config.get("backup_dir") or BACKUP_DIR
    )
    resumo = []

    for chave, rotulo, tipo, caminho in _fontes_backup(
        config,
        base
    ):
        if tipo == "diretorio":
            arquivos, tamanho = _inventariar_diretorio(
                caminho,
                destino_backup
            )
        else:
            arquivos, tamanho = _inventariar_arquivo(
                caminho,
                destino_backup
            )

        resumo.append({
            "Fonte": rotulo,
            "Chave": chave,
            "Tipo": "Diretório" if tipo == "diretorio" else "Arquivo",
            "Caminho": str(caminho),
            "Arquivos": arquivos,
            "Tamanho bytes": tamanho,
            "Tamanho": formatar_tamanho_bytes(tamanho),
            "Incluído": arquivos > 0
        })

    return resumo


def _tipo_backup(config):
    include_contracts = bool(config.get("include_contracts"))
    include_system = any(
        bool(config.get(chave))
        for chave in [
            "include_imports",
            "include_config",
            "include_cache",
            "include_database",
            "include_system_files"
        ]
    )

    if include_contracts and include_system:
        return "completo"

    if include_contracts:
        return "documentos"

    return "sistema"


def listar_backups(backup_dir=None):
    backup_dir = Path(backup_dir or BACKUP_DIR)

    if not backup_dir.exists():
        return []

    backups = []

    for arquivo in backup_dir.glob("sgs_backup_*.zip"):
        stat = arquivo.stat()
        backups.append({
            "Arquivo": arquivo.name,
            "Caminho": str(arquivo),
            "Criado em": datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "Tamanho MB": round(
                stat.st_size / 1024 / 1024,
                2
            )
        })

    return sorted(
        backups,
        key=lambda item: item["Criado em"],
        reverse=True
    )


def limpar_backups_antigos(backup_dir, retention):
    backups = listar_backups(backup_dir)
    removidos = []

    for backup in backups[int(retention):]:
        caminho = Path(backup["Caminho"])

        try:
            caminho.unlink()
            removidos.append(str(caminho))
        except FileNotFoundError:
            continue

    return removidos


def criar_backup(config=None, usuario="", motivo="manual", base_dir=None):
    config = {
        **DEFAULT_BACKUP_CONFIG,
        **(config or load_backup_config())
    }
    base = Path(base_dir or ".").resolve()
    destino_backup = Path(
        config.get("backup_dir") or BACKUP_DIR
    )
    destino_backup.mkdir(
        parents=True,
        exist_ok=True
    )

    agora = datetime.now()
    nome_arquivo = f"sgs_backup_{agora.strftime('%Y%m%d_%H%M%S')}.zip"
    caminho_backup = destino_backup / nome_arquivo
    arquivos = 0

    with ZipFile(
        caminho_backup,
        "w",
        ZIP_DEFLATED,
        strict_timestamps=False
    ) as zip_file:
        fontes_incluidas = []

        for chave, rotulo, tipo, caminho in _fontes_backup(
            config,
            base
        ):
            if tipo == "diretorio":
                adicionados = _adicionar_diretorio(
                    zip_file,
                    caminho,
                    base,
                    destino_backup
                )
            else:
                adicionados = _adicionar_arquivo(
                    zip_file,
                    caminho,
                    base,
                    destino_backup
                )

            arquivos += adicionados

            if adicionados:
                fontes_incluidas.append({
                    "key": chave,
                    "label": rotulo,
                    "path": str(caminho),
                    "files": adicionados
                })

        zip_file.writestr(
            "backup_metadata.json",
            json.dumps(
                {
                    "app": "SGS",
                    "version": get_app_version(),
                    "backup_type": _tipo_backup(config),
                    "created_at": agora.strftime("%Y-%m-%d %H:%M:%S"),
                    "user": usuario,
                    "reason": motivo,
                    "files": arquivos,
                    "sources": fontes_incluidas
                },
                ensure_ascii=False,
                indent=2
            ) + "\n"
        )

    config["last_backup_at"] = agora.strftime("%Y-%m-%d %H:%M:%S")
    config["last_backup_file"] = str(caminho_backup)
    save_backup_config(config)
    removidos = limpar_backups_antigos(
        destino_backup,
        config.get("retention") or DEFAULT_BACKUP_CONFIG["retention"]
    )

    return {
        "path": str(caminho_backup),
        "file": nome_arquivo,
        "files": arquivos,
        "size_mb": round(
            caminho_backup.stat().st_size / 1024 / 1024,
            2
        ),
        "removed": removidos
    }


def deve_executar_backup_automatico(config=None, agora=None):
    config = {
        **DEFAULT_BACKUP_CONFIG,
        **(config or load_backup_config())
    }

    if not config.get("enabled"):
        return False

    ultimo = str(
        config.get("last_backup_at") or ""
    ).strip()

    if not ultimo:
        return True

    try:
        data_ultimo = datetime.strptime(
            ultimo,
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return True

    intervalo = FREQUENCIAS_BACKUP.get(
        config.get("frequency"),
        FREQUENCIAS_BACKUP["Diário"]
    )

    return (agora or datetime.now()) - data_ultimo >= intervalo


def executar_backup_automatico_se_necessario(usuario="sistema"):
    config = load_backup_config()

    if not deve_executar_backup_automatico(config):
        return None

    return criar_backup(
        config,
        usuario=usuario,
        motivo="automatico"
    )
