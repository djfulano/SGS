from __future__ import annotations

import hashlib
import io
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app.config import CONFIG_DIR
from app.storage import read_json
from app.storage import write_json_atomic


FEASIBILITY_HISTORY_DIR = CONFIG_DIR / "feasibility_history"
RECORDS_FILE = FEASIBILITY_HISTORY_DIR / "records.json"
IMPORTS_FILE = FEASIBILITY_HISTORY_DIR / "imports.json"
REVISIONS_FILE = FEASIBILITY_HISTORY_DIR / "revisions.json"

CLASSIFICACOES = [
    "Viável direto",
    "Viável condicional",
    "Não viável",
    "Pendente",
]

PROPOSAL_VALUE_COLUMNS = {"Valor Mensal", "Valor Instalação"}
AUDIT_FIELDS = {
    "Importado em",
    "Importado por",
    "Atualizado em",
    "Lote importação",
    "Linha Excel",
    "Sites Candidatos",
}

PRODUCT_FIELDS = [
    ("PRODUTO", "VELOCIDADE PROD"),
    ("VPN", "VELOCIDADE VPN"),
    ("VPN VOIP", "VELOCIDADE VPN VOIP"),
    ("INTERNET", "VELOCIDADE INTERNET"),
    ("INTERNET VOIP", "VELOCIDADE INTERNET VOIP"),
    ("PRODUTO AGRG01", ""),
    ("PRODUTO AGRG02", ""),
]


def _text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _number(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 0.0 if pd.isna(value) else float(value)
    text = _text(value).replace("R$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    result = pd.to_numeric(text, errors="coerce")
    return 0.0 if pd.isna(result) else float(result)


def _date(value):
    if value is None or value == "":
        return ""
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return _text(value)
    return parsed.date().isoformat()


def _json_value(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return _date(value)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return int(value) if value.is_integer() else float(value)
    if isinstance(value, (int, bool)):
        return value
    return _text(value)


def normalize_text(value):
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def detect_header_row(source, sheet_name="PreVendas"):
    preview = pd.read_excel(
        source,
        sheet_name=sheet_name,
        header=None,
        nrows=30,
        dtype=object,
        engine="openpyxl",
    )
    for index, row in preview.iterrows():
        if any(normalize_text(value) == "COD_PROJETO" for value in row.tolist()):
            return int(index)
    raise ValueError("Cabeçalho com a coluna 'Cod Projeto' não encontrado.")


def _unique_columns(columns):
    result = []
    used = Counter()
    for value in columns:
        name = _text(value)
        if not name or normalize_text(name).startswith("UNNAMED"):
            result.append("")
            continue
        used[name] += 1
        result.append(name if used[name] == 1 else f"{name} {used[name]}")
    return result


def _products(source_data):
    products = []
    seen = set()
    for product_field, speed_field in PRODUCT_FIELDS:
        product = _text(source_data.get(product_field))
        speed = _text(source_data.get(speed_field)) if speed_field else ""
        if not product:
            continue
        label = f"{product} - {speed}" if speed else product
        key = normalize_text(label)
        if key and key not in seen:
            products.append(label)
            seen.add(key)
    return products


def _address(source_data):
    parts = [
        _text(source_data.get("Endereço")),
        _text(source_data.get("Numero")),
        _text(source_data.get("Bairro")),
        _text(source_data.get("Cidade")),
        _text(source_data.get("Estado")),
        _text(source_data.get("CEP")),
    ]
    return ", ".join(part for part in parts if part)


def classify_feasibility(source_data):
    has_feasibility = normalize_text(source_data.get("Possui Viabilidade"))
    report = normalize_text(source_data.get("Laudo RF Viab"))

    if has_feasibility not in {"SIM", "S", "YES"} or not report:
        return "Pendente"
    if any(term in report for term in [
        "NAO_VIAVEL",
        "INVIAVEL",
        "FORA_DA_AREA",
        "CANCELADO",
    ]):
        return "Não viável"
    if any(term in report for term in ["REPETICAO", "CUSTO_ADICIONAL", "VISTORIA"]):
        return "Viável condicional"
    if any(term in report for term in [
        "POSSIVEL_ATENDIMENTO",
        "COM_ATENDIMENTO",
        "UPGRADE_VIAVEL",
        "DOWNGRADE_VIAVEL",
    ]):
        return "Viável direto"
    return "Pendente"


def feasibility_conditions(source_data):
    combined = normalize_text(" ".join(_text(source_data.get(field)) for field in [
        "Laudo RF Viab",
        "Justificativa RF Viab",
        "OBS Viab",
        "Obs Cotacao",
    ]))
    conditions = []
    if "REPETICAO" in combined:
        conditions.append("Repetição")
    if "CUSTO_ADICIONAL" in combined:
        conditions.append("Custo adicional")
    if "VISTORIA" in combined:
        conditions.append("Vistoria")
    return conditions


def parse_site_path(path):
    tokens = []
    for raw in re.split(r"\s*/\s*", _text(path)):
        raw = raw.strip()
        if not raw:
            continue
        matches = re.findall(r"\(([^()]*)\)", raw)
        technical = matches[-1].strip() if matches else raw
        sector = raw[:raw.rfind("(")].strip() if matches else ""
        tokens.append({
            "Caminho original": raw,
            "Referência site": technical,
            "Setorial": sector,
        })
    return tokens


def _site_indexes(sites):
    by_name = {}
    by_code = {}
    by_abbreviation = {}
    for site in (sites or {}).values():
        name = normalize_text(getattr(site, "nome", ""))
        code = re.sub(r"\D", "", _text(getattr(site, "codigo_topos", "")))
        abbreviation = normalize_text(getattr(site, "abreviacao", ""))
        if name:
            by_name.setdefault(name, site)
        if code:
            by_code.setdefault(code.lstrip("0") or "0", site)
        if abbreviation:
            by_abbreviation.setdefault(abbreviation, site)
    return by_name, by_code, by_abbreviation


def resolve_site_reference(reference, sites):
    by_name, by_code, by_abbreviation = _site_indexes(sites)
    normalized = normalize_text(reference)
    site = by_name.get(normalized)
    method = "Nome SNMPc" if site else ""

    if not site:
        codes = re.findall(r"(?<!\d)(\d{4,})(?!\d)", _text(reference))
        for code in reversed(codes):
            site = by_code.get(code.lstrip("0") or "0")
            if site:
                method = "Código Aquiles"
                break

    if not site:
        candidates = [normalized]
        candidates.extend(part for part in normalized.split("_") if part)
        for candidate in candidates:
            site = by_abbreviation.get(candidate)
            if site:
                method = "Abreviação"
                break

    if not site:
        return None
    return {
        "Site": _text(getattr(site, "nome", "")),
        "Código Aquiles": _text(getattr(site, "codigo_topos", "")),
        "Nome": _text(getattr(site, "nome_cadastro", "")),
        "Método": method,
    }


def resolve_candidates(path, sites):
    result = []
    seen = set()
    for token in parse_site_path(path):
        resolved = resolve_site_reference(token["Referência site"], sites)
        item = dict(token)
        item.update(resolved or {
            "Site": "",
            "Código Aquiles": "",
            "Nome": "",
            "Método": "Não localizado",
        })
        key = (
            normalize_text(item.get("Site") or item.get("Referência site")),
            normalize_text(item.get("Setorial")),
        )
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _identity_key(record):
    products = record.get("Produtos") or []
    parts = [
        record.get("Projeto"),
        record.get("Data Início"),
        record.get("Endereço Completo"),
        "|".join(products),
    ]
    return "|".join(normalize_text(part) for part in parts)


def _stable_id(identity, occurrence):
    digest = hashlib.sha1(f"{identity}|{occurrence}".encode("utf-8")).hexdigest()[:18]
    return f"VIA-{digest}"


def read_feasibility_excel(source, sites=None, return_stats=False):
    excel = pd.ExcelFile(source, engine="openpyxl")
    try:
        if "PreVendas" not in excel.sheet_names:
            raise ValueError("Aba 'PreVendas' não encontrada.")
        header = detect_header_row(excel, "PreVendas")
        frame = pd.read_excel(
            excel,
            sheet_name="PreVendas",
            header=header,
            dtype=object,
        )
    finally:
        excel.close()

    columns = _unique_columns(frame.columns)
    useful_positions = [index for index, name in enumerate(columns) if name]
    frame = frame.iloc[:, useful_positions].copy()
    frame.columns = [columns[index] for index in useful_positions]
    if "Cod Projeto" not in frame.columns:
        raise ValueError("Coluna obrigatória 'Cod Projeto' não encontrada.")

    records = []
    invalid_rows = 0
    occurrences = Counter()
    for index, row in frame.iterrows():
        source_data = {column: _json_value(row.get(column)) for column in frame.columns}
        project = _text(source_data.get("Cod Projeto"))
        if not project:
            if any(_text(value) for value in source_data.values()):
                invalid_rows += 1
            continue
        products = _products(source_data)
        record = {
            "Projeto": project,
            "Nome Projeto": _text(source_data.get("Nome Projeto")),
            "Tipo Projeto": _text(source_data.get("Tipo Projeto")),
            "Status Projeto": _text(source_data.get("STATUS_PRE_VENDA")),
            "Data Início": _date(source_data.get("Data Inicio")),
            "Data Conclusão": _date(source_data.get("DATA CONCLUSAO")),
            "Período Contratar": _text(source_data.get("Periodo Contratar")),
            "Gerente de Contas": _text(source_data.get("GC")),
            "Responsável": _text(source_data.get("Responsavel Projeto")),
            "Produtos": products,
            "Produtos Texto": "; ".join(products),
            "Valor Mensal": _number(source_data.get("Vlr Mens Total")),
            "Valor Instalação": _number(source_data.get("Vlr Inst Total")),
            "Endereço Completo": _address(source_data),
            "Endereço": _text(source_data.get("Endereço")),
            "Número": _text(source_data.get("Numero")),
            "Bairro": _text(source_data.get("Bairro")),
            "Cidade": _text(source_data.get("Cidade")),
            "Estado": _text(source_data.get("Estado")),
            "CEP": _text(source_data.get("CEP")),
            "Possui Visada": _text(source_data.get("Possui Visada")),
            "Status Visada": _text(source_data.get("Status Visada")),
            "Possui Viabilidade": _text(source_data.get("Possui Viabilidade")),
            "Laudo RF Visada": _text(source_data.get("Laudo RF Visada")),
            "Laudo RF Viabilidade": _text(source_data.get("Laudo RF Viab")),
            "Justificativa RF": _text(source_data.get("Justificativa RF Viab")),
            "Observação Viabilidade": _text(source_data.get("OBS Viab")),
            "Observação Projeto": _text(source_data.get("Obs_Projeto")),
            "Observação Chamado": _text(source_data.get("Obs_Chamado")),
            "Observação Cotação": _text(source_data.get("Obs Cotacao")),
            "Caminho": _text(source_data.get("Viabilidade - Caminho")),
            "Classificação": classify_feasibility(source_data),
            "Condições": feasibility_conditions(source_data),
            "Dados Fonte": source_data,
            "Linha Excel": int(index) + header + 2,
        }
        record["Sites Candidatos"] = resolve_candidates(record["Caminho"], sites)
        identity = _identity_key(record)
        occurrences[identity] += 1
        record["Ocorrência"] = occurrences[identity]
        record["ID SGS"] = _stable_id(identity, record["Ocorrência"])
        records.append(record)
    if return_stats:
        return records, {"invalid_rows": invalid_rows}
    return records


def load_records():
    return read_json(RECORDS_FILE, [])


def load_imports():
    return read_json(IMPORTS_FILE, [])


def load_revisions():
    return read_json(REVISIONS_FILE, [])


def _comparable(record):
    return {key: value for key, value in record.items() if key not in AUDIT_FIELDS}


def preview_import(source, sites=None, filename="", user=""):
    content = source.getvalue() if hasattr(source, "getvalue") else None
    if content is None and isinstance(source, (bytes, bytearray)):
        content = bytes(source)
    read_source = io.BytesIO(content) if content is not None else source
    records, read_stats = read_feasibility_excel(
        read_source,
        sites=sites,
        return_stats=True,
    )
    existing = {record.get("ID SGS"): record for record in load_records()}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    digest = hashlib.sha256(content).hexdigest() if content is not None else ""
    batch_id = (
        f"IMP-VIA-{datetime.now():%Y%m%d%H%M%S%f}-"
        f"{digest[:8] or hashlib.sha1(now.encode()).hexdigest()[:8]}"
    )
    new_count = updated_count = unchanged_count = 0
    revisions = []
    merged = dict(existing)

    for record in records:
        record = dict(record)
        record["Importado por"] = user or ""
        record["Lote importação"] = batch_id
        current = existing.get(record["ID SGS"])
        if current is None:
            record["Importado em"] = now
            record["Atualizado em"] = now
            merged[record["ID SGS"]] = record
            new_count += 1
            continue
        record["Importado em"] = current.get("Importado em", now)
        record["Atualizado em"] = current.get("Atualizado em", now)
        before = _comparable(current)
        after = _comparable(record)
        if before == after:
            unchanged_count += 1
            continue
        changes = {
            key: {"anterior": before.get(key), "novo": after.get(key)}
            for key in sorted(set(before) | set(after))
            if before.get(key) != after.get(key)
        }
        record["Atualizado em"] = now
        merged[record["ID SGS"]] = record
        updated_count += 1
        revisions.append({
            "ID SGS": record["ID SGS"],
            "Lote importação": batch_id,
            "Alterado em": now,
            "Alterado por": user or "",
            "Alterações": changes,
        })

    classifications = Counter(record.get("Classificação") for record in records)
    localized = sum(
        1 for record in records
        for candidate in record.get("Sites Candidatos", [])
        if candidate.get("Site")
    )
    unresolved = sum(
        1 for record in records
        for candidate in record.get("Sites Candidatos", [])
        if not candidate.get("Site")
    )
    valid_dates = [record.get("Data Início") for record in records if record.get("Data Início")]
    batch = {
        "ID": batch_id,
        "Arquivo": filename or getattr(source, "name", ""),
        "Hash SHA256": digest,
        "Importado em": now,
        "Importado por": user or "",
        "Período inicial": min(valid_dates) if valid_dates else "",
        "Período final": max(valid_dates) if valid_dates else "",
        "Linhas lidas": len(records),
        "Novos": new_count,
        "Atualizados": updated_count,
        "Inalterados": unchanged_count,
        "Inválidos": read_stats["invalid_rows"],
        "Viáveis diretos": classifications["Viável direto"],
        "Viáveis condicionais": classifications["Viável condicional"],
        "Não viáveis": classifications["Não viável"],
        "Pendentes": classifications["Pendente"],
        "Caminhos localizados": localized,
        "Caminhos não localizados": unresolved,
    }
    return {
        "records": records,
        "merged_records": list(merged.values()),
        "revisions": revisions,
        "batch": batch,
    }


def save_import(preview):
    write_json_atomic(RECORDS_FILE, preview["merged_records"])
    imports = load_imports()
    batch_id = preview["batch"].get("ID")
    imports = [item for item in imports if item.get("ID") != batch_id]
    imports.append(preview["batch"])
    write_json_atomic(IMPORTS_FILE, imports)
    revisions = load_revisions()
    revisions.extend(preview.get("revisions", []))
    write_json_atomic(REVISIONS_FILE, revisions)
    return preview["batch"]


def records_dataframe(records=None, sites=None):
    rows = []
    for stored in records if records is not None else load_records():
        record = dict(stored)
        candidates = resolve_candidates(record.get("Caminho", ""), sites)
        record["Sites Candidatos"] = candidates
        record["Sites candidatos"] = "; ".join(
            candidate.get("Site") or candidate.get("Referência site", "")
            for candidate in candidates
        )
        record["Sites localizados"] = "; ".join(
            candidate.get("Site", "") for candidate in candidates if candidate.get("Site")
        )
        record["Caminhos não localizados"] = "; ".join(
            candidate.get("Referência site", "")
            for candidate in candidates if not candidate.get("Site")
        )
        record["Condições"] = "; ".join(record.get("Condições") or [])
        record["Produtos"] = "; ".join(record.get("Produtos") or [])
        rows.append(record)
    return pd.DataFrame(rows)


def site_opportunity_ranking(df, sites):
    columns = [
        "Nome",
        "Nome SNMPc",
        "Tipo",
        "Status",
        "Solicitações viáveis",
        "Viáveis diretas",
        "Condicionais",
        "Projetos distintos",
        "Clientes atuais",
        "Receita atual",
        "Custo atual",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    viable = df[df["Classificação"].isin(["Viável direto", "Viável condicional"])]
    events = []
    for _, record in viable.iterrows():
        candidates = record.get("Sites Candidatos") or resolve_candidates(record.get("Caminho"), sites)
        seen = set()
        for candidate in candidates:
            site_name = candidate.get("Site")
            if not site_name or site_name in seen:
                continue
            seen.add(site_name)
            events.append({
                "Nome SNMPc": site_name,
                "Classificação": record.get("Classificação"),
                "Projeto": record.get("Projeto"),
            })
    if not events:
        return pd.DataFrame(columns=columns)

    events_df = pd.DataFrame(events)
    grouped = events_df.groupby("Nome SNMPc", as_index=False).agg(
        **{
            "Solicitações viáveis": ("Nome SNMPc", "size"),
            "Projetos distintos": ("Projeto", "nunique"),
        }
    )
    grouped["Viáveis diretas"] = grouped["Nome SNMPc"].map(
        events_df[events_df["Classificação"] == "Viável direto"].groupby("Nome SNMPc").size()
    ).fillna(0).astype(int)
    grouped["Condicionais"] = grouped["Nome SNMPc"].map(
        events_df[events_df["Classificação"] == "Viável condicional"].groupby("Nome SNMPc").size()
    ).fillna(0).astype(int)
    site_map = {getattr(site, "nome", ""): site for site in (sites or {}).values()}
    grouped["Nome"] = grouped["Nome SNMPc"].map(
        lambda name: _text(getattr(site_map.get(name), "nome_cadastro", ""))
    )
    grouped["Tipo"] = grouped["Nome SNMPc"].map(
        lambda name: _text(getattr(site_map.get(name), "tipo", ""))
    )
    grouped["Status"] = grouped["Nome SNMPc"].map(
        lambda name: _text(getattr(site_map.get(name), "status_cadastro", ""))
    )
    grouped["Clientes atuais"] = grouped["Nome SNMPc"].map(
        lambda name: len(getattr(site_map.get(name), "clientes", []) or [])
    )
    grouped["Receita atual"] = grouped["Nome SNMPc"].map(
        lambda name: sum(float(getattr(client, "receita", 0) or 0) for client in (getattr(site_map.get(name), "clientes", []) or []))
    )
    grouped["Custo atual"] = grouped["Nome SNMPc"].map(
        lambda name: float(getattr(site_map.get(name), "custo", 0) or 0)
    )
    return grouped[columns].sort_values(
        ["Solicitações viáveis", "Nome SNMPc"], ascending=[False, True]
    ).reset_index(drop=True)


def default_dashboard_period(today=None):
    end = pd.Timestamp(today or date.today()).normalize()
    start = end - pd.DateOffset(months=12)
    return start.date(), end.date()


def export_records_excel(df, include_proposal_values=True):
    export = df.copy()
    if "Dados Fonte" in export.columns:
        source_rows = [
            value if isinstance(value, dict) else {}
            for value in export["Dados Fonte"]
        ]
        source_frame = pd.DataFrame(source_rows, index=export.index)
        for column in source_frame.columns:
            if column not in export.columns:
                export[column] = source_frame[column]

    hidden = ["Dados Fonte", "Sites Candidatos"]
    if not include_proposal_values:
        hidden.extend(PROPOSAL_VALUE_COLUMNS)
        hidden.extend(["Vlr Mens Total", "Vlr Inst Total"])
    export = export.drop(columns=[column for column in hidden if column in export.columns])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export.to_excel(writer, sheet_name="Viabilidades", index=False)
    return output.getvalue()
