from datetime import datetime
from pathlib import Path
import mimetypes
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


def site_contract_dir(site_code, site_name):
    name = safe_filename(
        site_name
    )

    if name and name != "documento":

        return CONTRACTS_DIR / name

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


def index_contract_folders(sites, *, uploaded_by="importacao"):
    data = load_contract_index()
    sites_index = data.setdefault("sites", {})
    for site_code, versions in list(sites_index.items()):
        sites_index[site_code] = [
            record
            for record in versions
            if contract_record_in_current_storage(record)
        ]
    sites_por_snmpc = {
        str(getattr(site, "nome", "") or "").strip(): site
        for site in (sites or {}).values()
        if str(getattr(site, "nome", "") or "").strip()
    }
    resumo = {
        "sites_encontrados": 0,
        "sites_nao_localizados": [],
        "arquivos_indexados": 0,
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

        nome_snmpc = pasta_site.name.strip()
        site = sites_por_snmpc.get(nome_snmpc)

        if not site:
            resumo["sites_nao_localizados"].append(nome_snmpc)
            continue

        site_code = normalize_site_code(
            getattr(site, "codigo_topos", "")
        )

        if not site_code:
            resumo["sites_nao_localizados"].append(nome_snmpc)
            continue

        resumo["sites_encontrados"] += 1
        site_versions = sites_index.setdefault(site_code, [])
        existentes = _existing_contract_keys(site_versions)

        for arquivo in sorted(pasta_site.iterdir()):
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
                    resumo["arquivos_ignorados"].append(str(arquivo))
                    continue

                record = _create_contract_record(
                    site_code,
                    nome_snmpc,
                    arquivo,
                    version_number=len(site_versions) + 1,
                    uploaded_by=uploaded_by,
                    notes=f"Indexado da pasta {pasta_site}"
                )
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
    sites_por_snmpc = {
        str(getattr(site, "nome", "") or "").strip(): site
        for site in (sites or {}).values()
        if str(getattr(site, "nome", "") or "").strip()
    }
    sites_sem_pasta = []

    for nome_site, site in sorted(sites_por_snmpc.items()):
        if nome_site in pastas:
            continue

        sites_sem_pasta.append({
            "Site SNMPc": nome_site,
            "Código Aquiles": getattr(site, "codigo_topos", ""),
            "Nome Cadastro": getattr(site, "nome_cadastro", ""),
            "Status Cadastro": getattr(site, "status_cadastro", ""),
            "Cidade": getattr(site, "cidade", ""),
            "UF": getattr(site, "uf", "")
        })

    pastas_sem_site = []

    for nome_pasta, pasta in sorted(pastas.items()):
        if nome_pasta in sites_por_snmpc:
            continue

        contagem = _contar_arquivos_pasta_documentos(pasta)
        pastas_sem_site.append({
            "Pasta": nome_pasta,
            **contagem,
            "Caminho": str(pasta)
        })

    return sites_sem_pasta, pastas_sem_site


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
