from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.auth import load_users
from app.services.site_cancellation_service import ACTIVITY_STATUSES
from app.services.site_cancellation_service import CLIENT_PROCESS_STATUSES
from app.services.site_cancellation_service import PROCESS_PRIORITIES
from app.services.site_cancellation_service import PROCESS_SCOPES
from app.services.site_cancellation_service import PROCESS_STATUSES
from app.services.site_cancellation_service import TEAMS
from app.services.site_cancellation_service import cancel_process
from app.services.site_cancellation_service import client_process_status
from app.services.site_cancellation_service import complete_process
from app.services.site_cancellation_service import completion_pending_items
from app.services.site_cancellation_service import create_cancellation_process
from app.services.site_cancellation_service import filter_processes_by_scope
from app.services.site_cancellation_service import get_cancellation_process
from app.services.site_cancellation_service import is_terminal_process
from app.services.site_cancellation_service import list_cancellation_processes
from app.services.site_cancellation_service import process_metrics
from app.services.site_cancellation_service import recalculate_process_distance_candidates
from app.services.site_cancellation_service import site_activities
from app.services.site_cancellation_service import update_client
from app.services.site_cancellation_service import update_site_activity
from app.services.site_registry_service import site_pode_atender_outros_enderecos
from app.ui.components.site_selector import rotulo_busca_site
from app.ui.components.site_selector import selecionar_site_pesquisavel
from app.ui.navigation import mostrar_subnavegacao


_usuario_logado = None
_mostrar_grid = None


def configurar_cancelamentos(
    usuario_logado,
    mostrar_grid=None,
    mostrar_botao_copiar_texto=None,
):
    del mostrar_botao_copiar_texto
    global _usuario_logado
    global _mostrar_grid
    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid


def usuario_atual():
    return _usuario_logado() if _usuario_logado else {}


def nome_usuario():
    return str(usuario_atual().get("username") or "").strip()


def pode(permissao):
    user = usuario_atual()
    return has_permission(user, "cancelamentos_sites") or has_permission(user, permissao)


def pode_consultar():
    return any(pode(key) for key in [
        "cancelamentos_consulta", "cancelamentos_editar", "cancelamentos_concluir"
    ])


def pode_editar():
    return pode("cancelamentos_editar")


def pode_concluir():
    return pode("cancelamentos_concluir")


def pode_ver_receita():
    return has_permission(usuario_atual(), "visualizar_valores_clientes")


def processo_encerrado(process):
    return is_terminal_process(process)


def _moeda(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date_value(value, default=None):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return default
    return parsed.date()


def _grid(df, key, height=420):
    if _mostrar_grid:
        return _mostrar_grid(df, key=key, height=height)
    return st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _user_options():
    try:
        users = load_users()
    except Exception:
        users = {}
    return [""] + sorted(
        [str(key).strip() for key in users if str(key).strip()],
        key=str.casefold,
    )


def _process_label(process):
    site = process.get("site", {})
    return (
        f"{process.get('code', '-')} / {site.get('site_name', '-')} - "
        f"{site.get('aquiles', '-')} / {site.get('site_label', '-')} - {process.get('status', '-')}"
    )


def _process_dataframe(processes):
    rows = []
    for process in processes:
        clients = process.get("clients", [])
        rows.append({
            "Processo": process.get("code"),
            "Nome SNMPc": process.get("site", {}).get("site_name"),
            "Código Aquiles": process.get("site", {}).get("aquiles"),
            "Nome": process.get("site", {}).get("site_label"),
            "Status": process.get("status"),
            "Prioridade": process.get("priority"),
            "Data prevista": process.get("planned_date"),
            "Responsável": process.get("responsible"),
            "Equipe": process.get("team"),
            "Clientes": len(clients),
            "Migrados": sum(client_process_status(item) == "Migrado" for item in clients),
            "Cancelados": sum(
                client_process_status(item) in {"Cancelado", "Desistência do cliente"}
                for item in clients
            ),
        })
    return pd.DataFrame(rows)


def _scope_control(key):
    options = ["Abertos", "Concluídos", "Cancelados", "Todos"]
    if st.session_state.get(key) not in options:
        st.session_state[key] = "Abertos"
    return st.segmented_control(
        "Situação dos processos",
        options,
        key=key,
        selection_mode="single",
        width="stretch",
    ) or "Abertos"


def mostrar_resumo_cancelamentos():
    st.header("Resumo de Cancelamentos")
    scope = _scope_control("cancelamentos_resumo_escopo")
    processes = filter_processes_by_scope(list_cancellation_processes(), scope)
    metrics = process_metrics(processes)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Processos", metrics["processes"])
    col2.metric("Sites", metrics["sites"])
    col3.metric("Clientes", metrics["clients"])
    col4.metric("Atividades atrasadas", metrics["overdue_activities"])

    st.subheader("Resultados dos clientes")
    columns = st.columns(4)
    for column, label in zip(
        columns,
        ["Em andamento", "Migrados", "Cancelados", "Sem solução"],
    ):
        result = metrics["results"][label]
        column.metric(label, result["count"])
        column.caption(
            f"Receita mensal: {_moeda(result['revenue'])}"
            if pode_ver_receita()
            else "Receita mensal: Restrito"
        )

    st.subheader("Atividades dos sites")
    activity_rows = pd.DataFrame([
        {"Status": status, "Quantidade": count}
        for status, count in metrics["activity_statuses"].items()
    ])
    st.dataframe(activity_rows, use_container_width=True, hide_index=True)

    st.subheader("Processos no escopo")
    process_df = _process_dataframe(processes)
    if process_df.empty:
        st.info("Nenhum processo encontrado para o filtro selecionado.")
    else:
        _grid(process_df, "cancelamentos_resumo_processos", min(520, 90 + len(process_df) * 34))


def _create_process_form(sites, equipments):
    if not pode_editar():
        return
    with st.expander("Novo processo", expanded=False):
        active_sites = {
            name: site for name, site in (sites or {}).items()
            if str(getattr(site, "status_cadastro", "") or "").strip().casefold() == "ativo"
        }
        labels = {name: rotulo_busca_site(site) for name, site in active_sites.items()}
        with st.form("cancelamento_novo_processo"):
            selected = selecionar_site_pesquisavel(
                sorted(active_sites, key=lambda name: labels[name].casefold()),
                labels,
                "cancelamento_novo_site",
            )
            col1, col2, col3 = st.columns(3)
            scope = col1.selectbox("Escopo", PROCESS_SCOPES)
            priority = col2.selectbox("Prioridade", PROCESS_PRIORITIES, index=1)
            planned_date = col3.date_input(
                "Cancelamento previsto",
                value=None,
                format="DD/MM/YYYY",
            )
            col1, col2 = st.columns(2)
            responsible = col1.selectbox("Responsável", _user_options(), index=0)
            team = col2.selectbox("Equipe", TEAMS, index=5)
            reason = st.text_area("Motivo", height=90)
            submit = st.form_submit_button("Criar processo", type="primary")
        if submit:
            if not selected:
                st.error("Selecione um site.")
                return
            try:
                with st.spinner("Abrindo processo e calculando os sites mais próximos dos clientes..."):
                    process = create_cancellation_process(
                        active_sites[selected],
                        sites,
                        equipments,
                        scope=scope,
                        reason=reason,
                        priority=priority,
                        planned_date=planned_date,
                        responsible=responsible,
                        team=team,
                        user=nome_usuario(),
                    )
                st.session_state["cancelamento_processo_selecionado"] = process["id"]
                st.success("Processo criado.")
                st.rerun()
            except Exception as error:
                st.error(f"Falha ao criar processo: {error}")


def _process_overview(process):
    site = process.get("site", {})
    st.subheader(f"{process.get('code')} - {site.get('site_name')}")
    st.caption(
        f"{site.get('site_label') or 'Sem nome cadastrado'} | "
        f"Escopo: {process.get('scope')}"
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", process.get("status"))
    col2.metric("Clientes", len(process.get("clients", [])))
    planned = _date_value(process.get("planned_date"))
    col3.metric("Data prevista", planned.strftime("%d/%m/%Y") if planned else "Não informada")
    col4.metric("Responsável", process.get("responsible") or "Não informado")
    st.markdown(f"**Motivo:** {process.get('reason') or 'Não informado'}")
    if process.get("status") == "Cancelado":
        st.warning("Processo cancelado. O site não foi alterado.")
        st.caption(
            f"Cancelado por {process.get('canceled_by') or 'Não informado'} em "
            f"{process.get('canceled_at') or 'data não informada'}: "
            f"{process.get('cancellation_reason') or 'sem justificativa'}"
        )
    elif process.get("status") == "Concluído":
        st.success("Processo concluído e site marcado como Cancelado.")
        st.caption(
            f"Concluído por {process.get('completed_by') or 'Não informado'} em "
            f"{process.get('completed_at') or 'data não informada'}."
        )


def _completion_section(process):
    if processo_encerrado(process):
        return
    pending = completion_pending_items(process)
    if pending:
        st.warning("Pendências para conclusão: " + "; ".join(pending) + ".")
    else:
        st.success("Clientes e atividades do site estão concluídos.")
    if not pode_concluir():
        st.caption("Seu usuário não possui permissão para concluir ou cancelar este processo.")
        return

    col1, col2 = st.columns(2)
    with col1:
        with st.form(f"cancelamento_concluir_{process['id']}"):
            justification = st.text_area(
                "Justificativa para conclusão com pendências",
                help="Obrigatória somente quando houver pendências.",
            )
            confirmation = st.text_input("Digite CONCLUIR para confirmar")
            submit = st.form_submit_button("Concluir e cancelar o site", type="primary")
        if submit:
            if confirmation.strip().upper() != "CONCLUIR":
                st.error("Digite CONCLUIR para confirmar.")
            else:
                try:
                    complete_process(
                        process["id"],
                        justification=justification,
                        user=nome_usuario(),
                    )
                    st.success("Processo concluído e site marcado como Cancelado.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Falha ao concluir processo: {error}")
    with col2:
        with st.form(f"cancelamento_cancelar_{process['id']}"):
            reason = st.text_area("Justificativa do cancelamento do processo")
            confirmation = st.text_input("Digite CANCELAR para confirmar")
            submit = st.form_submit_button("Cancelar processo")
        if submit:
            if confirmation.strip().upper() != "CANCELAR":
                st.error("Digite CANCELAR para confirmar.")
            else:
                try:
                    cancel_process(process["id"], reason=reason, user=nome_usuario())
                    st.success("Processo cancelado. O cadastro do site não foi alterado.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Falha ao cancelar processo: {error}")


def mostrar_processos_cancelamento(sites, equipments):
    st.header("Processos de Cancelamento")
    _create_process_form(sites, equipments)
    processes = list_cancellation_processes()
    if not processes:
        st.info("Nenhum processo de cancelamento foi registrado.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    search = col1.text_input(
        "Buscar processo",
        placeholder="Site, código, responsável ou processo",
        key="cancelamento_processos_busca",
    )
    status_filter = col2.multiselect("Status", PROCESS_STATUSES, key="cancelamento_processos_status")
    priority_filter = col3.multiselect(
        "Prioridade",
        PROCESS_PRIORITIES,
        key="cancelamento_processos_prioridade",
    )
    filtered = []
    for process in processes:
        searchable = " ".join([
            process.get("code", ""),
            process.get("site", {}).get("site_name", ""),
            process.get("site", {}).get("site_label", ""),
            process.get("site", {}).get("aquiles", ""),
            process.get("responsible", ""),
            process.get("team", ""),
        ]).casefold()
        if search and search.casefold() not in searchable:
            continue
        if status_filter and process.get("status") not in status_filter:
            continue
        if priority_filter and process.get("priority") not in priority_filter:
            continue
        filtered.append(process)

    process_df = _process_dataframe(filtered)
    if process_df.empty:
        st.info("Nenhum processo corresponde aos filtros.")
        return
    _grid(process_df, "cancelamentos_processos_lista", min(560, 100 + len(process_df) * 34))

    labels = {process["id"]: _process_label(process) for process in filtered}
    if st.session_state.get("cancelamento_processo_selecionado") not in labels:
        st.session_state.pop("cancelamento_processo_selecionado", None)
    selected_id = st.selectbox(
        "Processo para gerenciar",
        list(labels),
        index=None,
        placeholder="Digite para pesquisar e selecione um processo",
        format_func=lambda value: labels[value],
        key="cancelamento_processo_selecionado",
    )
    if not selected_id:
        return
    process = get_cancellation_process(selected_id)
    if process:
        _process_overview(process)
        with st.expander("Encerramento do processo", expanded=False):
            _completion_section(process)


def _eligible_destination_sites(process, sites):
    excluded = {item.get("site_name") for item in process.get("scope_sites", [])}
    return {
        name: site for name, site in (sites or {}).items()
        if name not in excluded
        and str(getattr(site, "status_cadastro", "") or "").strip().casefold() == "ativo"
        and site_pode_atender_outros_enderecos(site)
    }


def _destination_site_options(process, sites, current_destination="", client=None):
    eligible = _eligible_destination_sites(process, sites)
    candidate_order = []
    for item in (client or {}).get("candidate_sites", []) or []:
        name = str(item.get("site") or "").strip()
        if name in eligible and name not in candidate_order:
            candidate_order.append(name)
    remaining = sorted(
        [name for name in eligible if name not in candidate_order],
        key=lambda name: rotulo_busca_site(eligible[name]).casefold(),
    )
    options = [""] + candidate_order + remaining
    current_destination = str(current_destination or "").strip()
    if current_destination and current_destination not in options:
        options.append(current_destination)
    distances = {
        item.get("site"): item.get("distance_km")
        for item in (client or {}).get("candidate_sites", []) or []
    }
    labels = {"": "Não definido"}
    for name, site in eligible.items():
        label = rotulo_busca_site(site)
        if name in distances:
            label = f"{label} / {distances[name]:.2f} km"
        labels[name] = label
    labels.setdefault(current_destination, current_destination)
    return options, labels


def _client_rows(processes, show_revenue):
    rows = []
    references = {}
    for process in processes:
        for client in process.get("clients", []):
            key = f"{process.get('id')}::{client.get('signature')}"
            references[key] = (process.get("id"), client.get("signature"))
            equipment_names = []
            for equipment in client.get("equipments", []) or []:
                name = equipment.get("name") or equipment.get("icon")
                if name and name not in equipment_names:
                    equipment_names.append(name)
            row = {
                "_key": key,
                "Processo": process.get("code"),
                "Site em cancelamento": process.get("site", {}).get("site_name"),
                "Assinatura": client.get("signature"),
                "Cliente": client.get("name"),
                "Produto": client.get("product"),
                "Gerente de Contas": client.get("manager"),
                "Equipamentos": ", ".join(equipment_names) or "Não localizado",
                "Status": client_process_status(client),
                "Site destino": client.get("destination_site"),
                "Candidatos": len(client.get("candidate_sites", []) or []),
            }
            if show_revenue:
                row["Receita mensal"] = client.get("revenue", 0)
            rows.append(row)
    return pd.DataFrame(rows), references


def mostrar_clientes_cancelamento(sites):
    st.header("Atividades dos Clientes")
    scope = _scope_control("cancelamentos_clientes_escopo")
    processes = filter_processes_by_scope(list_cancellation_processes(), scope)
    if not processes:
        st.info("Nenhum processo encontrado para o filtro selecionado.")
        return

    labels = {process["id"]: _process_label(process) for process in processes}
    process_options = [""] + list(labels)
    if st.session_state.get("cancelamentos_clientes_processo") not in process_options:
        st.session_state["cancelamentos_clientes_processo"] = ""
    col1, col2, col3 = st.columns([1.4, 1, 1.4])
    process_id = col1.selectbox(
        "Processo",
        process_options,
        format_func=lambda value: "Todos os processos" if not value else labels[value],
        key="cancelamentos_clientes_processo",
    )
    statuses = col2.multiselect(
        "Status do cliente",
        CLIENT_PROCESS_STATUSES,
        key="cancelamentos_clientes_status",
    )
    search = col3.text_input(
        "Buscar cliente",
        placeholder="Nome ou assinatura",
        key="cancelamentos_clientes_busca",
    )
    selected_processes = [
        process for process in processes if not process_id or process.get("id") == process_id
    ]
    df, references = _client_rows(selected_processes, pode_ver_receita())
    if not df.empty:
        if statuses:
            df = df[df["Status"].isin(statuses)]
        if search:
            mask = (
                df["Cliente"].fillna("").astype(str).str.contains(search, case=False, regex=False)
                | df["Assinatura"].fillna("").astype(str).str.contains(search, case=False, regex=False)
            )
            df = df[mask]
    if df.empty:
        st.info("Nenhum cliente corresponde aos filtros.")
        return

    visible = df.drop(columns=["_key"])
    _grid(visible, "cancelamentos_clientes_lista", min(600, 100 + len(visible) * 34))
    selection_labels = {
        row["_key"]: (
            f"{row['Cliente']} - {row['Assinatura']} / "
            f"{row['Processo']} - {row['Site em cancelamento']}"
        )
        for row in df.to_dict(orient="records")
    }
    if st.session_state.get("cancelamento_cliente_global_selecionado") not in selection_labels:
        st.session_state.pop("cancelamento_cliente_global_selecionado", None)
    selected_key = st.selectbox(
        "Cliente para gerenciar",
        list(selection_labels),
        index=None,
        placeholder="Digite para pesquisar e selecione um cliente",
        format_func=lambda value: selection_labels[value],
        key="cancelamento_cliente_global_selecionado",
    )
    if not selected_key:
        return
    selected_process_id, signature = references[selected_key]
    process = get_cancellation_process(selected_process_id)
    if not process:
        return
    client = next(
        (item for item in process.get("clients", []) if item.get("signature") == signature),
        None,
    )
    if not client:
        return

    st.subheader(f"{client.get('name')} - {signature}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Produto", client.get("product") or "Não informado")
    col2.metric("Gerente de Contas", client.get("manager") or "Não informado")
    col3.metric("Status", client_process_status(client))
    col4.metric("Site destino", client.get("destination_site") or "Não definido")
    st.caption(
        "Sites atuais: "
        + (", ".join(link.get("site", "") for link in client.get("current_links", [])) or "Não localizado")
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Equipamentos utilizados**")
        equipments = pd.DataFrame([{
            "Equipamento": item.get("name") or item.get("icon") or "Não informado",
            "Ícone": item.get("icon"),
            "IP": item.get("ip") or "Não informado",
            "Site": item.get("site"),
        } for item in client.get("equipments", []) or []])
        if equipments.empty:
            st.caption("Nenhum equipamento foi localizado para esta assinatura.")
        else:
            st.dataframe(equipments, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Sites candidatos por distância**")
        candidates = pd.DataFrame([{
            "Posição": index,
            "Site": item.get("site"),
            "Nome": item.get("name"),
            "Distância km": item.get("distance_km"),
            "Tipo": item.get("type"),
            "Cidade": item.get("city"),
        } for index, item in enumerate(client.get("candidate_sites", []) or [], start=1)])
        if candidates.empty:
            st.warning(client.get("candidate_message") or "Nenhum site candidato foi calculado.")
        else:
            st.dataframe(candidates, use_container_width=True, hide_index=True)
            st.caption("A ordenação considera somente a distância geográfica.")

    editable = pode_editar() and not processo_encerrado(process)
    if not editable:
        return
    if st.button(
        "Recalcular candidatos",
        key=f"cancelamento_recalcular_{process['id']}_{signature}",
    ):
        try:
            with st.spinner("Recalculando os sites mais próximos..."):
                recalculate_process_distance_candidates(
                    process["id"],
                    sites,
                    user=nome_usuario(),
                )
            st.success("Candidatos recalculados.")
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao recalcular candidatos: {error}")

    destination_options, destination_labels = _destination_site_options(
        process,
        sites,
        client.get("destination_site", ""),
        client,
    )
    with st.form(f"cancelamento_cliente_form_{process['id']}_{signature}"):
        col1, col2 = st.columns(2)
        current_status = client_process_status(client)
        status = col1.selectbox(
            "Status do cliente",
            CLIENT_PROCESS_STATUSES,
            index=CLIENT_PROCESS_STATUSES.index(current_status),
        )
        destination = col2.selectbox(
            "Site destino",
            destination_options,
            index=(
                destination_options.index(client.get("destination_site"))
                if client.get("destination_site") in destination_options
                else 0
            ),
            format_func=lambda value: destination_labels.get(value, value),
        )
        notes = st.text_area("Observações", value=client.get("notes", ""), height=90)
        save = st.form_submit_button("Salvar atividade do cliente", type="primary")
    if save:
        try:
            update_client(
                process["id"],
                signature,
                {"status": status, "destination_site": destination, "notes": notes},
                user=nome_usuario(),
            )
            st.success("Atividade do cliente atualizada.")
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao atualizar cliente: {error}")


def _site_activity_rows(processes):
    rows = []
    references = {}
    for process in processes:
        for activity in site_activities(process):
            key = f"{process.get('id')}::{activity.get('id')}"
            references[key] = (process.get("id"), activity.get("id"))
            rows.append({
                "_key": key,
                "Processo": process.get("code"),
                "Nome SNMPc": process.get("site", {}).get("site_name"),
                "Nome": process.get("site", {}).get("site_label"),
                "Atividade": activity.get("name"),
                "Status": activity.get("status"),
                "Prazo": activity.get("due_date"),
                "Responsável": activity.get("responsible"),
                "Equipe": activity.get("team"),
                "Observações": activity.get("notes"),
            })
    return pd.DataFrame(rows), references


def mostrar_sites_cancelamento():
    st.header("Atividades dos Sites")
    scope = _scope_control("cancelamentos_sites_escopo")
    processes = filter_processes_by_scope(list_cancellation_processes(), scope)
    if not processes:
        st.info("Nenhum processo encontrado para o filtro selecionado.")
        return

    labels = {process["id"]: _process_label(process) for process in processes}
    process_options = [""] + list(labels)
    if st.session_state.get("cancelamentos_sites_processo") not in process_options:
        st.session_state["cancelamentos_sites_processo"] = ""
    col1, col2, col3 = st.columns([1.5, 1, 1.2])
    process_id = col1.selectbox(
        "Processo",
        process_options,
        format_func=lambda value: "Todos os processos" if not value else labels[value],
        key="cancelamentos_sites_processo",
    )
    statuses = col2.multiselect(
        "Status da atividade",
        ACTIVITY_STATUSES,
        key="cancelamentos_sites_status",
    )
    search = col3.text_input(
        "Buscar site",
        placeholder="Nome, código ou atividade",
        key="cancelamentos_sites_busca",
    )
    selected_processes = [
        process for process in processes if not process_id or process.get("id") == process_id
    ]
    df, references = _site_activity_rows(selected_processes)
    if not df.empty:
        if statuses:
            df = df[df["Status"].isin(statuses)]
        if search:
            searchable = (
                df["Nome SNMPc"].fillna("").astype(str)
                + " " + df["Nome"].fillna("").astype(str)
                + " " + df["Atividade"].fillna("").astype(str)
            )
            df = df[searchable.str.contains(search, case=False, regex=False)]
    if df.empty:
        st.info("Nenhuma atividade corresponde aos filtros.")
        return

    visible = df.drop(columns=["_key"])
    _grid(visible, "cancelamentos_sites_atividades", min(600, 100 + len(visible) * 34))
    selection_labels = {
        row["_key"]: (
            f"{row['Nome SNMPc']} / {row['Atividade']} - {row['Status']} ({row['Processo']})"
        )
        for row in df.to_dict(orient="records")
    }
    if st.session_state.get("cancelamento_site_atividade_global_selecionada") not in selection_labels:
        st.session_state.pop("cancelamento_site_atividade_global_selecionada", None)
    selected_key = st.selectbox(
        "Atividade para gerenciar",
        list(selection_labels),
        index=None,
        placeholder="Selecione uma atividade do site",
        format_func=lambda value: selection_labels[value],
        key="cancelamento_site_atividade_global_selecionada",
    )
    if not selected_key:
        return
    selected_process_id, activity_id = references[selected_key]
    process = get_cancellation_process(selected_process_id)
    if not process:
        return
    activity = next(
        (item for item in site_activities(process) if item.get("id") == activity_id),
        None,
    )
    if not activity:
        return

    st.subheader(f"{process.get('site', {}).get('site_name')} - {activity.get('name')}")
    if not pode_editar() or processo_encerrado(process):
        st.caption("Atividade disponível somente para consulta.")
        return
    users = _user_options()
    current_responsible = activity.get("responsible", "")
    if current_responsible and current_responsible not in users:
        users.append(current_responsible)
    with st.form(f"cancelamento_site_atividade_form_{process['id']}_{activity_id}"):
        col1, col2, col3 = st.columns(3)
        status = col1.selectbox(
            "Status",
            ACTIVITY_STATUSES,
            index=(
                ACTIVITY_STATUSES.index(activity.get("status"))
                if activity.get("status") in ACTIVITY_STATUSES
                else 0
            ),
        )
        responsible = col2.selectbox(
            "Responsável",
            users,
            index=users.index(current_responsible) if current_responsible in users else 0,
        )
        due_date = col3.date_input(
            "Prazo",
            value=_date_value(activity.get("due_date")),
            format="DD/MM/YYYY",
        )
        notes = st.text_area("Observações", value=activity.get("notes", ""), height=90)
        save = st.form_submit_button("Salvar atividade do site", type="primary")
    if save:
        try:
            update_site_activity(
                process["id"],
                activity_id,
                {
                    "status": status,
                    "responsible": responsible,
                    "due_date": due_date,
                    "notes": notes,
                },
                user=nome_usuario(),
            )
            st.success("Atividade do site atualizada.")
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao atualizar atividade: {error}")


def mostrar_cancelamentos(sites, equipments):
    if not pode_consultar():
        st.warning("Seu usuário não possui permissão para consultar cancelamentos de sites.")
        return
    items = [
        ("cancelamentos_resumo", "Resumo", mostrar_resumo_cancelamentos),
        (
            "cancelamentos_processos",
            "Processos",
            lambda: mostrar_processos_cancelamento(sites, equipments),
        ),
        (
            "cancelamentos_clientes",
            "Clientes",
            lambda: mostrar_clientes_cancelamento(sites),
        ),
        ("cancelamentos_atividades_sites", "Sites", mostrar_sites_cancelamento),
    ]
    function = mostrar_subnavegacao(items, key="cancelamentos_subaba")
    if function:
        function()
