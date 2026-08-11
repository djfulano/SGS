from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import hashlib
import uuid

from app.config import SITE_CANCELLATIONS_FILE
from app.logs import registrar_log_sistema
from app.services.client_viability import carregar_clientes_viabilidade
from app.services.line_of_sight import coordenada_valida
from app.services.line_of_sight import distancia_km
from app.services.map_service import carregar_cache_geocoding
from app.services.map_service import geocodificar_endereco
from app.services.map_service import salvar_cache_geocoding
from app.services.site_metrics import sites_descendentes
from app.services.site_registry_service import SITE_REGISTRY_COLUMNS
from app.services.site_registry_service import load_site_registry
from app.services.site_registry_service import normalize_code
from app.services.site_registry_service import site_pode_atender_outros_enderecos
from app.services.site_registry_service import upsert_site
from app.storage import read_json_authoritative
from app.storage import update_json_atomic


SCHEMA_VERSION = 2
PROCESS_STATUSES = ["Aberto", "Concluído", "Cancelado"]
TERMINAL_PROCESS_STATUSES = {"Concluído", "Cancelado"}
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
CLIENT_PROCESS_STATUSES = [
    "Pendente",
    "Em análise",
    "Aguardando atividade técnica",
    "Migração em andamento",
    "Migrado",
    "Cancelamento em andamento",
    "Cancelado",
    "Desistência do cliente",
    "Sem solução",
]
FINAL_CLIENT_PROCESS_STATUSES = {
    "Migrado",
    "Cancelado",
    "Desistência do cliente",
    "Sem solução",
}
DEFAULT_SITE_ACTIVITIES = [
    ("send_termination", "Enviar distrato", "Jurídico/Contratos"),
    ("notice_period", "Aguardar prazo de aviso", "Jurídico/Contratos"),
    ("remove_equipment", "Retirar equipamentos", "Operações"),
]
CANDIDATE_SITE_LIMIT = 10


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _texto(value):
    if value is None:
        return ""
    return str(value).strip()


def _numero(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = _texto(value).replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _data(value):
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _texto(value)
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return ""


def _new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def _default_data():
    return {"schema_version": SCHEMA_VERSION, "processes": {}}


def _reset_legacy_data(path, data):
    reset = {}

    def updater(current):
        if current.get("schema_version") == SCHEMA_VERSION:
            return current
        reset["count"] = len(current.get("processes", {}) or {})
        return _default_data()

    updated = update_json_atomic(
        path,
        _default_data(),
        updater,
        backup_previous=False,
    )
    if "count" in reset:
        backup_path = path.with_name(f"{path.name}.bak")
        try:
            backup_path.unlink()
        except FileNotFoundError:
            pass
        registrar_log_sistema(
            "cancelamentos_schema_reset",
            status="sucesso",
            detalhes={"processos_removidos": reset["count"], "schema": SCHEMA_VERSION},
        )
    return updated


def load_cancellation_processes(path=None):
    target = Path(path or SITE_CANCELLATIONS_FILE)
    data = read_json_authoritative(target, _default_data())
    if not isinstance(data, dict) or not isinstance(data.get("processes", {}), dict):
        raise ValueError("O cadastro de cancelamentos de sites é inválido.")
    if data.get("schema_version") != SCHEMA_VERSION:
        data = _reset_legacy_data(target, data)
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


def is_terminal_process(process_or_status):
    status = (
        process_or_status.get("status")
        if isinstance(process_or_status, dict)
        else process_or_status
    )
    return _texto(status) in TERMINAL_PROCESS_STATUSES


def _site_identity(site):
    return {
        "site_name": _texto(getattr(site, "nome", "")),
        "site_label": _texto(getattr(site, "nome_cadastro", "")),
        "aquiles": _texto(getattr(site, "codigo_topos", "")),
        "microsiga": _texto(getattr(site, "microsiga", "")),
        "type": _texto(getattr(site, "tipo", "")),
        "status": _texto(getattr(site, "status_cadastro", "")),
    }


def _scope_sites(site, scope):
    selected = sites_descendentes(site) if scope == "Site e descendentes" else [site]
    unique = {}
    for item in selected:
        unique[_texto(getattr(item, "nome", ""))] = item
    return list(unique.values())


def _client_snapshot(scope_sites, viability_data=None):
    viability_data = viability_data or {}
    scope_names = {_texto(getattr(site, "nome", "")) for site in scope_sites}
    clients = {}
    for site in scope_sites:
        links = (
            site.listar_vinculos_clientes(incluir_adicionais=True)
            if hasattr(site, "listar_vinculos_clientes")
            else [
                {
                    "cliente": client,
                    "setorial": getattr(client, "setorial", ""),
                    "tipo": "Principal",
                }
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
            technical_data = viability_data.get(signature, {}) or {}
            item = clients.setdefault(signature, {
                "signature": signature,
                "name": _texto(getattr(client, "nome", "")),
                "product": _texto(getattr(client, "produto", "")),
                "manager": _texto(getattr(client, "gerente_contas", "")),
                "revenue": _numero(getattr(client, "receita", 0)),
                "address": _texto(getattr(client, "endereco_completo", "")),
                "city": _texto(getattr(client, "cidade", "")),
                "latitude": _numero(
                    technical_data.get("latitude") or getattr(client, "latitude", 0)
                ),
                "longitude": _numero(
                    technical_data.get("longitude") or getattr(client, "longitude", 0)
                ),
                "current_links": current_links,
                "affected_links": [],
                "equipments": [],
                "candidate_sites": [],
                "candidate_status": "Pendente",
                "candidate_message": "",
                "candidate_calculated_at": "",
                "status": "Pendente",
                "destination_site": "",
                "notes": "",
                "updated_at": "",
                "updated_by": "",
            })
            for current_link in current_links:
                if current_link["site"] in scope_names and current_link not in item["affected_links"]:
                    item["affected_links"].append(current_link)
    return list(clients.values())


def _equipment_key(equipment):
    source = "|".join(_texto(equipment.get(key)) for key in [
        "Site", "Equipamento", "Endereco", "Assinatura", "Icone", "Arvore"
    ])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _attach_client_equipments(clients, equipments):
    clients_by_signature = {item["signature"]: item for item in clients}
    seen = set()
    for equipment in equipments or []:
        signature = _texto(equipment.get("Assinatura"))
        if signature not in clients_by_signature:
            continue
        key = _equipment_key(equipment)
        if key in seen:
            continue
        seen.add(key)
        clients_by_signature[signature]["equipments"].append({
            "id": key,
            "name": _texto(equipment.get("Equipamento")) or _texto(equipment.get("Icone")),
            "icon": _texto(equipment.get("Icone")),
            "ip": _texto(equipment.get("Endereco")),
            "site": _texto(equipment.get("Site")),
        })
    return clients


def _site_candidate_identity(site, distance, current_sites):
    site_name = _texto(getattr(site, "nome", ""))
    return {
        "site": site_name,
        "name": _texto(getattr(site, "nome_cadastro", "")),
        "aquiles": _texto(getattr(site, "codigo_topos", "")),
        "microsiga": _texto(getattr(site, "microsiga", "")),
        "type": _texto(getattr(site, "tipo", "")),
        "city": _texto(getattr(site, "cidade", "")),
        "distance_km": round(float(distance), 3),
        "current_service": site_name in current_sites,
    }


def calculate_client_distance_candidates(
    clients,
    sites,
    excluded_sites=None,
    limit=CANDIDATE_SITE_LIMIT,
    geocode=None,
    geocoding_cache=None,
):
    excluded_sites = {_texto(item) for item in (excluded_sites or [])}
    cache = geocoding_cache if geocoding_cache is not None else carregar_cache_geocoding()
    geocode = geocode or geocodificar_endereco
    geocoding_attempted = False
    calculated_at = _agora()

    for client in clients or []:
        latitude = _numero(client.get("latitude"))
        longitude = _numero(client.get("longitude"))
        address = _texto(client.get("address"))
        message = ""
        if not coordenada_valida(latitude, longitude) and address:
            geocoding_attempted = True
            try:
                point = geocode(address, cache)
                if point:
                    latitude = _numero(point.get("lat"))
                    longitude = _numero(point.get("lon"))
            except Exception as error:
                message = "Não foi possível geocodificar o endereço do cliente."
                registrar_log_sistema(
                    "cancelamento_cliente_geocodificacao",
                    status="erro",
                    detalhes={
                        "assinatura": _texto(client.get("signature")),
                        "erro": type(error).__name__,
                    },
                )

        client["latitude"] = latitude
        client["longitude"] = longitude
        client["candidate_calculated_at"] = calculated_at
        if not coordenada_valida(latitude, longitude):
            client["candidate_sites"] = []
            client["candidate_status"] = "Sem coordenadas"
            client["candidate_message"] = message or "Cliente sem coordenadas válidas."
            continue

        current_sites = {
            _texto(link.get("site")) for link in client.get("current_links", [])
        }
        candidates = []
        for site in (sites or {}).values():
            site_name = _texto(getattr(site, "nome", ""))
            if site_name in excluded_sites:
                continue
            if _texto(getattr(site, "status_cadastro", "")).casefold() != "ativo":
                continue
            if not site_pode_atender_outros_enderecos(site):
                continue
            site_latitude = _numero(getattr(site, "latitude", 0))
            site_longitude = _numero(getattr(site, "longitude", 0))
            if not coordenada_valida(site_latitude, site_longitude):
                continue
            distance = distancia_km(latitude, longitude, site_latitude, site_longitude)
            candidates.append(_site_candidate_identity(site, distance, current_sites))
        candidates.sort(key=lambda item: (item["distance_km"], item["site"].casefold()))
        client["candidate_sites"] = candidates[:max(1, int(limit or CANDIDATE_SITE_LIMIT))]
        client["candidate_status"] = "Calculado" if candidates else "Nenhum site localizado"
        client["candidate_message"] = message

    if geocoding_attempted and geocoding_cache is None:
        try:
            salvar_cache_geocoding(cache)
        except Exception as error:
            registrar_log_sistema(
                "cancelamento_cache_geocodificacao",
                status="erro",
                detalhes={"erro": type(error).__name__},
            )
    return clients


def _default_site_activities():
    return [
        {
            "id": activity_id,
            "name": name,
            "status": "Não iniciado",
            "responsible": "",
            "team": team,
            "due_date": "",
            "notes": "",
            "completed_at": "",
            "updated_at": "",
            "updated_by": "",
        }
        for activity_id, name, team in DEFAULT_SITE_ACTIVITIES
    ]


def site_activities(process):
    activities = process.get("site_activities")
    return deepcopy(activities) if isinstance(activities, list) else _default_site_activities()


def client_process_status(client):
    status = _texto(client.get("status"))
    return status if status in CLIENT_PROCESS_STATUSES else "Pendente"


def _append_history(process, event, user, details=None):
    now = _agora()
    process.setdefault("history", []).append({
        "at": now,
        "user": _texto(user),
        "event": _texto(event),
        "details": details or {},
    })
    process["updated_at"] = now
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
    planned_date = _data(planned_date)
    if not planned_date:
        raise ValueError("Informe a data prevista para o cancelamento.")
    if not _texto(responsible):
        raise ValueError("Informe o responsável pelo processo.")
    if _texto(team) not in TEAMS:
        raise ValueError("Equipe responsável inválida.")

    target = Path(path or SITE_CANCELLATIONS_FILE)
    load_cancellation_processes(target)
    scoped_sites = _scope_sites(site, scope)
    clients = _client_snapshot(scoped_sites, carregar_clientes_viabilidade())
    _attach_client_equipments(clients, equipments)
    calculate_client_distance_candidates(
        clients,
        sites,
        excluded_sites=[getattr(item, "nome", "") for item in scoped_sites],
    )
    process_id = _new_id("cancel")
    created_at = _agora()
    process = {
        "id": process_id,
        "code": f"CAN-{datetime.now().strftime('%Y%m%d')}-{process_id[-6:].upper()}",
        "status": "Aberto",
        "priority": priority,
        "scope": scope,
        "reason": _texto(reason),
        "planned_date": planned_date,
        "responsible": _texto(responsible),
        "team": _texto(team),
        "site": identity,
        "scope_sites": [_site_identity(item) for item in scoped_sites],
        "clients": clients,
        "site_activities": _default_site_activities(),
        "created_at": created_at,
        "created_by": _texto(user),
        "updated_at": created_at,
        "updated_by": _texto(user),
        "completed_at": "",
        "completed_by": "",
        "completion_justification": "",
        "canceled_at": "",
        "canceled_by": "",
        "cancellation_reason": "",
        "history": [],
    }
    _append_history(process, "process_created", user, {
        "site": identity["site_name"],
        "scope": scope,
        "clients": len(clients),
    })

    def updater(data):
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("O cadastro de cancelamentos precisa ser reinicializado.")
        for current in data.get("processes", {}).values():
            if current.get("status") != "Aberto":
                continue
            current_site = current.get("site", {})
            same_aquiles = identity["aquiles"] and current_site.get("aquiles") == identity["aquiles"]
            same_name = current_site.get("site_name") == identity["site_name"]
            if same_aquiles or same_name:
                raise ValueError("Já existe um processo ativo para este site.")
        data.setdefault("processes", {})[process_id] = process
        return data

    update_json_atomic(target, _default_data(), updater)
    registrar_log_sistema(
        "cancelamento_site_aberto",
        usuario=user,
        status="sucesso",
        detalhes={"processo": process["code"], "site": identity["site_name"]},
    )
    return deepcopy(process)


def update_cancellation_process(
    process_id,
    mutator,
    *,
    event,
    user,
    details=None,
    path=None,
):
    target = Path(path or SITE_CANCELLATIONS_FILE)
    load_cancellation_processes(target)
    result = {}

    def updater(data):
        process = data.get("processes", {}).get(process_id)
        if not process:
            raise ValueError("Processo de cancelamento não encontrado.")
        if is_terminal_process(process):
            raise ValueError("Processos concluídos ou cancelados não podem ser alterados.")
        mutator(process)
        _append_history(process, event, user, details)
        result.update(deepcopy(process))
        return data

    update_json_atomic(target, _default_data(), updater)
    return result


def update_client(process_id, signature, fields, *, user, path=None):
    allowed = {"status", "destination_site", "notes"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if values.get("status") and values["status"] not in CLIENT_PROCESS_STATUSES:
        raise ValueError("Status do cliente inválido.")

    def mutate(process):
        client = next(
            (item for item in process.get("clients", []) if item.get("signature") == signature),
            None,
        )
        if not client:
            raise ValueError("Cliente não encontrado no processo.")
        client.update({key: _texto(value) for key, value in values.items()})
        client["updated_at"] = _agora()
        client["updated_by"] = _texto(user)

    return update_cancellation_process(
        process_id,
        mutate,
        event="client_updated",
        user=user,
        details={"signature": signature, "fields": sorted(values)},
        path=path,
    )


def update_site_activity(process_id, activity_id, fields, *, user, path=None):
    allowed = {"status", "responsible", "due_date", "notes"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if values.get("status") and values["status"] not in ACTIVITY_STATUSES:
        raise ValueError("Status da atividade inválido.")
    if "due_date" in values:
        values["due_date"] = _data(values["due_date"])

    def mutate(process):
        activity = next(
            (item for item in process.get("site_activities", []) if item.get("id") == activity_id),
            None,
        )
        if not activity:
            raise ValueError("Atividade do site não encontrada.")
        activity.update({
            key: (_texto(value) if key != "due_date" else value)
            for key, value in values.items()
        })
        activity["completed_at"] = _agora() if activity.get("status") == "Concluído" else ""
        activity["updated_at"] = _agora()
        activity["updated_by"] = _texto(user)

    return update_cancellation_process(
        process_id,
        mutate,
        event="site_activity_updated",
        user=user,
        details={"activity": activity_id, "fields": sorted(values)},
        path=path,
    )


def recalculate_process_distance_candidates(process_id, sites, *, user, path=None):
    process = get_cancellation_process(process_id, path)
    if not process:
        raise ValueError("Processo de cancelamento não encontrado.")
    calculated = deepcopy(process.get("clients", []))
    calculate_client_distance_candidates(
        calculated,
        sites,
        excluded_sites=[item.get("site_name") for item in process.get("scope_sites", [])],
    )

    def mutate(current):
        current["clients"] = calculated

    return update_cancellation_process(
        process_id,
        mutate,
        event="distance_candidates_recalculated",
        user=user,
        details={"clients": len(calculated)},
        path=path,
    )


def completion_pending_items(process):
    pending = []
    unfinished_clients = [
        item for item in process.get("clients", [])
        if client_process_status(item) not in FINAL_CLIENT_PROCESS_STATUSES
    ]
    if unfinished_clients:
        pending.append(f"{len(unfinished_clients)} cliente(s) com atendimento pendente")
    unfinished_activities = [
        item for item in site_activities(process)
        if item.get("status") not in {"Concluído", "Não aplicável"}
    ]
    if unfinished_activities:
        pending.append(f"{len(unfinished_activities)} atividade(s) do site pendente(s)")
    return pending


def _cancel_site_registry(process):
    registry = load_site_registry().astype(object)
    aquiles = normalize_code(process.get("site", {}).get("aquiles"))
    site_name = _texto(process.get("site", {}).get("site_name"))
    selected = registry.iloc[0:0]
    if aquiles:
        selected = registry[
            registry["CÓDIGO AQUILES"].apply(normalize_code).eq(aquiles)
        ]
    if selected.empty and site_name:
        selected = registry[registry["SMNPC"].astype(str).str.strip().eq(site_name)]
    if selected.empty:
        raise ValueError("O site principal não foi encontrado no cadastro de Sites.")
    row = selected.iloc[0]
    record = {column: row.get(column, "") for column in SITE_REGISTRY_COLUMNS}
    record["Status"] = "Cancelado"
    upsert_site(record, original_code=normalize_code(row.get("CÓDIGO AQUILES")))


def complete_process(process_id, *, justification, user, path=None):
    process = get_cancellation_process(process_id, path)
    if not process:
        raise ValueError("Processo de cancelamento não encontrado.")
    if process.get("status") == "Cancelado":
        raise ValueError("Processos cancelados não podem ser concluídos.")
    if process.get("status") == "Concluído":
        raise ValueError("O processo já está concluído.")
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
        detalhes={"processo": completed.get("code"), "site": completed.get("site", {}).get("site_name")},
    )
    return completed


def cancel_process(process_id, *, reason, user, path=None):
    reason = _texto(reason)
    if not reason:
        raise ValueError("Informe a justificativa do cancelamento do processo.")
    process = get_cancellation_process(process_id, path)
    if not process:
        raise ValueError("Processo de cancelamento não encontrado.")
    if process.get("status") == "Concluído":
        raise ValueError("Processos concluídos não podem ser cancelados.")
    if process.get("status") == "Cancelado":
        raise ValueError("O processo já está cancelado.")

    def mutate(item):
        item["status"] = "Cancelado"
        item["canceled_at"] = _agora()
        item["canceled_by"] = _texto(user)
        item["cancellation_reason"] = reason

    canceled = update_cancellation_process(
        process_id,
        mutate,
        event="process_canceled",
        user=user,
        details={"reason": reason},
        path=path,
    )
    registrar_log_sistema(
        "cancelamento_processo_cancelado",
        usuario=user,
        status="sucesso",
        detalhes={"processo": canceled.get("code"), "site": canceled.get("site", {}).get("site_name")},
    )
    return canceled


def filter_processes_by_scope(processes, scope):
    mapping = {
        "Abertos": {"Aberto"},
        "Concluídos": {"Concluído"},
        "Cancelados": {"Cancelado"},
    }
    statuses = mapping.get(scope)
    if not statuses:
        return list(processes or [])
    return [item for item in (processes or []) if item.get("status") in statuses]


def _client_result_group(client):
    status = client_process_status(client)
    if status == "Migrado":
        return "Migrados"
    if status in {"Cancelado", "Desistência do cliente"}:
        return "Cancelados"
    if status == "Cancelamento em andamento":
        return "Cancelamentos em andamento"
    if status == "Sem solução":
        return "Sem solução"
    return "Em andamento"


def process_metrics(processes, today=None):
    today = today or date.today()
    processes = list(processes or [])
    latest_clients = {}
    for process in processes:
        for index, client in enumerate(process.get("clients", [])):
            signature = _texto(client.get("signature"))
            key = signature or f"{process.get('id')}:{index}"
            updated_at = client.get("updated_at") or process.get("updated_at") or ""
            current = latest_clients.get(key)
            if not current or updated_at >= current[0]:
                latest_clients[key] = (updated_at, client)

    results = {
        label: {"count": 0, "revenue": 0.0}
        for label in [
            "Em andamento",
            "Migrados",
            "Cancelados",
            "Cancelamentos em andamento",
            "Sem solução",
        ]
    }
    for _updated_at, client in latest_clients.values():
        group = _client_result_group(client)
        results[group]["count"] += 1
        results[group]["revenue"] += _numero(client.get("revenue"))

    activity_statuses = {status: 0 for status in ACTIVITY_STATUSES}
    overdue = 0
    for process in processes:
        for activity in site_activities(process):
            status = activity.get("status") if activity.get("status") in ACTIVITY_STATUSES else "Não iniciado"
            activity_statuses[status] += 1
            due = _data(activity.get("due_date"))
            if due and status not in {"Concluído", "Não aplicável"}:
                if datetime.fromisoformat(due).date() < today:
                    overdue += 1

    sites = {
        process.get("site", {}).get("aquiles")
        or process.get("site", {}).get("site_name")
        for process in processes
    }
    sites.discard(None)
    sites.discard("")
    return {
        "processes": len(processes),
        "sites": len(sites),
        "clients": len(latest_clients),
        "results": results,
        "activity_statuses": activity_statuses,
        "overdue_activities": overdue,
    }
