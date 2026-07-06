from datetime import datetime
from pathlib import Path
import mimetypes
import os
import re
import shutil
import uuid

from app.config import CONTRACTS_DIR
from app.config import CONTRACTS_INDEX_FILE
from app.storage import read_json
from app.storage import write_json_atomic


ALLOWED_CONTRACT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".msg"
}
IGNORED_CONTRACT_FILES = {
    "thumbs.db",
    ".ds_store",
    "desktop.ini"
}
MAX_CONTRACT_SIZE_BYTES = 50 * 1024 * 1024


def normalize_site_code(value):
    text = str(value or "").strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def safe_filename(value):
    text = str(value or "documento").strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE)
    text = text.strip("._")

    return text or "documento"


def unique_destination_path(path):
    path = Path(path)

    if not path.exists():
        return path

    return path.with_name(
        f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{path.suffix}"
    )


def site_contract_dir(site_code, site_name):
    return CONTRACTS_DIR / safe_filename(
        site_code
    )


def site_nome_snmpc(site):
    return str(getattr(site, "nome", "") or "").strip()


def site_codigo_aquiles(site):
    return normalize_site_code(
        getattr(site, "codigo_topos", "")
    )


def sites_documentos_index(sites):
    por_codigo = {}
    por_nome = {}

    for site in (sites or {}).values():
        codigo = site_codigo_aquiles(site)
        nome = site_nome_snmpc(site)

        if codigo:
            por_codigo[safe_filename(codigo)] = site

        if nome:
            por_nome[safe_filename(nome)] = site

    return por_codigo, por_nome


def site_folder_for_code(site_code):
    return CONTRACTS_DIR / safe_filename(
        site_code
    )


def load_contract_index():
    data = read_json(
        CONTRACTS_INDEX_FILE,
        {
            "sites": {}
        }
    )

    if "sites" not in data or not isinstance(data["sites"], dict):
        data["sites"] = {}

    return data


def save_contract_index(data):
    write_json_atomic(
        CONTRACTS_INDEX_FILE,
        data
    )


def list_site_contracts(site_code):
    site_code = normalize_site_code(site_code)
    data = load_contract_index()

    return [
        record
        for record in data.get("sites", {}).get(site_code, [])
        if contract_record_in_current_storage(record)
    ]


def list_site_documents(site_code, archived=False):
    return [
        record
        for record in list_site_contracts(site_code)
        if bool(record.get("archived")) is bool(archived)
    ]


def contract_file_path(record):
    return Path(
        record.get("path") or ""
    )


def contract_record_in_current_storage(record):
    path = contract_file_path(record)

    try:
        resolved_path = path.resolve()
        contracts_root = CONTRACTS_DIR.resolve()
    except OSError:
        return False

    return (
        contracts_root in resolved_path.parents
        or resolved_path == contracts_root
    )


def safe_contract_file_path(record):
    path = contract_file_path(record)

    try:

        resolved_path = path.resolve()
        contracts_root = CONTRACTS_DIR.resolve()

    except OSError:

        return None

    if contracts_root not in resolved_path.parents and resolved_path != contracts_root:

        return None

    return resolved_path


def read_contract_file(record):
    path = safe_contract_file_path(record)

    if not path or not path.exists() or not path.is_file():
        return None

    return path.read_bytes()


def find_contract_record(data, record_id):
    for site_code, records in data.get("sites", {}).items():
        for index, record in enumerate(records):
            if record.get("id") == record_id:
                return site_code, index, record

    return None, None, None


def archive_contract_file(record_id, archived_by=""):
    data = load_contract_index()
    site_code, index, record = find_contract_record(
        data,
        record_id
    )

    if record is None:
        raise ValueError("Documento não encontrado.")

    if record.get("archived"):
        return record

    origem = safe_contract_file_path(record)

    if not origem or not origem.exists() or not origem.is_file():
        raise FileNotFoundError("Arquivo do documento não encontrado.")

    pasta_arquivado = origem.parent / "Arquivado"
    pasta_arquivado.mkdir(
        parents=True,
        exist_ok=True
    )
    destino = pasta_arquivado / origem.name

    if destino.exists():
        destino = pasta_arquivado / (
            f"{origem.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            f"{origem.suffix}"
        )

    shutil.move(
        str(origem),
        str(destino)
    )

    record = {
        **record,
        "path": str(destino),
        "archived": True,
        "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archived_by": str(archived_by or "").strip()
    }
    data["sites"][site_code][index] = record
    save_contract_index(data)

    return record


def restore_archived_contract_file(record_id, restored_by=""):
    data = load_contract_index()
    site_code, index, record = find_contract_record(
        data,
        record_id
    )

    if record is None:
        raise ValueError("Documento não encontrado.")

    if not record.get("archived"):
        raise ValueError("Documento não está arquivado.")

    origem = safe_contract_file_path(record)

    if not origem or not origem.exists() or not origem.is_file():
        raise FileNotFoundError("Arquivo do documento não encontrado.")

    if origem.parent.name.strip().casefold() == "arquivado":
        pasta_destino = origem.parent.parent
    else:
        pasta_destino = origem.parent

    pasta_destino.mkdir(
        parents=True,
        exist_ok=True
    )
    destino = pasta_destino / origem.name

    if destino.exists():
        destino = pasta_destino / (
            f"{origem.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            f"{origem.suffix}"
        )

    shutil.move(
        str(origem),
        str(destino)
    )

    record = {
        **record,
        "path": str(destino),
        "stored_filename": destino.name,
        "archived": False,
        "restored_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "restored_by": str(restored_by or "").strip()
    }
    record.pop("archived_at", None)
    record.pop("archived_by", None)
    data["sites"][site_code][index] = record
    save_contract_index(data)

    return record


def delete_archived_contract_file(record_id):
    data = load_contract_index()
    site_code, index, record = find_contract_record(
        data,
        record_id
    )

    if record is None:
        raise ValueError("Documento não encontrado.")

    if not record.get("archived"):
        raise ValueError("Somente documentos arquivados podem ser excluídos definitivamente.")

    caminho = safe_contract_file_path(record)

    if caminho is None:
        raise ValueError("Caminho do documento inválido.")

    if caminho.exists():
        if not caminho.is_file():
            raise ValueError("Caminho do documento não aponta para um arquivo.")

        caminho.unlink()

    del data["sites"][site_code][index]
    save_contract_index(data)

    return record


def allowed_contract_file(path):
    path = Path(path)

    if path.name.strip().lower() in IGNORED_CONTRACT_FILES:
        return False

    return path.suffix.lower() in ALLOWED_CONTRACT_EXTENSIONS


def _existing_contract_keys(site_versions):
    chaves = set()

    for record in site_versions:
        chaves.add((
            str(record.get("original_filename") or ""),
            int(record.get("size") or 0)
        ))
        path = str(record.get("path") or "")
        if path:
            chaves.add(("path", path))

    return chaves


def _create_contract_record(
    site_code,
    site_name,
    path,
    *,
    version_number,
    uploaded_by="",
    version_label="",
    notes=""
):
    path = Path(path)
    return {
        "id": uuid.uuid4().hex,
        "site_code": normalize_site_code(site_code),
        "site_name": str(site_name or "").strip(),
        "version": version_number,
        "version_label": str(version_label or "").strip(),
        "notes": str(notes or "").strip(),
        "original_filename": path.name,
        "stored_filename": path.name,
        "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size": path.stat().st_size,
        "uploaded_by": str(uploaded_by or "").strip(),
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "path": str(path)
    }


def _contract_file_is_archived(path, site_folder):
    try:
        relative_parts = Path(path).resolve().relative_to(
            Path(site_folder).resolve()
        ).parts
    except ValueError:
        return False

    return any(
        str(part).strip().casefold() == "arquivado"
        for part in relative_parts[:-1]
    )


def index_contract_folders(sites, *, uploaded_by="importacao"):
    data = load_contract_index()
    sites_index = data.setdefault("sites", {})
    for site_code, versions in list(sites_index.items()):
        sites_index[site_code] = [
            record
            for record in versions
            if contract_record_in_current_storage(record)
        ]
    sites_por_codigo, sites_por_snmpc = sites_documentos_index(sites)
    resumo = {
        "sites_encontrados": 0,
        "sites_nao_localizados": [],
        "arquivos_indexados": 0,
        "arquivos_ja_indexados": [],
        "arquivos_ignorados": [],
        "erros": []
    }

    if not CONTRACTS_DIR.exists():
        CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
        return resumo

    for pasta_site in sorted(CONTRACTS_DIR.iterdir()):
        if (
            not pasta_site.is_dir()
            or pasta_site.name.strip().casefold() == "arquivado"
        ):
            continue

        nome_pasta = safe_filename(
            pasta_site.name.strip()
        )
        site = (
            sites_por_codigo.get(nome_pasta)
            or sites_por_snmpc.get(nome_pasta)
        )

        if not site:
            resumo["sites_nao_localizados"].append(pasta_site.name.strip())
            continue

        site_code = site_codigo_aquiles(site)
        nome_snmpc = site_nome_snmpc(site)

        if not site_code:
            resumo["sites_nao_localizados"].append(pasta_site.name.strip())
            continue

        resumo["sites_encontrados"] += 1
        site_versions = sites_index.setdefault(site_code, [])
        existentes = _existing_contract_keys(site_versions)

        for arquivo in sorted(pasta_site.rglob("*")):
            if not arquivo.is_file():
                continue

            try:
                if not allowed_contract_file(arquivo):
                    resumo["arquivos_ignorados"].append(str(arquivo))
                    continue

                tamanho = arquivo.stat().st_size
                chave_nome = (arquivo.name, tamanho)
                chave_path = ("path", str(arquivo))

                if chave_nome in existentes or chave_path in existentes:
                    resumo["arquivos_ja_indexados"].append(str(arquivo))
                    continue

                record = _create_contract_record(
                    site_code,
                    nome_snmpc,
                    arquivo,
                    version_number=len(site_versions) + 1,
                    uploaded_by=uploaded_by,
                    notes=f"Indexado da pasta {pasta_site}"
                )
                if _contract_file_is_archived(
                    arquivo,
                    pasta_site
                ):
                    record["archived"] = True
                    record["archived_at"] = ""
                    record["archived_by"] = "indexacao"

                site_versions.append(record)
                existentes.add(chave_nome)
                existentes.add(chave_path)
                resumo["arquivos_indexados"] += 1
            except Exception as erro:
                resumo["erros"].append({
                    "arquivo": str(arquivo),
                    "erro": str(erro)
                })

    save_contract_index(data)
    return resumo


def _contar_arquivos_pasta_documentos(pasta):
    arquivos = [
        arquivo
        for arquivo in Path(pasta).iterdir()
        if arquivo.is_file()
    ]
    return {
        "Qtd arquivos": len(arquivos),
        "Qtd arquivos válidos": sum(
            1
            for arquivo in arquivos
            if allowed_contract_file(arquivo)
        )
    }


def compare_sites_and_document_folders(sites):
    CONTRACTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )
    pastas = {
        pasta.name.strip(): pasta
        for pasta in CONTRACTS_DIR.iterdir()
        if (
            pasta.is_dir()
            and pasta.name.strip().casefold() != "arquivado"
        )
    }
    sites_por_codigo, sites_por_snmpc = sites_documentos_index(sites)
    sites_sem_pasta = []

    for _chave_codigo, site in sorted(sites_por_codigo.items()):
        codigo = site_codigo_aquiles(site)
        nome_site = site_nome_snmpc(site)
        pasta_codigo = safe_filename(codigo)
        pasta_nome = safe_filename(nome_site)

        if pasta_codigo in pastas or pasta_nome in pastas:
            continue

        sites_sem_pasta.append({
            "Site SNMPc": nome_site,
            "Código Aquiles": codigo,
            "Pasta Esperada": pasta_codigo,
            "Nome Cadastro": getattr(site, "nome_cadastro", ""),
            "Status Cadastro": getattr(site, "status_cadastro", ""),
            "Cidade": getattr(site, "cidade", ""),
            "UF": getattr(site, "uf", "")
        })

    pastas_sem_site = []

    for nome_pasta, pasta in sorted(pastas.items()):
        chave_pasta = safe_filename(nome_pasta)
        site = (
            sites_por_codigo.get(chave_pasta)
            or sites_por_snmpc.get(chave_pasta)
        )

        if site:
            continue

        contagem = _contar_arquivos_pasta_documentos(pasta)
        pastas_sem_site.append({
            "Pasta": nome_pasta,
            "Código Aquiles": "",
            "Site SNMPc": "",
            **contagem,
            "Caminho": str(pasta)
        })

    return sites_sem_pasta, pastas_sem_site


def _migrar_item_documento(origem, destino_base, dry_run):
    origem = Path(origem)
    destino_base = Path(destino_base)
    destino = destino_base / origem.name
    conflito = False

    if destino.exists() and not (origem.is_dir() and destino.is_dir()):
        destino = unique_destination_path(destino)
        conflito = True

    if origem.is_dir():
        if not dry_run:
            destino.mkdir(
                parents=True,
                exist_ok=True
            )
        mapeamentos = []

        for item in sorted(origem.iterdir()):
            _destino_item, _conflito_item, mapeamentos_item = _migrar_item_documento(
                item,
                destino,
                dry_run=dry_run
            )
            mapeamentos.extend(mapeamentos_item)

        if not dry_run:
            try:
                origem.rmdir()
            except OSError:
                pass

        return destino, conflito, mapeamentos

    if not dry_run:
        destino.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        shutil.move(
            str(origem),
            str(destino)
        )

    return destino, conflito, [
        {
            "origem": str(origem),
            "destino": str(destino),
            "conflito": conflito
        }
    ]


def _novo_caminho_migrado(caminho, origem_pasta, destino_pasta):
    caminho = Path(caminho)
    origem_pasta = Path(origem_pasta)
    destino_pasta = Path(destino_pasta)

    try:
        relativo = caminho.resolve().relative_to(
            origem_pasta.resolve()
        )
    except ValueError:
        return None

    return destino_pasta / relativo


def _erro_permissao_documentos(caminho, acao):
    return {
        "caminho": str(caminho),
        "erro": (
            f"Sem permissão para {acao}. Ajuste o dono/permissões da pasta contracts "
            "para o usuário que executa o SGS."
        )
    }


def _erros_permissao_migracao(pasta_origem, pasta_destino):
    pasta_origem = Path(pasta_origem)
    pasta_destino = Path(pasta_destino)
    erros = []

    if not os.access(pasta_origem, os.R_OK | os.W_OK | os.X_OK):
        erros.append(
            _erro_permissao_documentos(
                pasta_origem,
                "ler e mover a pasta de origem"
            )
        )

    destino_base = pasta_destino if pasta_destino.exists() else CONTRACTS_DIR
    if not os.access(destino_base, os.W_OK | os.X_OK):
        erros.append(
            _erro_permissao_documentos(
                destino_base,
                "criar ou alterar a pasta de destino"
            )
        )

    for item in pasta_origem.rglob("*"):
        if item.is_dir():
            if not os.access(item, os.R_OK | os.W_OK | os.X_OK):
                erros.append(
                    _erro_permissao_documentos(
                        item,
                        "ler e mover esta subpasta"
                    )
                )
        elif item.is_file() and not os.access(item, os.R_OK):
            erros.append(
                _erro_permissao_documentos(
                    item,
                    "ler este arquivo"
                )
            )

    return erros


def migrar_pastas_documentos_para_codigo_aquiles(
    sites,
    dry_run=True,
    usuario=""
):
    CONTRACTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )
    data = load_contract_index()
    sites_index = data.setdefault("sites", {})
    resumo = {
        "dry_run": bool(dry_run),
        "pastas_migradas": 0,
        "arquivos_movidos": 0,
        "registros_atualizados": 0,
        "conflitos": [],
        "sites_sem_codigo": [],
        "pastas_nao_localizadas": [],
        "erros": []
    }

    for site in (sites or {}).values():
        codigo = site_codigo_aquiles(site)
        nome_snmpc = site_nome_snmpc(site)

        if not codigo:
            if nome_snmpc:
                resumo["sites_sem_codigo"].append(nome_snmpc)
            continue

        if not nome_snmpc:
            continue

        pasta_origem = CONTRACTS_DIR / safe_filename(nome_snmpc)
        pasta_destino = site_folder_for_code(codigo)

        if pasta_origem == pasta_destino:
            continue

        if not pasta_origem.exists() or not pasta_origem.is_dir():
            continue

        try:
            erros_permissao = _erros_permissao_migracao(
                pasta_origem,
                pasta_destino
            )

            if erros_permissao:
                for erro_permissao in erros_permissao:
                    resumo["erros"].append({
                        "site": nome_snmpc,
                        "codigo": codigo,
                        **erro_permissao
                    })
                continue

            resumo["pastas_migradas"] += 1
            pasta_destino.mkdir(
                parents=True,
                exist_ok=True
            ) if not dry_run else None
            mapeamentos = []

            for item in sorted(pasta_origem.iterdir()):
                try:
                    _destino_item, _conflito, mapeamentos_item = _migrar_item_documento(
                        item,
                        pasta_destino,
                        dry_run=dry_run
                    )
                except PermissionError as erro:
                    resumo["erros"].append({
                        "site": nome_snmpc,
                        "codigo": codigo,
                        "caminho": str(item),
                        "erro": (
                            f"Sem permissão para mover este item: {erro}. "
                            "Ajuste o dono/permissões da pasta contracts."
                        )
                    })
                    continue

                mapeamentos.extend(mapeamentos_item)
                resumo["arquivos_movidos"] += len(mapeamentos_item)

                for mapeamento in mapeamentos_item:
                    if mapeamento.get("conflito"):
                        resumo["conflitos"].append({
                            "origem": mapeamento.get("origem"),
                            "destino": mapeamento.get("destino")
                        })

            if not dry_run:
                try:
                    pasta_origem.rmdir()
                except OSError:
                    pass

            mapeamentos_por_origem = {
                mapeamento["origem"]: mapeamento["destino"]
                for mapeamento in mapeamentos
            }
            site_code = normalize_site_code(codigo)
            for record in sites_index.get(site_code, []):
                caminho_atual = record.get("path") or ""
                novo_caminho = mapeamentos_por_origem.get(caminho_atual)

                if not novo_caminho:
                    novo_caminho = _novo_caminho_migrado(
                        caminho_atual,
                        pasta_origem,
                        pasta_destino
                    )

                if not novo_caminho:
                    continue

                resumo["registros_atualizados"] += 1
                if not dry_run:
                    record["path"] = str(novo_caminho)
                    record["site_name"] = nome_snmpc

        except Exception as erro:
            resumo["erros"].append({
                "site": nome_snmpc,
                "codigo": codigo,
                "erro": str(erro)
            })

    pastas_por_site = {
        safe_filename(site_codigo_aquiles(site))
        for site in (sites or {}).values()
        if site_codigo_aquiles(site)
    } | {
        safe_filename(site_nome_snmpc(site))
        for site in (sites or {}).values()
        if site_nome_snmpc(site)
    }

    for pasta in sorted(CONTRACTS_DIR.iterdir()):
        if (
            pasta.is_dir()
            and pasta.name.strip().casefold() != "arquivado"
            and safe_filename(pasta.name) not in pastas_por_site
        ):
            resumo["pastas_nao_localizadas"].append(pasta.name)

    if not dry_run:
        save_contract_index(data)

    return resumo


def add_site_contract(
    site_code,
    site_name,
    original_filename,
    content,
    *,
    content_type="",
    uploaded_by="",
    version_label="",
    notes=""
):
    site_code = normalize_site_code(site_code)

    if not site_code:
        raise ValueError("Codigo Aquiles do site nao informado.")

    if not content:
        raise ValueError("Arquivo do documento vazio.")

    if len(content) > MAX_CONTRACT_SIZE_BYTES:
        raise ValueError("Arquivo do documento excede o limite de 50 MB.")

    data = load_contract_index()
    site_versions = data.setdefault("sites", {}).setdefault(site_code, [])
    version_number = len(site_versions) + 1
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    original_filename = safe_filename(original_filename)
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_CONTRACT_EXTENSIONS:
        raise ValueError("Tipo de arquivo do documento nao permitido.")

    stored_filename = (
        f"v{version_number:03d}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
        f"{uuid.uuid4().hex[:8]}_"
        f"{original_filename}"
    )
    site_dir = site_contract_dir(
        site_code,
        site_name
    )
    site_dir.mkdir(parents=True, exist_ok=True)
    path = site_dir / stored_filename
    path.write_bytes(content)

    record = {
        "id": uuid.uuid4().hex,
        "site_code": site_code,
        "site_name": str(site_name or "").strip(),
        "version": version_number,
        "version_label": str(version_label or "").strip(),
        "notes": str(notes or "").strip(),
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "content_type": str(content_type or "").strip(),
        "size": len(content),
        "uploaded_by": str(uploaded_by or "").strip(),
        "uploaded_at": uploaded_at,
        "path": str(path)
    }
    site_versions.append(record)
    save_contract_index(data)

    return record
