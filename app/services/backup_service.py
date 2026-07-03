import json
import shutil
import tempfile
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from zipfile import BadZipFile
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

FONTES_RESTAURAVEIS = {
    "imports": {
        "label": "Arquivos importados",
        "type": "directory",
        "path": IMPORTS_DIR
    },
    "config": {
        "label": "Configurações, usuários e logs",
        "type": "directory",
        "path": CONFIG_DIR
    },
    "cache": {
        "label": "Cache",
        "type": "directory",
        "path": CACHE_DIR
    },
    "contracts": {
        "label": "Documentos dos sites",
        "type": "directory",
        "path": CONTRACTS_DIR
    },
    "database": {
        "label": "Banco SQLite",
        "type": "file",
        "path": Path("rede.db")
    }
}


def _backup_dir_oficial():
    return Path(BACKUP_DIR)


def _normalizar_backup_config(config=None):
    config_normalizada = {
        **DEFAULT_BACKUP_CONFIG,
        **(config or {})
    }
    config_normalizada["backup_dir"] = str(_backup_dir_oficial())

    config_normalizada["retention"] = max(
        1,
        int(
            config_normalizada.get("retention")
            or DEFAULT_BACKUP_CONFIG["retention"]
        )
    )

    if config_normalizada.get("frequency") not in FREQUENCIAS_BACKUP:
        config_normalizada["frequency"] = DEFAULT_BACKUP_CONFIG["frequency"]

    return config_normalizada


def load_backup_config(path=None):
    path = path or BACKUP_CONFIG_FILE
    config = read_json(
        path,
        {}
    )

    return _normalizar_backup_config(config)


def save_backup_config(config, path=None):
    path = path or BACKUP_CONFIG_FILE
    config_save = _normalizar_backup_config(config)

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


def _fontes_restauraveis(base):
    return {
        "imports": {
            **FONTES_RESTAURAVEIS["imports"],
            "path": IMPORTS_DIR
        },
        "config": {
            **FONTES_RESTAURAVEIS["config"],
            "path": CONFIG_DIR
        },
        "cache": {
            **FONTES_RESTAURAVEIS["cache"],
            "path": CACHE_DIR
        },
        "contracts": {
            **FONTES_RESTAURAVEIS["contracts"],
            "path": CONTRACTS_DIR
        },
        "database": {
            **FONTES_RESTAURAVEIS["database"],
            "path": base / "rede.db"
        }
    }


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
    config = _normalizar_backup_config(config or load_backup_config())
    base = Path(base_dir or ".").resolve()
    destino_backup = _backup_dir_oficial()
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
    backup_dir = _backup_dir_oficial()

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


def caminho_backup_download(arquivo):
    base_backup = _backup_dir_oficial().resolve()
    caminho = Path(arquivo)

    if not caminho.is_absolute():
        caminho = base_backup / caminho.name

    caminho = caminho.resolve()

    try:
        caminho.relative_to(base_backup)
    except ValueError as erro:
        raise ValueError("Backup fora da pasta oficial de backups.") from erro

    if not caminho.exists() or not caminho.is_file():
        raise FileNotFoundError("Arquivo de backup não encontrado.")

    if caminho.suffix.lower() != ".zip":
        raise ValueError("Somente arquivos ZIP de backup podem ser baixados.")

    return caminho


def read_backup_file(arquivo):
    caminho = caminho_backup_download(arquivo)
    return caminho.read_bytes()


def _entrada_zip_segura(nome):
    nome_normalizado = str(nome).replace("\\", "/")
    caminho = Path(nome_normalizado)

    if (
        not nome_normalizado
        or nome_normalizado.startswith("/")
        or ":" in caminho.parts[0]
    ):
        return False

    return ".." not in caminho.parts


def _fonte_por_entrada(nome):
    nome = str(nome).replace("\\", "/")

    if nome == "rede.db":
        return "database"

    primeiro = Path(nome).parts[0] if Path(nome).parts else ""

    if primeiro in {
        "imports",
        "config",
        "cache",
        "contracts"
    }:
        return primeiro

    return None


def inspecionar_backup(caminho_backup):
    caminho_backup = Path(caminho_backup)

    if not caminho_backup.exists() or not caminho_backup.is_file():
        raise FileNotFoundError("Arquivo de backup não encontrado.")

    fontes = {}
    entradas_invalidas = []
    metadata = {}

    try:
        with ZipFile(caminho_backup) as zip_file:
            for info in zip_file.infolist():
                nome = info.filename

                if not _entrada_zip_segura(nome):
                    entradas_invalidas.append(nome)
                    continue

                if nome == "backup_metadata.json":
                    try:
                        metadata = json.loads(
                            zip_file.read(info).decode("utf-8")
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        metadata = {}
                    continue

                if info.is_dir():
                    continue

                fonte = _fonte_por_entrada(nome)

                if not fonte:
                    continue

                dados = fontes.setdefault(
                    fonte,
                    {
                        "Fonte": FONTES_RESTAURAVEIS[fonte]["label"],
                        "Chave": fonte,
                        "Arquivos": 0,
                        "Tamanho bytes": 0
                    }
                )
                dados["Arquivos"] += 1
                dados["Tamanho bytes"] += int(info.file_size or 0)
    except BadZipFile as erro:
        raise ValueError("Arquivo ZIP inválido.") from erro

    for dados in fontes.values():
        dados["Tamanho"] = formatar_tamanho_bytes(
            dados["Tamanho bytes"]
        )

    return {
        "arquivo": caminho_backup.name,
        "caminho": str(caminho_backup),
        "metadata": metadata,
        "tipo": metadata.get("backup_type") or "desconhecido",
        "versao": metadata.get("version") or "",
        "criado_em": metadata.get("created_at") or "",
        "fontes": sorted(
            fontes.values(),
            key=lambda item: item["Chave"]
        ),
        "fontes_chaves": sorted(fontes.keys()),
        "entradas_invalidas": entradas_invalidas,
        "restauravel": bool(fontes) and not entradas_invalidas
    }


def _extrair_backup_para_temp(caminho_backup, destino_temp):
    with ZipFile(caminho_backup) as zip_file:
        for info in zip_file.infolist():
            nome = info.filename

            if not _entrada_zip_segura(nome):
                raise ValueError(
                    f"Entrada insegura no backup: {nome}"
                )

            if info.is_dir():
                continue

            fonte = _fonte_por_entrada(nome)

            if not fonte and nome != "backup_metadata.json":
                continue

            destino = Path(destino_temp) / nome
            destino.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            with zip_file.open(info) as origem, open(destino, "wb") as saida:
                shutil.copyfileobj(
                    origem,
                    saida
                )


def _copiar_fonte_extraida(origem, destino, tipo):
    origem = Path(origem)
    destino = Path(destino)

    if tipo == "directory":
        if not origem.exists():
            return 0

        destino.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        shutil.copytree(
            origem,
            destino
        )

        return sum(
            1
            for arquivo in destino.rglob("*")
            if arquivo.is_file()
        )

    if not origem.exists():
        return 0

    destino.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    shutil.copy2(
        origem,
        destino
    )

    return 1


def restaurar_backup(
    caminho_backup,
    usuario="",
    restaurar_contracts=False,
    incluir_cache=True,
    base_dir=None,
    criar_backup_previo=True
):
    base = Path(base_dir or ".").resolve()
    caminho_backup = Path(caminho_backup)
    info = inspecionar_backup(caminho_backup)

    if info["entradas_invalidas"]:
        raise ValueError(
            "Backup contém caminhos inseguros e não pode ser restaurado."
        )

    fontes_disponiveis = set(info["fontes_chaves"])
    fontes_desejadas = {
        "imports",
        "config",
        "database"
    }

    if incluir_cache:
        fontes_desejadas.add("cache")

    if restaurar_contracts:
        fontes_desejadas.add("contracts")

    fontes_para_restaurar = sorted(
        fontes_disponiveis & fontes_desejadas
    )

    if not fontes_para_restaurar:
        raise ValueError(
            "Backup não contém nenhuma fonte selecionada para restauração."
        )

    backup_previo = None

    if criar_backup_previo:
        config_pre_restore = {
            **DEFAULT_BACKUP_CONFIG,
            "backup_dir": str(BACKUP_DIR),
            "retention": 9999,
            "include_imports": True,
            "include_config": True,
            "include_cache": True,
            "include_contracts": bool(restaurar_contracts),
            "include_database": True,
            "include_system_files": False
        }
        backup_previo = criar_backup(
            config_pre_restore,
            usuario=usuario,
            motivo="pre_restore",
            base_dir=base
        )

    fontes = _fontes_restauraveis(base)
    restaurados = []
    rollback = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        extraido = temp_dir / "extraido"
        antigos = temp_dir / "antigos"
        extraido.mkdir()
        antigos.mkdir()
        _extrair_backup_para_temp(
            caminho_backup,
            extraido
        )

        try:
            for chave in fontes_para_restaurar:
                fonte = fontes[chave]
                destino = Path(fonte["path"])
                destino_backup = antigos / chave

                if destino.exists():
                    destino_backup.parent.mkdir(
                        parents=True,
                        exist_ok=True
                    )
                    shutil.move(
                        str(destino),
                        str(destino_backup)
                    )
                    rollback.append(
                        (destino_backup, destino)
                    )

                origem = (
                    extraido / "rede.db"
                    if chave == "database"
                    else extraido / chave
                )
                arquivos = _copiar_fonte_extraida(
                    origem,
                    destino,
                    fonte["type"]
                )
                restaurados.append({
                    "key": chave,
                    "label": fonte["label"],
                    "path": str(destino),
                    "files": arquivos
                })
        except Exception:
            for origem_antiga, destino_original in reversed(rollback):
                if destino_original.exists():
                    if destino_original.is_dir():
                        shutil.rmtree(
                            destino_original,
                            ignore_errors=True
                        )
                    else:
                        destino_original.unlink(
                            missing_ok=True
                        )

                if origem_antiga.exists():
                    shutil.move(
                        str(origem_antiga),
                        str(destino_original)
                    )

            raise

    return {
        "backup": str(caminho_backup),
        "backup_previo": backup_previo,
        "fontes_restauradas": restaurados,
        "restaurar_contracts": bool(restaurar_contracts),
        "incluir_cache": bool(incluir_cache)
    }


def limpar_backups_antigos(backup_dir=None, retention=10):
    backup_dir = _backup_dir_oficial()
    backups = listar_backups()
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
    config = _normalizar_backup_config(config or load_backup_config())
    base = Path(base_dir or ".").resolve()
    destino_backup = _backup_dir_oficial()
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
