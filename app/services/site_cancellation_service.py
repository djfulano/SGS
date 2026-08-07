from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from io import BytesIO
import hashlib
import uuid

import pandas as pd

from app.config import SITE_CANCELLATIONS_FILE
from app.logs import registrar_log_sistema
from app.services.finance_service import historico_financeiro_site
from app.services.site_metrics import sites_descendentes
from app.services.site_registry_service import SITE_REGISTRY_COLUMNS
from app.services.site_registry_service import load_site_registry
from app.services.site_registry_service import normalize_code
from app.services.site_registry_service import upsert_site
from app.storage import read_json_authoritative
from app.storage import update_json_atomic


SCHEMA_VERSION = 1
PROCESS_STATUSES = [
    "Em andamento",
    "Aguardando terceiros",
    "Suspenso",
    "Pronto para conclusão",
    "Concluído",
]
PROCESS_PRIORITIES = ["Crítica", "Alta", "Média", "Baixa"]
PROCESS_SCOPES = ["Somente site", "Site e descendentes"]
TEAMS = [
    "Engenharia",
    "NOC",
    "Suporte/Técnica",
    "Financeiro",
    "Jurídico/Contratos",
    "Operações",
    "Comercial",
    "Outros",
]
ACTIVITY_STATUSES = [
    "Não iniciado",
    "Em andamento",
    "Aguardando terceiro",
    "Bloqueado",
    "Concluído",
    "Não aplicável",
]
CLIENT_STUDY_STATUSES = [
    "Pendente",
    "Em processamento",
    "Migrável",
    "Condicional",
    "Não migrável",
    "Erro",
]
CLIENT_STAGES = [
    "Pendente de estudo",
    "Estudo concluído",
    "Chamado aberto",
    "Atividade agendada",
    "Em execução",
    "Pendente de notificação",
    "Concluído",
]
CLIENT_RESULTS = [
    "Pendente",
    "Migrado",
    "Cancelado pela empresa",
    "Desistência do cliente",
    "Mantido",
    "Sem solução",
]
TICKET_STATUSES = [
    "Não aberto",
    "Aberto",
    "Em atendimento",
    "Agendado",
    "Concluído",
    "Cancelado",
]
EQUIPMENT_RESULTS = [
    "Pendente",
    "Retirado",
    "Transferido",
    "Permanecerá",
    "Não localizado",
    "Não se aplica",
]
LINK_CATEGORIES = [
    "Estudo",
    "Chamado",
    "Notificação",
    "Distrato",
    "Financeiro",
    "Retirada",
    "Outro",
]
NOTIFICATION_CHANNELS = [
    "E-mail",
    "Telefone",
    "WhatsApp",
    "Carta",
    "Outro",
]
DEFAULT_PHASES = [
    ("planejamento", "Planejamento e levantamento", "Operações"),
    ("estudo", "Estudo técnico e migrações", "Engenharia"),
    ("execucao", "Execução e comunicação com clientes", "Suporte/Técnica"),
    ("financeiro", "Financeiro e distrato", "Financeiro"),
    ("equipamentos", "Equipamentos e retirada", "Operações"),
    ("conclusao", "Conclusão do cancelamento", "Operações"),
]


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _texto(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def _numero(value):
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _data(value):
    if value in (None, ""):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _json_value(value):
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(df):
    if df is None or df.empty:
        return []
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def _default_data():
    return {"schema_version": SCHEMA_VERSION, "processes": {}}


def load_cancellation_processes(path=None):
    data = read_json_authoritative(path or SITE_CANCELLATIONS_FILE, _default_data())
    if not isinstance(data, dict) or not isinstance(data.get("processes", {}), dict):
        raise ValueError("O cadastro de cancelamentos de sites é inválido.")
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("processes", {})
    return data


def list_cancellation_processes(path=None):
    processes = load_cancellation_processes(path).get("processes", {})
    return sorted(
        [deepcopy(item) for item in processes.values()],
        key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        reverse=True,
    )


def get_cancellation_process(process_id, path=None):
    process = load_cancellation_processes(path).get("processes", {}).get(process_id)
    return deepcopy(process) if process else None


def _site_identity(site):
    return {
        "site_name": _texto(getattr(site, "nome", "")),
        "site_label": _texto(getattr(site, "nome_cadastro", "")),
        "aquiles": _texto(getattr(site, "codigo_topos", "")),
        "microsiga": _texto(getattr(site, "microsiga", "")),
        "type": _texto(getattr(site, "tipo", "")),
        "status": _texto(getattr(site, "status_cadastro", "")),
        "cost": _numero(getattr(site, "custo", 0)),
        "address": _texto(getattr(site, "endereco", "")),
        "city": _texto(getattr(site, "cidade", "")),
    }


def _scope_sites(site, scope):
    selected = sites_descendentes(site) if scope == "Site e descendentes" else [site]
    unique = {}
    for item in selected:
        unique[_texto(getattr(item, "nome", ""))] = item
    return list(unique.values())


def _client_snapshot(scope_sites):
    scope_names = {_texto(getattr(site, "nome", "")) for site in scope_sites}
    clients = {}
    for site in scope_sites:
        links = (
            site.listar_vinculos_clientes(incluir_adicionais=True)
            if hasattr(site, "listar_vinculos_clientes")
            else [
                {"cliente": client, "setorial": getattr(client, "setorial", ""), "tipo": "Principal"}
                for client in getattr(site, "clientes", [])
            ]
        )
        for link in links:
            client = link.get("cliente")
            signature = _texto(getattr(client, "num_assinatura", ""))
            if not signature:
                continue
            current_links = []
            for current in getattr(client, "vinculos_atendimento", []) or []:
                current_site = current.get("site")
                current_name = _texto(getattr(current_site, "nome", ""))
                if not current_name:
                    continue
                entry = {
                    "site": current_name,
                    "setorial": _texto(current.get("setorial")) or "Direto",
                    "type": _texto(current.get("tipo")) or "Principal",
                }
                if entry not in current_links:
                    current_links.append(entry)
            if not current_links:
                current_links.append({
                    "site": _texto(getattr(site, "nome", "")),
                    "setorial": _texto(link.get("setorial")) or "Direto",
                    "type": _texto(link.get("tipo")) or "Principal",
                })
            affected = [item for item in current_links if item["site"] in scope_names]
            remaining = [item for item in current_links if item["site"] not in scope_names]
            item = clients.setdefault(signature, {
                "signature": signature,
                "name": _texto(getattr(client, "nome", "")),
                "product": _texto(getattr(client, "produto", "")),
                "manager": _texto(getattr(client, "gerente_contas", "")),
                "revenue": _numero(getattr(client, "receita", 0)),
                "address": _texto(getattr(client, "endereco_completo", "")),
                "city": _texto(getattr(client, "cidade", "")),
                "current_links": current_links,
                "affected_links": [],
                "remaining_links": remaining,
                "has_remaining_service": bool(remaining),
                "current_state": "Atual",
                "study_status": "Pendente",
                "study_message": "",
                "study_candidates": [],
                "study_updated_at": "",
                "stage": "Pendente de estudo",
                "destination_site": "",
                "final_result": "Pendente",
                "responsible": "",
                "team": "Engenharia",
                "due_date": "",
                "notes": "",
                "notification": {
                    "date": "",
                    "channel": "",
                    "protocol": "",
                    "link": "",
                    "notes": "",
                },
            })
            for affected_link in affected:
                if affected_link not in item["affected_links"]:
                    item["affected_links"].append(affected_link)
    return list(clients.values())


def _equipment_key(equipment):
    source = "|".join(_texto(equipment.get(key)) for key in [
        "Site", "Equipamento", "Endereco", "Assinatura", "Icone", "Arvore"
    ])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _equipment_snapshot(equipments, scope_sites, clients):
    scope_names = {_texto(getattr(site, "nome", "")) for site in scope_sites}
    signatures = {item["signature"] for item in clients}
    selected = {}
    for equipment in equipments or []:
        site_name = _texto(equipment.get("Site"))
        signature = _texto(equipment.get("Assinatura"))
        if site_name not in scope_names and signature not in signatures:
            continue
        key = _equipment_key(equipment)
        selected.setdefault(key, {
            "id": key,
            "site": site_name,
            "signature": signature,
            "icon": _texto(equipment.get("Icone")),
            "equipment": _texto(equipment.get("Equipamento")),
            "address": _texto(equipment.get("Endereco")),
            "parent": _texto(equipment.get("Parent")),
            "sector": _texto(equipment.get("Setorial")),
            "tree": _texto(equipment.get("Arvore")),
            "current_state": "Atual",
            "result": "Pendente",
            "destination": "",
            "responsible": "",
            "date": "",
            "notes": "",
        })
    return list(selected.values())


def _child_snapshot(site, scope):
    if scope != "Site e descendentes":
        return []
    children = []
    for child in sites_descendentes(site)[1:]:
        children.append({
            **_site_identity(child),
            "new_parent": "",
            "ticket": "",
            "responsible": "",
            "team": "Engenharia",
            "due_date": "",
            "status": "Não iniciado",
            "notes": "",
        })
    return children


def _financial_snapshot(site):
    history = historico_financeiro_site(getattr(site, "microsiga", ""))
    return {
        "microsiga": history.get("microsiga", ""),
        "cost": _numero(getattr(site, "custo", 0)),
        "overdue_value": _numero(history.get("valor_em_atraso")),
        "overdue_count": int(history.get("parcelas_vencidas") or 0),
        "future_value": _numero(history.get("valor_futuro")),
        "future_count": int(history.get("parcelas_futuras") or 0),
        "open_agreements_value": _numero(history.get("valor_acordos_abertos")),
        "open_agreements_count": int(history.get("quantidade_acordos_abertos") or 0),
        "overdue_items": _records(history.get("vencidas")),
        "future_items": _records(history.get("futuras")),
        "agreement_items": _records(history.get("acordos_abertos")),
        "survey_confirmed": False,
        "settlement_confirmed": False,
        "notes": "",
    }


def _default_phases(responsible, planned_date):
    phases = []
    for key, name, team in DEFAULT_PHASES:
        phases.append({
            "id": key,
            "name": name,
            "status": "Não iniciado",
            "responsible": responsible if key in {"planejamento", "conclusao"} else "",
            "team": team,
            "due_date": planned_date if key == "conclusao" else "",
            "notes": "",
            "links": [],
            "required": True,
            "completed_at": "",
        })
    return phases


def _append_history(process, event, user, details=None):
    process.setdefault("history", []).append({
        "at": _agora(),
        "user": _texto(user),
        "event": _texto(event),
        "details": details or {},
    })
    process["updated_at"] = _agora()
    process["updated_by"] = _texto(user)


def create_cancellation_process(
    site,
    sites,
    equipments,
    *,
    scope,
    reason,
    priority,
    planned_date,
    responsible,
    team,
    user,
    path=None,
):
    if scope not in PROCESS_SCOPES:
        raise ValueError("Escopo de cancelamento inválido.")
    if priority not in PROCESS_PRIORITIES:
        raise ValueError("Prioridade de cancelamento inválida.")
    if not _texto(reason):
        raise ValueError("Informe o motivo do cancelamento.")
    identity = _site_identity(site)
    if not identity["site_name"]:
        raise ValueError("Site inválido para abertura do cancelamento.")
    if identity["status"].casefold() != "ativo":
        raise ValueError("Somente sites ativos podem iniciar um processo de cancelamento.")
    if not _data(planned_date):
        raise ValueError("Informe a data prevista para o cancelamento.")
    if not _texto(responsible):
        raise ValueError("Informe o responsável pelo processo.")
    if _texto(team) not in TEAMS:
        raise ValueError("Equipe responsável inválida.")
    scoped_sites = _scope_sites(site, scope)
    clients = _client_snapshot(scoped_sites)
    process_id = _new_id("cancel")
    created_at = _agora()
    process = {
        "id": process_id,
        "code": f"CAN-{datetime.now().strftime('%Y%m%d')}-{process_id[-6:].upper()}",
        "status": "Em andamento",
        "priority": priority,
        "scope": scope,
        "reason": _texto(reason),
        "planned_date": _data(planned_date),
        "responsible": _texto(responsible),
        "team": _texto(team),
        "site": identity,
        "scope_sites": [_site_identity(item) for item in scoped_sites],
        "clients": clients,
        "child_sites": _child_snapshot(site, scope),
        "equipments": _equipment_snapshot(equipments, scoped_sites, clients),
        "financial": _financial_snapshot(site),
        "phases": _default_phases(_texto(responsible), _data(planned_date)),
        "extra_tasks": [],
        "tickets": [],
        "links": [],
        "migration_batch": {
            "radius_km": 10.0,
            "site_limit": 10,
            "batch_size": 10,
            "status": "Pendente",
            "processed": 0,
            "total": len(clients),
            "last_error": "",
        },
        "created_at": created_at,
        "created_by": _texto(user),
        "updated_at": created_at,
        "updated_by": _texto(user),
        "completed_at": "",
        "completed_by": "",
        "completion_justification": "",
        "reopened_at": "",
        "reopened_by": "",
        "history": [],
    }
    _append_history(process, "process_created", user, {
        "site": identity["site_name"],
        "scope": scope,
        "clients": len(clients),
        "equipments": len(process["equipments"]),
    })

    def updater(data):
        data = data if isinstance(data, dict) else _default_data()
        processes = data.setdefault("processes", {})
        site_key = identity["aquiles"] or identity["site_name"].casefold()
        for current in processes.values():
            current_site = current.get("site", {})
            current_key = current_site.get("aquiles") or _texto(current_site.get("site_name")).casefold()
            if current_key == site_key and current.get("status") != "Concluído":
                raise ValueError("Já existe um processo ativo para este site.")
        processes[process_id] = process
        data["schema_version"] = SCHEMA_VERSION
        return data

    update_json_atomic(path or SITE_CANCELLATIONS_FILE, _default_data(), updater)
    registrar_log_sistema(
        "cancelamento_site_criado",
        usuario=user,
        status="sucesso",
        detalhes={"processo": process["code"], "site": identity["site_name"]},
    )
    return deepcopy(process)


def update_cancellation_process(process_id, mutator, *, event, user, details=None, path=None):
    result = {}

    def updater(data):
        process = data.get("processes", {}).get(process_id)
        if process is None:
            raise ValueError("Processo de cancelamento não encontrado.")
        if process.get("status") == "Concluído" and event != "process_reopened":
            raise ValueError("Reabra o processo antes de realizar alterações.")
        mutator(process)
        _append_history(process, event, user, details)
        result.update(deepcopy(process))
        return data

    update_json_atomic(path or SITE_CANCELLATIONS_FILE, _default_data(), updater)
    return result


def update_process_fields(process_id, fields, *, user, path=None):
    allowed = {"status", "priority", "reason", "planned_date", "responsible", "team"}
    normalized = {key: value for key, value in fields.items() if key in allowed}
    if "priority" in normalized and normalized["priority"] not in PROCESS_PRIORITIES:
        raise ValueError("Prioridade inválida.")
    if "status" in normalized and normalized["status"] not in PROCESS_STATUSES:
        raise ValueError("Status inválido.")
    if "planned_date" in normalized:
        normalized["planned_date"] = _data(normalized["planned_date"])
    return update_cancellation_process(
        process_id,
        lambda process: process.update(normalized),
        event="process_updated",
        user=user,
        details={"fields": list(normalized)},
        path=path,
    )


def _update_item(items, item_id, fields, id_field="id"):
    for item in items:
        if _texto(item.get(id_field)) == _texto(item_id):
            item.update(fields)
            return
    raise ValueError("Item do processo não encontrado.")


def update_phase(process_id, phase_id, fields, *, user, path=None):
    allowed = {"status", "responsible", "team", "due_date", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("status") and values["status"] not in ACTIVITY_STATUSES:
        raise ValueError("Status de etapa inválido.")
    if "due_date" in values:
        values["due_date"] = _data(values["due_date"])
    values["completed_at"] = _agora() if values.get("status") in {"Concluído", "Não aplicável"} else ""
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("phases", []), phase_id, values),
        event="phase_updated",
        user=user,
        details={"phase": phase_id, "fields": list(values)},
        path=path,
    )


def add_extra_task(process_id, task, *, user, path=None):
    name = _texto(task.get("name"))
    if not name:
        raise ValueError("Informe o nome da atividade.")
    item = {
        "id": _new_id("task"),
        "name": name,
        "status": task.get("status") if task.get("status") in ACTIVITY_STATUSES else "Não iniciado",
        "responsible": _texto(task.get("responsible")),
        "team": _texto(task.get("team")),
        "due_date": _data(task.get("due_date")),
        "notes": _texto(task.get("notes")),
        "required": False,
        "completed_at": "",
    }
    return update_cancellation_process(
        process_id,
        lambda process: process.setdefault("extra_tasks", []).append(item),
        event="task_added",
        user=user,
        details={"task": name},
        path=path,
    )


def update_extra_task(process_id, task_id, fields, *, user, path=None):
    allowed = {"name", "status", "responsible", "team", "due_date", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("status") and values["status"] not in ACTIVITY_STATUSES:
        raise ValueError("Status de atividade inválido.")
    if "due_date" in values:
        values["due_date"] = _data(values["due_date"])
    values["completed_at"] = _agora() if values.get("status") in {"Concluído", "Não aplicável"} else ""
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("extra_tasks", []), task_id, values),
        event="task_updated",
        user=user,
        details={"task": task_id, "fields": list(values)},
        path=path,
    )


def update_client(process_id, signature, fields, *, user, path=None):
    allowed = {
        "study_status", "study_message", "study_candidates", "study_updated_at",
        "stage", "destination_site", "final_result", "responsible", "team",
        "due_date", "notes", "notification",
    }
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("study_status") and values["study_status"] not in CLIENT_STUDY_STATUSES:
        raise ValueError("Resultado de estudo inválido.")
    if values.get("stage") and values["stage"] not in CLIENT_STAGES:
        raise ValueError("Etapa de cliente inválida.")
    if values.get("final_result") and values["final_result"] not in CLIENT_RESULTS:
        raise ValueError("Resultado final de cliente inválido.")
    if "due_date" in values:
        values["due_date"] = _data(values["due_date"])
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("clients", []), signature, values, id_field="signature"),
        event="client_updated",
        user=user,
        details={"signature": signature, "fields": list(values)},
        path=path,
    )


def update_child_site(process_id, site_name, fields, *, user, path=None):
    allowed = {"new_parent", "ticket", "responsible", "team", "due_date", "status", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("status") and values["status"] not in ACTIVITY_STATUSES:
        raise ValueError("Status de site filho inválido.")
    if "due_date" in values:
        values["due_date"] = _data(values["due_date"])
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("child_sites", []), site_name, values, id_field="site_name"),
        event="child_site_updated",
        user=user,
        details={"site": site_name, "fields": list(values)},
        path=path,
    )


def update_equipment(process_id, equipment_id, fields, *, user, path=None):
    allowed = {"result", "destination", "responsible", "date", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("result") and values["result"] not in EQUIPMENT_RESULTS:
        raise ValueError("Resultado de equipamento inválido.")
    if "date" in values:
        values["date"] = _data(values["date"])
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("equipments", []), equipment_id, values),
        event="equipment_updated",
        user=user,
        details={"equipment": equipment_id, "fields": list(values)},
        path=path,
    )


def update_financial_checklist(process_id, fields, *, user, path=None):
    allowed = {"survey_confirmed", "settlement_confirmed", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    return update_cancellation_process(
        process_id,
        lambda process: process.setdefault("financial", {}).update(values),
        event="financial_checklist_updated",
        user=user,
        details={"fields": list(values)},
        path=path,
    )


def add_ticket(process_id, ticket, *, user, path=None):
    number = _texto(ticket.get("number"))
    if not number:
        raise ValueError("Informe o número do chamado.")
    item = {
        "id": _new_id("ticket"),
        "number": number,
        "status": ticket.get("status") if ticket.get("status") in TICKET_STATUSES else "Aberto",
        "signatures": sorted({_texto(value) for value in ticket.get("signatures", []) if _texto(value)}),
        "notes": _texto(ticket.get("notes")),
        "created_at": _agora(),
        "updated_at": _agora(),
    }
    return update_cancellation_process(
        process_id,
        lambda process: process.setdefault("tickets", []).append(item),
        event="ticket_added",
        user=user,
        details={"number": number, "signatures": item["signatures"]},
        path=path,
    )


def update_ticket(process_id, ticket_id, fields, *, user, path=None):
    allowed = {"number", "status", "signatures", "notes"}
    values = {key: fields.get(key) for key in allowed if key in fields}
    if values.get("status") and values["status"] not in TICKET_STATUSES:
        raise ValueError("Status de chamado inválido.")
    if "signatures" in values:
        values["signatures"] = sorted({_texto(value) for value in values["signatures"] if _texto(value)})
    values["updated_at"] = _agora()
    return update_cancellation_process(
        process_id,
        lambda process: _update_item(process.get("tickets", []), ticket_id, values),
        event="ticket_updated",
        user=user,
        details={"ticket": ticket_id, "fields": list(values)},
        path=path,
    )


def add_external_link(process_id, link, *, user, path=None):
    title = _texto(link.get("title"))
    url = _texto(link.get("url"))
    category = _texto(link.get("category")) or "Outro"
    if not title or not url:
        raise ValueError("Informe o título e a URL da referência.")
    if category not in LINK_CATEGORIES:
        raise ValueError("Categoria de referência inválida.")
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("A referência deve usar uma URL HTTP ou HTTPS.")
    item = {
        "id": _new_id("link"),
        "category": category,
        "title": title,
        "url": url,
        "notes": _texto(link.get("notes")),
        "created_at": _agora(),
        "created_by": _texto(user),
    }
    return update_cancellation_process(
        process_id,
        lambda process: process.setdefault("links", []).append(item),
        event="external_link_added",
        user=user,
        details={"category": category, "title": title},
        path=path,
    )


def pending_migration_clients(process, limit=10):
    pending = [
        item for item in process.get("clients", [])
        if item.get("study_status") in {"Pendente", "Erro"}
        and item.get("final_result") == "Pendente"
    ]
    return pending[:max(1, int(limit or 10))]


def save_migration_study(process_id, signature, candidates, status, message, *, user, path=None):
    candidates = [
        {key: _json_value(value) for key, value in item.items()}
        for item in candidates
    ]

    def mutate(process):
        _update_item(process.get("clients", []), signature, {
            "study_status": status,
            "study_message": _texto(message),
            "study_candidates": candidates,
            "study_updated_at": _agora(),
            "stage": "Estudo concluído" if status not in {"Pendente", "Em processamento"} else "Pendente de estudo",
        }, id_field="signature")
        batch = process.setdefault("migration_batch", {})
        batch["processed"] = sum(
            1 for item in process.get("clients", [])
            if item.get("study_status") in {"Migrável", "Condicional", "Não migrável"}
        )
        batch["total"] = len(process.get("clients", []))
        batch["status"] = "Concluído" if batch["processed"] >= batch["total"] else "Em andamento"
        batch["last_error"] = _texto(message) if status == "Erro" else ""

    return update_cancellation_process(
        process_id,
        mutate,
        event="migration_study_saved",
        user=user,
        details={"signature": signature, "status": status, "candidates": len(candidates)},
        path=path,
    )


def compare_process_snapshot(process, sites, equipments):
    root_name = process.get("site", {}).get("site_name")
    root = (sites or {}).get(root_name)
    if root is None:
        return {
            "site_missing": True,
            "new_clients": [],
            "missing_clients": [item.get("signature") for item in process.get("clients", [])],
            "new_equipments": [],
            "missing_equipments": [item.get("id") for item in process.get("equipments", [])],
        }
    scoped = _scope_sites(root, process.get("scope"))
    current_clients = _client_snapshot(scoped)
    current_equipments = _equipment_snapshot(equipments, scoped, current_clients)
    old_clients = {item.get("signature") for item in process.get("clients", [])}
    new_clients_by_id = {item.get("signature"): item for item in current_clients}
    old_equipment = {item.get("id") for item in process.get("equipments", [])}
    new_equipment_by_id = {item.get("id"): item for item in current_equipments}
    return {
        "site_missing": False,
        "new_clients": [item for key, item in new_clients_by_id.items() if key not in old_clients],
        "missing_clients": sorted(old_clients - set(new_clients_by_id)),
        "new_equipments": [item for key, item in new_equipment_by_id.items() if key not in old_equipment],
        "missing_equipments": sorted(old_equipment - set(new_equipment_by_id)),
    }


def reconcile_process(process_id, sites, equipments, *, user, path=None):
    current = get_cancellation_process(process_id, path)
    if not current:
        raise ValueError("Processo de cancelamento não encontrado.")
    comparison = compare_process_snapshot(current, sites, equipments)

    def mutate(process):
        clients = process.setdefault("clients", [])
        equipments_current = process.setdefault("equipments", [])
        clients.extend(comparison["new_clients"])
        equipments_current.extend(comparison["new_equipments"])
        missing_clients = set(comparison["missing_clients"])
        missing_equipments = set(comparison["missing_equipments"])
        for item in clients:
            item["current_state"] = "Ausente da base atual" if item.get("signature") in missing_clients else "Atual"
        for item in equipments_current:
            item["current_state"] = "Ausente da base atual" if item.get("id") in missing_equipments else "Atual"
        process.setdefault("migration_batch", {})["total"] = len(clients)

    return update_cancellation_process(
        process_id,
        mutate,
        event="snapshot_reconciled",
        user=user,
        details={
            "new_clients": len(comparison["new_clients"]),
            "missing_clients": len(comparison["missing_clients"]),
            "new_equipments": len(comparison["new_equipments"]),
            "missing_equipments": len(comparison["missing_equipments"]),
        },
        path=path,
    )


def completion_pending_items(process):
    pending = []
    unfinished_clients = [
        item for item in process.get("clients", [])
        if item.get("final_result") == "Pendente"
    ]
    if unfinished_clients:
        pending.append(f"{len(unfinished_clients)} cliente(s) sem resultado final")
    unfinished_children = [
        item for item in process.get("child_sites", [])
        if item.get("status") not in {"Concluído", "Não aplicável"}
    ]
    if unfinished_children:
        pending.append(f"{len(unfinished_children)} site(s) filho(s) sem migração concluída")
    financial = process.get("financial", {})
    if not financial.get("survey_confirmed"):
        pending.append("levantamento financeiro não confirmado")
    if not financial.get("settlement_confirmed"):
        pending.append("regularização financeira não confirmada")
    unfinished_equipment = [
        item for item in process.get("equipments", [])
        if item.get("result") == "Pendente"
    ]
    if unfinished_equipment:
        pending.append(f"{len(unfinished_equipment)} equipamento(s) sem resultado")
    unfinished_phases = [
        item for item in process.get("phases", [])
        if item.get("required") and item.get("status") not in {"Concluído", "Não aplicável"}
    ]
    if unfinished_phases:
        pending.append(f"{len(unfinished_phases)} etapa(s) obrigatória(s) pendente(s)")
    return pending


def _cancel_site_registry(process):
    registry = load_site_registry().astype(object)
    aquiles = normalize_code(process.get("site", {}).get("aquiles"))
    site_name = _texto(process.get("site", {}).get("site_name"))
    selected = pd.DataFrame()
    if aquiles:
        selected = registry[
            registry["CÓDIGO AQUILES"].apply(normalize_code).eq(aquiles)
        ]
    if selected.empty and site_name:
        selected = registry[
            registry["SMNPC"].astype(str).str.strip().eq(site_name)
        ]
    if selected.empty:
        raise ValueError("O site principal não foi encontrado no cadastro de Sites.")
    row = selected.iloc[0]
    record = {column: row.get(column, "") for column in SITE_REGISTRY_COLUMNS}
    record["Status"] = "Cancelado"
    original_code = normalize_code(row.get("CÓDIGO AQUILES"))
    upsert_site(record, original_code=original_code)


def complete_process(process_id, *, justification, user, path=None):
    process = get_cancellation_process(process_id, path)
    if not process:
        raise ValueError("Processo de cancelamento não encontrado.")
    pending = completion_pending_items(process)
    justification = _texto(justification)
    if pending and not justification:
        raise ValueError("Informe uma justificativa para concluir com pendências.")
    _cancel_site_registry(process)

    def mutate(item):
        item["status"] = "Concluído"
        item["completed_at"] = _agora()
        item["completed_by"] = _texto(user)
        item["completion_justification"] = justification

    completed = update_cancellation_process(
        process_id,
        mutate,
        event="process_completed",
        user=user,
        details={"pending": pending, "justification": justification},
        path=path,
    )
    registrar_log_sistema(
        "cancelamento_site_concluido",
        usuario=user,
        status="sucesso",
        detalhes={"processo": completed.get("code"), "site": completed.get("site", {}).get("site_name"), "pendencias": pending},
    )
    return completed


def reopen_process(process_id, *, justification, user, path=None):
    justification = _texto(justification)
    if not justification:
        raise ValueError("Informe a justificativa da reabertura.")
    current = get_cancellation_process(process_id, path)
    if not current or current.get("status") != "Concluído":
        raise ValueError("Somente processos concluídos podem ser reabertos.")

    def mutate(process):
        process["status"] = "Em andamento"
        process["reopened_at"] = _agora()
        process["reopened_by"] = _texto(user)
        process["reopen_justification"] = justification

    result = {}

    def updater(data):
        process = data.get("processes", {}).get(process_id)
        if not process:
            raise ValueError("Processo de cancelamento não encontrado.")
        site = process.get("site", {})
        site_key = site.get("aquiles") or _texto(site.get("site_name")).casefold()
        for other_id, other in data.get("processes", {}).items():
            if other_id == process_id or other.get("status") == "Concluído":
                continue
            other_site = other.get("site", {})
            other_key = other_site.get("aquiles") or _texto(other_site.get("site_name")).casefold()
            if other_key == site_key:
                raise ValueError("Já existe outro processo ativo para este site.")
        mutate(process)
        _append_history(process, "process_reopened", user, {"justification": justification})
        result.update(deepcopy(process))
        return data

    update_json_atomic(path or SITE_CANCELLATIONS_FILE, _default_data(), updater)
    registrar_log_sistema(
        "cancelamento_site_reaberto",
        usuario=user,
        status="sucesso",
        detalhes={"processo": result.get("code"), "justificativa": justification},
    )
    return result


def process_metrics(processes, today=None):
    today = today or date.today()
    active = [item for item in processes if item.get("status") != "Concluído"]
    activities = agenda_items(active, today=today)
    clients = [client for item in active for client in item.get("clients", [])]
    equipments = [equipment for item in active for equipment in item.get("equipments", [])]
    return {
        "active_processes": len(active),
        "overdue_activities": sum(1 for item in activities if item.get("situation") == "Atrasado"),
        "next_7_days": sum(1 for item in activities if item.get("situation") == "Próximos 7 dias"),
        "affected_clients": len({item.get("signature") for item in clients if item.get("signature")}),
        "migrated_clients": sum(1 for item in clients if item.get("final_result") == "Migrado"),
        "cancelled_clients": sum(1 for item in clients if item.get("final_result") in {"Cancelado pela empresa", "Desistência do cliente"}),
        "unsolved_clients": sum(1 for item in clients if item.get("final_result") == "Sem solução"),
        "pending_equipments": sum(1 for item in equipments if item.get("result") == "Pendente"),
        "monthly_savings": sum(_numero(item.get("site", {}).get("cost")) for item in active),
    }


def agenda_items(processes, today=None):
    today = today or date.today()
    result = []

    def add(process, item_type, title, due, status, responsible, team):
        due_date = pd.to_datetime(due, errors="coerce")
        if pd.isna(due_date):
            return
        due_day = due_date.date()
        if status in {"Concluído", "Não aplicável", "Cancelado"}:
            situation = "Concluído"
        elif due_day < today:
            situation = "Atrasado"
        elif due_day <= today + timedelta(days=7):
            situation = "Próximos 7 dias"
        else:
            situation = "Programado"
        result.append({
            "process_id": process.get("id"),
            "process": process.get("code"),
            "site": process.get("site", {}).get("site_name"),
            "type": item_type,
            "title": title,
            "due_date": due_day.isoformat(),
            "status": status,
            "situation": situation,
            "responsible": responsible,
            "team": team,
        })

    for process in processes:
        for phase in process.get("phases", []):
            add(process, "Etapa", phase.get("name"), phase.get("due_date"), phase.get("status"), phase.get("responsible"), phase.get("team"))
        for task in process.get("extra_tasks", []):
            add(process, "Atividade", task.get("name"), task.get("due_date"), task.get("status"), task.get("responsible"), task.get("team"))
        for client in process.get("clients", []):
            add(process, "Cliente", f"{client.get('name')} - {client.get('signature')}", client.get("due_date"), client.get("stage"), client.get("responsible"), client.get("team"))
        for child in process.get("child_sites", []):
            add(process, "Site filho", child.get("site_name"), child.get("due_date"), child.get("status"), child.get("responsible"), child.get("team"))
    return sorted(result, key=lambda item: (item["due_date"], item["site"], item["title"]))


def _currency(value):
    return f"R$ {_numero(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cancellation_email_text(process, show_client_values=True, show_cost_values=True):
    clients = process.get("clients", [])
    pending = completion_pending_items(process)
    lines = [
        "CANCELAMENTO DE SITE",
        f"Processo: {process.get('code', '')}",
        f"Site: {process.get('site', {}).get('site_name', '')} / {process.get('site', {}).get('site_label', '')}",
        f"Status: {process.get('status', '')}",
        f"Prioridade: {process.get('priority', '')}",
        f"Cancelamento previsto: {process.get('planned_date') or 'Não informado'}",
        f"Responsável: {process.get('responsible') or 'Não informado'}",
        "",
        f"Clientes impactados: {len(clients)}",
        f"Migrados: {sum(1 for item in clients if item.get('final_result') == 'Migrado')}",
        f"Cancelados/desistentes: {sum(1 for item in clients if item.get('final_result') in {'Cancelado pela empresa', 'Desistência do cliente'})}",
        f"Sem solução: {sum(1 for item in clients if item.get('final_result') == 'Sem solução')}",
        f"Receita impactada: {_currency(sum(_numero(item.get('revenue')) for item in clients)) if show_client_values else 'Restrito'}",
        f"Custo mensal do site: {_currency(process.get('site', {}).get('cost')) if show_cost_values else 'Restrito'}",
        "",
        "CLIENTES",
    ]
    for client in sorted(clients, key=lambda item: (_texto(item.get("name")).casefold(), item.get("signature", ""))):
        revenue = _currency(client.get("revenue")) if show_client_values else "Restrito"
        lines.append(
            f"- {client.get('name')} ({client.get('signature')}) | {client.get('final_result')} | "
            f"Destino: {client.get('destination_site') or 'Não definido'} | Receita: {revenue}"
        )
    lines.extend(["", "PRÓXIMAS PENDÊNCIAS"])
    lines.extend(f"- {item}" for item in pending)
    if not pending:
        lines.append("- Nenhuma pendência obrigatória.")
    return "\n".join(lines)


def export_cancellation_excel(process, show_client_values=True, show_cost_values=True):
    summary = pd.DataFrame([{
        "Processo": process.get("code"),
        "Site": process.get("site", {}).get("site_name"),
        "Nome": process.get("site", {}).get("site_label"),
        "Código Aquiles": process.get("site", {}).get("aquiles"),
        "Código Microsiga": process.get("site", {}).get("microsiga"),
        "Status": process.get("status"),
        "Prioridade": process.get("priority"),
        "Escopo": process.get("scope"),
        "Data prevista": process.get("planned_date"),
        "Responsável": process.get("responsible"),
        "Equipe": process.get("team"),
        "Custo mensal": process.get("site", {}).get("cost") if show_cost_values else "Restrito",
    }])
    clients = pd.DataFrame([{
        "Assinatura": item.get("signature"),
        "Cliente": item.get("name"),
        "Produto": item.get("product"),
        "Gerente de Contas": item.get("manager"),
        "Sites atuais": ", ".join(link.get("site", "") for link in item.get("current_links", [])),
        "Atendimento remanescente": "Sim" if item.get("has_remaining_service") else "Não",
        "Estudo": item.get("study_status"),
        "Etapa": item.get("stage"),
        "Site destino": item.get("destination_site"),
        "Resultado final": item.get("final_result"),
        "Responsável": item.get("responsible"),
        "Equipe": item.get("team"),
        "Prazo": item.get("due_date"),
        "Observações": item.get("notes"),
        **({"Receita": _numero(item.get("revenue"))} if show_client_values else {}),
    } for item in process.get("clients", [])])
    financial_data = process.get("financial", {})
    financial = pd.DataFrame([{
        "Código Microsiga": financial_data.get("microsiga"),
        "Custo mensal": _numero(financial_data.get("cost")),
        "Parcelas vencidas": financial_data.get("overdue_count", 0),
        "Valor vencido": _numero(financial_data.get("overdue_value")),
        "Parcelas futuras": financial_data.get("future_count", 0),
        "Valor futuro": _numero(financial_data.get("future_value")),
        "Acordos abertos": financial_data.get("open_agreements_count", 0),
        "Valor de acordos": _numero(financial_data.get("open_agreements_value")),
        "Levantamento conferido": "Sim" if financial_data.get("survey_confirmed") else "Não",
        "Regularização confirmada": "Sim" if financial_data.get("settlement_confirmed") else "Não",
        "Observações": financial_data.get("notes"),
    }])
    if not show_cost_values:
        financial = pd.DataFrame([{"Valores": "Restrito"}])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumo", index=False)
        clients.to_excel(writer, sheet_name="Clientes", index=False)
        pd.DataFrame(process.get("child_sites", [])).to_excel(writer, sheet_name="Sites Filhos", index=False)
        pd.DataFrame(process.get("phases", []) + process.get("extra_tasks", [])).to_excel(writer, sheet_name="Tarefas", index=False)
        pd.DataFrame([{
            "Número": item.get("number"),
            "Status": item.get("status"),
            "Assinaturas": ", ".join(item.get("signatures", [])),
            "Observações": item.get("notes"),
        } for item in process.get("tickets", [])]).to_excel(writer, sheet_name="Chamados", index=False)
        financial.to_excel(writer, sheet_name="Financeiro", index=False)
        pd.DataFrame(process.get("equipments", [])).to_excel(writer, sheet_name="Equipamentos", index=False)
        pd.DataFrame(process.get("links", [])).to_excel(writer, sheet_name="Links", index=False)
        pd.DataFrame([{
            "Data": item.get("at"),
            "Usuário": item.get("user"),
            "Evento": item.get("event"),
            "Detalhes": str(item.get("details") or ""),
        } for item in process.get("history", [])]).to_excel(writer, sheet_name="Histórico", index=False)
        for worksheet in writer.book.worksheets:
            headers = {cell.value: cell.column for cell in worksheet[1]}
            for header in ["Custo mensal", "Receita", "Valor vencido", "Valor futuro", "Valor de acordos"]:
                column = headers.get(header)
                if not column:
                    continue
                for row in range(2, worksheet.max_row + 1):
                    worksheet.cell(row=row, column=column).number_format = 'R$ #,##0.00'
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
    output.seek(0)
    return output.getvalue()
