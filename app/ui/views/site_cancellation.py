from __future__ import annotations

import calendar
from datetime import date, datetime

import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.auth import load_users
from app.services.line_of_sight import coordenada_valida
from app.services.site_cancellation_service import ACTIVITY_STATUSES
from app.services.site_cancellation_service import CLIENT_RESULTS
from app.services.site_cancellation_service import CLIENT_STAGES
from app.services.site_cancellation_service import CLIENT_STUDY_STATUSES
from app.services.site_cancellation_service import EQUIPMENT_RESULTS
from app.services.site_cancellation_service import LINK_CATEGORIES
from app.services.site_cancellation_service import NOTIFICATION_CHANNELS
from app.services.site_cancellation_service import PROCESS_PRIORITIES
from app.services.site_cancellation_service import PROCESS_SCOPES
from app.services.site_cancellation_service import PROCESS_STATUSES
from app.services.site_cancellation_service import TEAMS
from app.services.site_cancellation_service import TICKET_STATUSES
from app.services.site_cancellation_service import add_external_link
from app.services.site_cancellation_service import add_extra_task
from app.services.site_cancellation_service import add_ticket
from app.services.site_cancellation_service import agenda_items
from app.services.site_cancellation_service import cancellation_email_text
from app.services.site_cancellation_service import cancel_process
from app.services.site_cancellation_service import compare_process_snapshot
from app.services.site_cancellation_service import complete_process
from app.services.site_cancellation_service import completion_pending_items
from app.services.site_cancellation_service import correct_migration_study
from app.services.site_cancellation_service import create_cancellation_process
from app.services.site_cancellation_service import export_cancellation_excel
from app.services.site_cancellation_service import get_cancellation_process
from app.services.site_cancellation_service import is_terminal_process
from app.services.site_cancellation_service import list_cancellation_processes
from app.services.site_cancellation_service import migration_study_rows
from app.services.site_cancellation_service import pending_migration_clients
from app.services.site_cancellation_service import process_metrics
from app.services.site_cancellation_service import reconcile_process
from app.services.site_cancellation_service import reopen_process
from app.services.site_cancellation_service import save_migration_study
from app.services.site_cancellation_service import update_child_site
from app.services.site_cancellation_service import update_client
from app.services.site_cancellation_service import update_equipment
from app.services.site_cancellation_service import update_extra_task
from app.services.site_cancellation_service import update_financial_checklist
from app.services.site_cancellation_service import update_phase
from app.services.site_cancellation_service import update_process_fields
from app.services.site_cancellation_service import update_ticket
from app.services.site_registry_service import site_pode_atender_outros_enderecos
from app.ui.components.site_selector import rotulo_busca_site
from app.ui.components.site_selector import selecionar_site_pesquisavel
from app.ui.navigation import mostrar_subnavegacao
from app.ui.views.viability import cliente_por_assinatura
from app.ui.views.viability import montar_resultados_viabilidade
from app.ui.views.viability import ponto_cliente


_usuario_logado = None
_mostrar_grid = None
_mostrar_botao_copiar_texto = None


def configurar_cancelamentos(usuario_logado, mostrar_grid=None, mostrar_botao_copiar_texto=None):
    global _usuario_logado
    global _mostrar_grid
    global _mostrar_botao_copiar_texto
    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid
    _mostrar_botao_copiar_texto = mostrar_botao_copiar_texto


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


def processo_encerrado(process):
    return is_terminal_process(process)


def pode_ver_receita():
    return has_permission(usuario_atual(), "visualizar_valores_clientes")


def pode_ver_custos():
    return has_permission(usuario_atual(), "visualizar_valores_custos")


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


def _process_dataframe(processes, show_costs):
    rows = []
    for process in processes:
        clients = process.get("clients", [])
        rows.append({
            "Processo": process.get("code"),
            "Site": process.get("site", {}).get("site_name"),
            "Nome": process.get("site", {}).get("site_label"),
            "Status": process.get("status"),
            "Prioridade": process.get("priority"),
            "Data prevista": process.get("planned_date"),
            "Responsável": process.get("responsible"),
            "Equipe": process.get("team"),
            "Clientes": len(clients),
            "Migrados": sum(1 for item in clients if item.get("final_result") == "Migrado"),
            "Pendentes": sum(1 for item in clients if item.get("final_result") == "Pendente"),
            **({"Economia mensal estimada": process.get("site", {}).get("cost", 0)} if show_costs else {}),
        })
    return pd.DataFrame(rows)


def mostrar_dashboard_cancelamentos():
    st.header("Cancelamento de Sites")
    processes = list_cancellation_processes()
    metrics = process_metrics(processes)
    cols = st.columns(5)
    cols[0].metric("Processos ativos", metrics["active_processes"])
    cols[1].metric("Atividades atrasadas", metrics["overdue_activities"])
    cols[2].metric("Próximos 7 dias", metrics["next_7_days"])
    cols[3].metric("Clientes impactados", metrics["affected_clients"])
    cols[4].metric("Equipamentos pendentes", metrics["pending_equipments"])

    cols = st.columns(4)
    cols[0].metric("Clientes migrados", metrics["migrated_clients"])
    cols[1].metric("Clientes cancelados", metrics["cancelled_clients"])
    cols[2].metric("Clientes sem solução", metrics["unsolved_clients"])
    cols[3].metric(
        "Economia mensal estimada",
        _moeda(metrics["monthly_savings"]) if pode_ver_custos() else "Restrito",
    )

    active = [item for item in processes if not processo_encerrado(item)]
    st.subheader("Processos em andamento")
    df = _process_dataframe(active, pode_ver_custos())
    if df.empty:
        st.info("Nenhum processo de cancelamento está ativo.")
    else:
        _grid(df, "cancelamentos_dashboard_processos", min(560, 80 + len(df) * 34))

    upcoming = pd.DataFrame(agenda_items(active))
    st.subheader("Próximos compromissos")
    if upcoming.empty:
        st.info("Nenhuma atividade com prazo foi encontrada.")
    else:
        upcoming = upcoming[upcoming["situation"].isin(["Atrasado", "Próximos 7 dias"])].head(20)
        _grid(upcoming.rename(columns={
            "process": "Processo", "site": "Site", "type": "Tipo", "title": "Atividade",
            "due_date": "Prazo", "status": "Status", "situation": "Situação",
            "responsible": "Responsável", "team": "Equipe",
        }).drop(columns=["process_id"], errors="ignore"), "cancelamentos_dashboard_agenda", 420)


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
            planned_date = col3.date_input("Cancelamento previsto", value=None, format="DD/MM/YYYY")
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
                process = create_cancellation_process(
                    active_sites[selected], sites, equipments,
                    scope=scope, reason=reason, priority=priority,
                    planned_date=planned_date, responsible=responsible,
                    team=team, user=nome_usuario(),
                )
                st.session_state["cancelamento_processo_selecionado"] = process["id"]
                st.success("Processo criado.")
                st.rerun()
            except Exception as error:
                st.error(f"Falha ao criar processo: {error}")


def _overview(process):
    site = process.get("site", {})
    st.subheader(f"{process.get('code')} - {site.get('site_name')}")
    st.caption(f"{site.get('site_label') or 'Sem nome cadastrado'} | Escopo: {process.get('scope')}")
    cols = st.columns(5)
    cols[0].metric("Status", process.get("status"))
    cols[1].metric("Prioridade", process.get("priority"))
    cols[2].metric("Clientes", len(process.get("clients", [])))
    cols[3].metric("Sites filhos", len(process.get("child_sites", [])))
    cols[4].metric("Equipamentos", len(process.get("equipments", [])))

    if pode_editar() and not processo_encerrado(process):
        with st.form(f"cancelamento_editar_geral_{process['id']}"):
            col1, col2, col3 = st.columns(3)
            editable_statuses = [item for item in PROCESS_STATUSES if item not in {"Concluído", "Cancelado"}]
            status = col1.selectbox("Status", editable_statuses, index=max(0, editable_statuses.index(process.get("status")) if process.get("status") in editable_statuses else 0))
            priority = col2.selectbox("Prioridade", PROCESS_PRIORITIES, index=PROCESS_PRIORITIES.index(process.get("priority")) if process.get("priority") in PROCESS_PRIORITIES else 1)
            planned = col3.date_input("Data prevista", value=_date_value(process.get("planned_date")), format="DD/MM/YYYY")
            col1, col2 = st.columns(2)
            users = _user_options()
            responsible = col1.selectbox("Responsável", users, index=users.index(process.get("responsible")) if process.get("responsible") in users else 0)
            team = col2.selectbox("Equipe", TEAMS, index=TEAMS.index(process.get("team")) if process.get("team") in TEAMS else 0)
            reason = st.text_area("Motivo", value=process.get("reason", ""), height=80)
            save = st.form_submit_button("Salvar dados gerais")
        if save:
            update_process_fields(process["id"], {
                "status": status, "priority": priority, "planned_date": planned,
                "responsible": responsible, "team": team, "reason": reason,
            }, user=nome_usuario())
            st.success("Dados gerais atualizados.")
            st.rerun()

    text = cancellation_email_text(process, pode_ver_receita(), pode_ver_custos())
    st.markdown("**Resumo para email**")
    st.code(text, language=None)
    if _mostrar_botao_copiar_texto:
        _mostrar_botao_copiar_texto(text, "Copiar resumo para email")
    st.download_button(
        "Baixar Excel",
        data=export_cancellation_excel(process, pode_ver_receita(), pode_ver_custos()),
        file_name=f"{process.get('code', 'cancelamento')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"cancelamento_excel_{process['id']}",
    )


def _run_client_study(process, item, sites):
    signature = item.get("signature")
    excluded = [item.get("site_name") for item in process.get("scope_sites", [])]
    try:
        current_site, client = cliente_por_assinatura(sites, signature)
        if client is None:
            message = "Cliente não localizado na base atual."
            save_migration_study(process["id"], signature, [], "Erro", message, user=nome_usuario())
            return "Erro", message, False
        point = ponto_cliente(current_site, client)
        if not coordenada_valida(point.get("Latitude"), point.get("Longitude")):
            message = "Cliente sem coordenadas válidas."
            save_migration_study(process["id"], signature, [], "Erro", message, user=nome_usuario())
            return "Erro", message, False
        results, _profiles = montar_resultados_viabilidade(
            sites, point,
            process.get("migration_batch", {}).get("radius_km", 10),
            limite_sites=process.get("migration_batch", {}).get("site_limit", 10),
            sites_atuais=point.get("Sites Atuais") or [],
            sites_excluidos=excluded,
        )
        records = results.to_dict(orient="records") if not results.empty else []
        statuses = {str(row.get("Status") or "") for row in records}
        if "Livre" in statuses:
            status = "Migrável"
        elif "Parcial" in statuses:
            status = "Condicional"
        else:
            status = "Não migrável"
        save_migration_study(process["id"], signature, records, status, "", user=nome_usuario())
        return status, "", False
    except Exception as error:
        message = str(error)
        save_migration_study(process["id"], signature, [], "Erro", message, user=nome_usuario())
        return "Erro", message, True


def _process_study_batch(process, sites):
    pending = pending_migration_clients(process, process.get("migration_batch", {}).get("batch_size", 10))
    if not pending:
        st.success("Todos os clientes possuem resultado de estudo.")
        return
    progress = st.progress(0, text="Preparando estudo em lote...")
    processed = 0
    for index, item in enumerate(pending, start=1):
        signature = item.get("signature")
        progress.progress((index - 1) / len(pending), text=f"Analisando {item.get('name')} ({signature})")
        _status, message, interrupted = _run_client_study(process, item, sites)
        processed += 1
        if interrupted:
            st.error(f"O lote foi interrompido em {signature}: {message}")
            break
    progress.progress(1.0, text=f"{processed} cliente(s) processado(s).")
    st.rerun()


def _eligible_destination_sites(process, sites):
    excluded = {item.get("site_name") for item in process.get("scope_sites", [])}
    return {
        name: site for name, site in (sites or {}).items()
        if name not in excluded
        and str(getattr(site, "status_cadastro", "") or "").strip().casefold() == "ativo"
        and site_pode_atender_outros_enderecos(site)
    }


def mostrar_estudos_migracao(sites):
    st.header("Estudos de Migração")
    st.caption("Revise os resultados automáticos, consulte os candidatos e registre correções justificadas.")
    notice = st.session_state.pop("cancelamentos_estudos_aviso", None)
    if notice:
        getattr(st, notice.get("type", "success"))(notice.get("message", ""))
    include_completed = st.checkbox("Incluir processos encerrados", key="cancelamentos_estudos_incluir_concluidos")
    processes = list_cancellation_processes()
    rows = migration_study_rows(processes, include_completed=include_completed)
    if not rows:
        st.info("Nenhum estudo de migração foi encontrado.")
        return

    metrics = st.columns(6)
    metrics[0].metric("Estudos", len(rows))
    for column, status in zip(metrics[1:], ["Pendente", "Erro", "Migrável", "Condicional", "Não migrável"]):
        column.metric(status, sum(1 for item in rows if item["study_status"] == status))

    process_labels = {
        process["id"]: f"{process.get('code', '')} - {process.get('site', {}).get('site_name', '')}"
        for process in processes
        if include_completed or not processo_encerrado(process)
    }
    col1, col2, col3 = st.columns([2, 1.4, 1.4])
    search = col1.text_input(
        "Buscar cliente", placeholder="Nome, assinatura, site atual ou site em cancelamento",
        key="cancelamentos_estudos_busca",
    )
    process_filter = col2.multiselect(
        "Processos", list(process_labels), format_func=lambda value: process_labels[value],
        key="cancelamentos_estudos_processos",
    )
    status_filter = col3.multiselect(
        "Resultado", CLIENT_STUDY_STATUSES, key="cancelamentos_estudos_status",
    )
    filtered = []
    for item in rows:
        searchable = " ".join([
            item["client"], item["signature"], item["current_sites"],
            item["cancellation_site"], item["process_code"],
        ]).casefold()
        if search and search.casefold() not in searchable:
            continue
        if process_filter and item["process_id"] not in process_filter:
            continue
        if status_filter and item["study_status"] not in status_filter:
            continue
        filtered.append(item)

    display = pd.DataFrame([{
        "Processo": item["process_code"],
        "Status do processo": item["process_status"],
        "Site em cancelamento": item["cancellation_site"],
        "Assinatura": item["signature"],
        "Cliente": item["client"],
        "Sites atuais": item["current_sites"],
        "Resultado": item["study_status"],
        "Origem": item["study_source"],
        "Atualizado em": item["study_updated_at"],
        "Corrigido em": item["corrected_at"],
        "Corrigido por": item["corrected_by"],
        "Candidatos": item["candidate_count"],
        "Site destino": item["destination_site"],
        "Resultado final": item["final_result"],
        "Mensagem": item["study_message"],
    } for item in filtered])
    if display.empty:
        st.info("Nenhum estudo atende aos filtros selecionados.")
        return
    _grid(display, "cancelamentos_estudos_lista", min(620, 100 + len(display) * 34))

    row_by_key = {f"{item['process_id']}|{item['signature']}": item for item in filtered}
    labels = {
        key: f"{item['client']} - {item['signature']} / {item['process_code']}"
        for key, item in row_by_key.items()
    }
    selected_key = st.selectbox(
        "Estudo para verificar", list(labels), index=None,
        placeholder="Digite para pesquisar e selecione um estudo",
        format_func=lambda value: labels[value], key="cancelamentos_estudo_selecionado",
    )
    if not selected_key:
        return
    row = row_by_key[selected_key]
    process = get_cancellation_process(row["process_id"])
    if not process:
        st.error("O processo selecionado não está mais disponível.")
        return
    client = next(
        (item for item in process.get("clients", []) if item.get("signature") == row["signature"]),
        None,
    )
    if not client:
        st.error("O cliente selecionado não está mais disponível neste processo.")
        return

    st.markdown(f"### {client.get('name')} - {client.get('signature')}")
    detail_columns = st.columns(4)
    detail_columns[0].metric("Resultado", client.get("study_status") or "Pendente")
    detail_columns[1].metric("Origem", client.get("study_source") or "Não processado")
    detail_columns[2].metric("Candidatos", len(client.get("study_candidates", []) or []))
    detail_columns[3].metric("Site destino", client.get("destination_site") or "Não definido")
    if client.get("study_message"):
        st.warning(f"Mensagem do processamento: {client['study_message']}")
    if client.get("study_correction_reason"):
        st.info(
            f"Correção de {client.get('study_corrected_by') or 'usuário não informado'}: "
            f"{client['study_correction_reason']}"
        )

    candidates = pd.DataFrame(client.get("study_candidates", []) or [])
    st.markdown("**Candidatos calculados**")
    if candidates.empty:
        st.caption("O processamento não salvou sites candidatos para esta assinatura.")
    else:
        st.dataframe(candidates, use_container_width=True, hide_index=True)

    if not pode_editar() or processo_encerrado(process):
        return
    if st.button("Reprocessar estudo selecionado", key=f"cancelamento_reprocessar_{selected_key}"):
        with st.spinner("Reprocessando estudo de migração..."):
            status, message, _interrupted = _run_client_study(process, client, sites)
        if status == "Erro":
            st.session_state["cancelamentos_estudos_aviso"] = {
                "type": "error", "message": f"O estudo retornou erro: {message}",
            }
        else:
            st.session_state["cancelamentos_estudos_aviso"] = {
                "type": "success", "message": f"Estudo reprocessado: {status}.",
            }
        st.rerun()

    eligible_sites = _eligible_destination_sites(process, sites)
    site_options = [""] + sorted(eligible_sites, key=lambda name: rotulo_busca_site(eligible_sites[name]).casefold())
    current_destination = client.get("destination_site", "")
    if current_destination and current_destination not in site_options:
        site_options.append(current_destination)
    site_labels = {"": "Não definido"}
    site_labels.update({name: rotulo_busca_site(site) for name, site in eligible_sites.items()})
    site_labels.setdefault(current_destination, current_destination)
    manual_statuses = [status for status in CLIENT_STUDY_STATUSES if status != "Em processamento"]
    with st.form(f"cancelamento_correcao_estudo_{selected_key}"):
        st.markdown("**Correção manual**")
        st.caption("A correção preserva os candidatos técnicos calculados e fica registrada no histórico do processo.")
        col1, col2 = st.columns(2)
        current_status = client.get("study_status")
        status = col1.selectbox(
            "Resultado revisado", manual_statuses,
            index=manual_statuses.index(current_status) if current_status in manual_statuses else 0,
        )
        destination = col2.selectbox(
            "Site destino", site_options,
            index=site_options.index(current_destination) if current_destination in site_options else 0,
            format_func=lambda value: site_labels.get(value, value),
        )
        reason = st.text_area("Motivo da correção", height=90)
        submit = st.form_submit_button("Salvar correção manual")
    if submit:
        try:
            correct_migration_study(
                process["id"], client["signature"], status, destination, reason,
                user=nome_usuario(),
            )
            st.session_state["cancelamentos_estudos_aviso"] = {
                "type": "success", "message": "Correção manual registrada.",
            }
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao registrar correção: {error}")


def _clients_section(process, sites):
    clients = process.get("clients", [])
    batch = process.get("migration_batch", {})
    st.caption(f"Estudos processados: {batch.get('processed', 0)} de {batch.get('total', len(clients))}")
    if pode_editar() and not processo_encerrado(process):
        if st.button("Processar próximo lote de estudos", key=f"cancelamento_lote_{process['id']}"):
            _process_study_batch(process, sites)
    rows = []
    for item in clients:
        current_sites = ", ".join(link.get("site", "") for link in item.get("current_links", []))
        rows.append({
            "Assinatura": item.get("signature"), "Cliente": item.get("name"), "Produto": item.get("product"),
            "Gerente de Contas": item.get("manager"), "Sites atuais": current_sites,
            "Atendimento remanescente": "Sim" if item.get("has_remaining_service") else "Não",
            "Estudo": item.get("study_status"), "Etapa": item.get("stage"),
            "Site destino": item.get("destination_site"), "Resultado final": item.get("final_result"),
            "Prazo": item.get("due_date"), "Responsável": item.get("responsible"),
            **({"Receita": item.get("revenue", 0)} if pode_ver_receita() else {}),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        _grid(df, f"cancelamento_clientes_{process['id']}", min(580, 100 + len(df) * 32))
    else:
        st.info("Nenhum cliente foi identificado no escopo.")
        return
    if not pode_editar() or processo_encerrado(process):
        return
    labels = {item["signature"]: f"{item.get('name')} - {item['signature']}" for item in clients}
    signature = st.selectbox("Cliente para atualizar", list(labels), format_func=lambda value: labels[value], key=f"cancelamento_cliente_sel_{process['id']}")
    selected = next(item for item in clients if item["signature"] == signature)
    with st.form(f"cancelamento_cliente_form_{process['id']}_{signature}"):
        col1, col2, col3 = st.columns(3)
        stage = col1.selectbox("Etapa", CLIENT_STAGES, index=CLIENT_STAGES.index(selected.get("stage")) if selected.get("stage") in CLIENT_STAGES else 0)
        result = col2.selectbox("Resultado final", CLIENT_RESULTS, index=CLIENT_RESULTS.index(selected.get("final_result")) if selected.get("final_result") in CLIENT_RESULTS else 0)
        destination = col3.text_input("Site destino", value=selected.get("destination_site", ""))
        col1, col2, col3 = st.columns(3)
        users = _user_options()
        responsible = col1.selectbox("Responsável", users, index=users.index(selected.get("responsible")) if selected.get("responsible") in users else 0)
        team = col2.selectbox("Equipe", TEAMS, index=TEAMS.index(selected.get("team")) if selected.get("team") in TEAMS else 0)
        due = col3.date_input("Prazo", value=_date_value(selected.get("due_date")), format="DD/MM/YYYY")
        notes = st.text_area("Observações", value=selected.get("notes", ""), height=80)
        st.markdown("**Notificação**")
        notification = selected.get("notification", {})
        col1, col2, col3 = st.columns(3)
        notification_date = col1.date_input("Data da notificação", value=_date_value(notification.get("date")), format="DD/MM/YYYY")
        channel_options = [""] + NOTIFICATION_CHANNELS
        channel = col2.selectbox("Canal", channel_options, index=channel_options.index(notification.get("channel")) if notification.get("channel") in channel_options else 0)
        protocol = col3.text_input("Protocolo", value=notification.get("protocol", ""))
        link = st.text_input("Link da evidência", value=notification.get("link", ""))
        notification_notes = st.text_input("Observação da notificação", value=notification.get("notes", ""))
        save = st.form_submit_button("Salvar cliente")
    if save:
        update_client(process["id"], signature, {
            "stage": stage, "final_result": result, "destination_site": destination,
            "responsible": responsible, "team": team, "due_date": due, "notes": notes,
            "notification": {
                "date": notification_date.isoformat() if notification_date else "",
                "channel": channel, "protocol": protocol, "link": link, "notes": notification_notes,
            },
        }, user=nome_usuario())
        st.success("Cliente atualizado.")
        st.rerun()
    if selected.get("study_candidates"):
        with st.expander("Resultado técnico salvo", expanded=False):
            st.dataframe(pd.DataFrame(selected["study_candidates"]), use_container_width=True, hide_index=True)


def _children_section(process):
    children = process.get("child_sites", [])
    if not children:
        st.info("O processo não possui sites filhos no escopo.")
        return
    df = pd.DataFrame([{
        "Site": item.get("site_name"), "Nome": item.get("site_label"), "Novo site pai": item.get("new_parent"),
        "Chamado": item.get("ticket"), "Status": item.get("status"), "Prazo": item.get("due_date"),
        "Responsável": item.get("responsible"), "Equipe": item.get("team"),
    } for item in children])
    _grid(df, f"cancelamento_filhos_{process['id']}", min(500, 90 + len(df) * 34))
    if not pode_editar() or processo_encerrado(process):
        return
    labels = {item["site_name"]: rotulo_busca_site({
        "Site SNMPc": item.get("site_name"), "Codigo": item.get("aquiles"),
        "Nome Cadastro": item.get("site_label"), "Microsiga": item.get("microsiga"),
    }) for item in children}
    site_name = st.selectbox("Site filho para atualizar", list(labels), format_func=lambda value: labels[value], key=f"cancelamento_filho_sel_{process['id']}")
    selected = next(item for item in children if item["site_name"] == site_name)
    with st.form(f"cancelamento_filho_form_{process['id']}_{site_name}"):
        col1, col2, col3 = st.columns(3)
        new_parent = col1.text_input("Novo site pai/enlace", value=selected.get("new_parent", ""))
        ticket = col2.text_input("Chamado", value=selected.get("ticket", ""))
        status = col3.selectbox("Status", ACTIVITY_STATUSES, index=ACTIVITY_STATUSES.index(selected.get("status")) if selected.get("status") in ACTIVITY_STATUSES else 0)
        col1, col2, col3 = st.columns(3)
        users = _user_options()
        responsible = col1.selectbox("Responsável", users, index=users.index(selected.get("responsible")) if selected.get("responsible") in users else 0)
        team = col2.selectbox("Equipe", TEAMS, index=TEAMS.index(selected.get("team")) if selected.get("team") in TEAMS else 0)
        due = col3.date_input("Prazo", value=_date_value(selected.get("due_date")), format="DD/MM/YYYY")
        notes = st.text_area("Observações", value=selected.get("notes", ""))
        save = st.form_submit_button("Salvar site filho")
    if save:
        update_child_site(process["id"], site_name, {
            "new_parent": new_parent, "ticket": ticket, "status": status,
            "responsible": responsible, "team": team, "due_date": due, "notes": notes,
        }, user=nome_usuario())
        st.success("Site filho atualizado.")
        st.rerun()


def _financial_section(process):
    financial = process.get("financial", {})
    cols = st.columns(4)
    cols[0].metric("Parcelas vencidas", financial.get("overdue_count", 0))
    cols[1].metric("Valor vencido", _moeda(financial.get("overdue_value")) if pode_ver_custos() else "Restrito")
    cols[2].metric("Acordos abertos", financial.get("open_agreements_count", 0))
    cols[3].metric("Custo mensal", _moeda(financial.get("cost")) if pode_ver_custos() else "Restrito")
    if pode_ver_custos():
        for title, key in [
            ("Parcelas vencidas", "overdue_items"), ("Parcelas futuras", "future_items"), ("Acordos", "agreement_items")
        ]:
            items = pd.DataFrame(financial.get(key, []))
            if not items.empty:
                with st.expander(title, expanded=False):
                    st.dataframe(items, use_container_width=True, hide_index=True)
    if pode_editar() and not processo_encerrado(process):
        with st.form(f"cancelamento_financeiro_{process['id']}"):
            survey = st.checkbox("Levantamento financeiro conferido", value=bool(financial.get("survey_confirmed")))
            settlement = st.checkbox("Regularização financeira concluída ou encaminhada", value=bool(financial.get("settlement_confirmed")))
            notes = st.text_area("Observações financeiras", value=financial.get("notes", ""))
            save = st.form_submit_button("Salvar financeiro")
        if save:
            update_financial_checklist(process["id"], {
                "survey_confirmed": survey, "settlement_confirmed": settlement, "notes": notes,
            }, user=nome_usuario())
            st.success("Checklist financeiro atualizado.")
            st.rerun()


def _equipment_section(process):
    equipments = process.get("equipments", [])
    if not equipments:
        st.info("Nenhum equipamento foi identificado no snapshot.")
        return
    df = pd.DataFrame([{
        "Equipamento": item.get("equipment") or item.get("icon"), "Ícone": item.get("icon"),
        "IP": item.get("address"), "Site": item.get("site"), "Assinatura": item.get("signature"),
        "Resultado": item.get("result"), "Destino": item.get("destination"),
        "Data": item.get("date"), "Responsável": item.get("responsible"), "Situação na base": item.get("current_state"),
    } for item in equipments])
    _grid(df, f"cancelamento_equipamentos_{process['id']}", min(600, 100 + len(df) * 32))
    if not pode_editar() or processo_encerrado(process):
        return
    labels = {item["id"]: f"{item.get('equipment') or item.get('icon') or 'Equipamento'} / {item.get('address') or '-'} / {item.get('site') or '-'}" for item in equipments}
    equipment_id = st.selectbox("Equipamento para atualizar", list(labels), format_func=lambda value: labels[value], key=f"cancelamento_equip_sel_{process['id']}")
    selected = next(item for item in equipments if item["id"] == equipment_id)
    with st.form(f"cancelamento_equip_form_{process['id']}_{equipment_id}"):
        col1, col2, col3 = st.columns(3)
        result = col1.selectbox("Resultado", EQUIPMENT_RESULTS, index=EQUIPMENT_RESULTS.index(selected.get("result")) if selected.get("result") in EQUIPMENT_RESULTS else 0)
        destination = col2.text_input("Destino", value=selected.get("destination", ""))
        users = _user_options()
        responsible = col3.selectbox("Responsável", users, index=users.index(selected.get("responsible")) if selected.get("responsible") in users else 0)
        item_date = st.date_input("Data", value=_date_value(selected.get("date")), format="DD/MM/YYYY")
        notes = st.text_area("Observações", value=selected.get("notes", ""))
        save = st.form_submit_button("Salvar equipamento")
    if save:
        update_equipment(process["id"], equipment_id, {
            "result": result, "destination": destination, "responsible": responsible,
            "date": item_date, "notes": notes,
        }, user=nome_usuario())
        st.success("Equipamento atualizado.")
        st.rerun()


def _tasks_section(process):
    phases = process.get("phases", [])
    tasks = process.get("extra_tasks", [])
    rows = [{**item, "type": "Etapa padrão"} for item in phases] + [{**item, "type": "Atividade extra"} for item in tasks]
    df = pd.DataFrame([{
        "Tipo": item.get("type"), "Atividade": item.get("name"), "Status": item.get("status"),
        "Responsável": item.get("responsible"), "Equipe": item.get("team"), "Prazo": item.get("due_date"),
        "Observações": item.get("notes"),
    } for item in rows])
    _grid(df, f"cancelamento_tarefas_{process['id']}", min(560, 100 + len(df) * 34))
    if not pode_editar() or processo_encerrado(process):
        return
    labels = {}
    for item in phases:
        labels[f"phase:{item['id']}"] = f"Etapa padrão: {item['name']}"
    for item in tasks:
        labels[f"task:{item['id']}"] = f"Atividade extra: {item['name']}"
    selected_key = st.selectbox("Atividade para atualizar", list(labels), format_func=lambda value: labels[value], key=f"cancelamento_tarefa_sel_{process['id']}")
    kind, item_id = selected_key.split(":", 1)
    selected = next(item for item in (phases if kind == "phase" else tasks) if item["id"] == item_id)
    with st.form(f"cancelamento_tarefa_form_{process['id']}_{item_id}"):
        col1, col2, col3 = st.columns(3)
        status = col1.selectbox("Status", ACTIVITY_STATUSES, index=ACTIVITY_STATUSES.index(selected.get("status")) if selected.get("status") in ACTIVITY_STATUSES else 0)
        users = _user_options()
        responsible = col2.selectbox("Responsável", users, index=users.index(selected.get("responsible")) if selected.get("responsible") in users else 0)
        team = col3.selectbox("Equipe", TEAMS, index=TEAMS.index(selected.get("team")) if selected.get("team") in TEAMS else 0)
        due = st.date_input("Prazo", value=_date_value(selected.get("due_date")), format="DD/MM/YYYY")
        notes = st.text_area("Observações", value=selected.get("notes", ""))
        save = st.form_submit_button("Salvar atividade")
    if save:
        function = update_phase if kind == "phase" else update_extra_task
        function(process["id"], item_id, {
            "status": status, "responsible": responsible, "team": team, "due_date": due, "notes": notes,
        }, user=nome_usuario())
        st.success("Atividade atualizada.")
        st.rerun()
    with st.expander("Adicionar atividade extra", expanded=False):
        with st.form(f"cancelamento_nova_tarefa_{process['id']}"):
            name = st.text_input("Atividade")
            col1, col2, col3 = st.columns(3)
            responsible = col1.selectbox("Responsável", _user_options(), key=f"nova_tarefa_resp_{process['id']}")
            team = col2.selectbox("Equipe", TEAMS, key=f"nova_tarefa_team_{process['id']}")
            due = col3.date_input("Prazo", value=None, format="DD/MM/YYYY")
            notes = st.text_area("Observações")
            add = st.form_submit_button("Adicionar atividade")
        if add:
            add_extra_task(process["id"], {
                "name": name, "responsible": responsible, "team": team, "due_date": due, "notes": notes,
            }, user=nome_usuario())
            st.success("Atividade adicionada.")
            st.rerun()


def _tickets_links_section(process):
    tickets = process.get("tickets", [])
    links = process.get("links", [])
    st.markdown("**Chamados técnicos**")
    if tickets:
        _grid(pd.DataFrame([{
            "Número": item.get("number"), "Status": item.get("status"),
            "Assinaturas": ", ".join(item.get("signatures", [])), "Observações": item.get("notes"),
        } for item in tickets]), f"cancelamento_chamados_{process['id']}", min(400, 80 + len(tickets) * 34))
    else:
        st.caption("Nenhum chamado registrado.")
    if pode_editar() and not processo_encerrado(process):
        with st.expander("Adicionar chamado", expanded=False):
            with st.form(f"cancelamento_novo_chamado_{process['id']}"):
                col1, col2 = st.columns(2)
                number = col1.text_input("Número")
                status = col2.selectbox("Status", TICKET_STATUSES, index=1)
                signatures = st.multiselect(
                    "Assinaturas relacionadas", [item.get("signature") for item in process.get("clients", [])],
                    format_func=lambda value: next((f"{item.get('name')} - {value}" for item in process.get("clients", []) if item.get("signature") == value), value),
                )
                notes = st.text_area("Observações")
                add = st.form_submit_button("Adicionar chamado")
            if add:
                add_ticket(process["id"], {"number": number, "status": status, "signatures": signatures, "notes": notes}, user=nome_usuario())
                st.success("Chamado adicionado.")
                st.rerun()
        if tickets:
            ticket_labels = {item["id"]: item.get("number") for item in tickets}
            ticket_id = st.selectbox("Chamado para atualizar", list(ticket_labels), format_func=lambda value: ticket_labels[value], key=f"cancelamento_ticket_sel_{process['id']}")
            selected = next(item for item in tickets if item["id"] == ticket_id)
            with st.form(f"cancelamento_ticket_form_{process['id']}_{ticket_id}"):
                col1, col2 = st.columns(2)
                number = col1.text_input("Número", value=selected.get("number", ""))
                status = col2.selectbox("Status", TICKET_STATUSES, index=TICKET_STATUSES.index(selected.get("status")) if selected.get("status") in TICKET_STATUSES else 0)
                signatures = st.multiselect("Assinaturas relacionadas", [item.get("signature") for item in process.get("clients", [])], default=selected.get("signatures", []))
                notes = st.text_area("Observações", value=selected.get("notes", ""))
                save = st.form_submit_button("Salvar chamado")
            if save:
                update_ticket(process["id"], ticket_id, {"number": number, "status": status, "signatures": signatures, "notes": notes}, user=nome_usuario())
                st.success("Chamado atualizado.")
                st.rerun()

    st.markdown("**Referências externas**")
    if links:
        for item in links:
            st.markdown(f"- **{item.get('category')}**: [{item.get('title')}]({item.get('url')})")
    else:
        st.caption("Nenhuma referência externa registrada.")
    if pode_editar() and not processo_encerrado(process):
        with st.expander("Adicionar referência externa", expanded=False):
            with st.form(f"cancelamento_novo_link_{process['id']}"):
                col1, col2 = st.columns(2)
                category = col1.selectbox("Categoria", LINK_CATEGORIES)
                title = col2.text_input("Título")
                url = st.text_input("URL")
                notes = st.text_input("Observações")
                add = st.form_submit_button("Adicionar referência")
            if add:
                add_external_link(process["id"], {"category": category, "title": title, "url": url, "notes": notes}, user=nome_usuario())
                st.success("Referência adicionada.")
                st.rerun()


def _reconciliation_section(process, sites, equipments):
    comparison = compare_process_snapshot(process, sites, equipments)
    cols = st.columns(4)
    cols[0].metric("Novos clientes", len(comparison["new_clients"]))
    cols[1].metric("Clientes ausentes", len(comparison["missing_clients"]))
    cols[2].metric("Novos equipamentos", len(comparison["new_equipments"]))
    cols[3].metric("Equipamentos ausentes", len(comparison["missing_equipments"]))
    if comparison.get("site_missing"):
        st.error("O site principal não existe na base técnica atual.")
    if comparison["new_clients"]:
        st.dataframe(pd.DataFrame(comparison["new_clients"])[["signature", "name", "product"]], use_container_width=True, hide_index=True)
    if pode_editar() and not processo_encerrado(process) and st.button("Aplicar conciliação", key=f"cancelamento_reconciliar_{process['id']}"):
        reconcile_process(process["id"], sites, equipments, user=nome_usuario())
        st.success("Snapshot conciliado sem remover o histórico.")
        st.rerun()


def _completion_section(process):
    if process.get("status") == "Cancelado":
        st.warning("Processo cancelado. Os dados foram preservados somente para consulta.")
        st.markdown(f"**Cancelado em:** {process.get('canceled_at') or 'Não informado'}")
        st.markdown(f"**Cancelado por:** {process.get('canceled_by') or 'Não informado'}")
        st.markdown(f"**Justificativa:** {process.get('cancellation_reason') or 'Não informada'}")
        st.caption("Este processo não pode ser reativado. Abra um novo processo para retomar o trabalho do site.")
        return
    pending = completion_pending_items(process)
    if pending:
        st.warning("O processo possui pendências:")
        for item in pending:
            st.markdown(f"- {item}")
    else:
        st.success("Todas as validações obrigatórias estão concluídas.")
    if process.get("status") == "Concluído":
        st.info(f"Concluído em {process.get('completed_at')} por {process.get('completed_by')}.")
        if process.get("completion_justification"):
            st.caption(f"Justificativa: {process.get('completion_justification')}")
        if pode_concluir():
            with st.form(f"cancelamento_reabrir_{process['id']}"):
                justification = st.text_area("Justificativa da reabertura")
                confirmation = st.text_input("Digite REABRIR para confirmar")
                submit = st.form_submit_button("Reabrir processo")
            if submit:
                if confirmation.strip().upper() != "REABRIR":
                    st.error("Digite REABRIR para confirmar.")
                else:
                    reopen_process(process["id"], justification=justification, user=nome_usuario())
                    st.success("Processo reaberto. O cadastro do site permanece Cancelado até nova conclusão.")
                    st.rerun()
        return
    if not pode_concluir():
        st.caption("Seu usuário não possui permissão para concluir ou cancelar este processo.")
        return
    with st.form(f"cancelamento_concluir_{process['id']}"):
        justification = st.text_area("Justificativa para conclusão com pendências", help="Obrigatória somente quando houver pendências.")
        confirmation = st.text_input("Digite CONCLUIR para confirmar")
        submit = st.form_submit_button("Concluir e cancelar o site", type="primary")
    if submit:
        if confirmation.strip().upper() != "CONCLUIR":
            st.error("Digite CONCLUIR para confirmar.")
            return
        try:
            complete_process(process["id"], justification=justification, user=nome_usuario())
            st.success("Processo concluído e site marcado como Cancelado.")
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao concluir processo: {error}")

    st.divider()
    st.markdown("**Processo aberto por engano**")
    st.caption("O cancelamento preserva o histórico, não altera o site e libera uma nova abertura para o mesmo local.")
    with st.form(f"cancelamento_cancelar_processo_{process['id']}"):
        cancellation_reason = st.text_area("Justificativa do cancelamento do processo")
        cancellation_confirmation = st.text_input("Digite CANCELAR para confirmar")
        cancel = st.form_submit_button("Cancelar processo")
    if cancel:
        if cancellation_confirmation.strip().upper() != "CANCELAR":
            st.error("Digite CANCELAR para confirmar.")
            return
        try:
            cancel_process(
                process["id"], reason=cancellation_reason, user=nome_usuario()
            )
            st.success("Processo cancelado. O cadastro do site não foi alterado.")
            st.rerun()
        except Exception as error:
            st.error(f"Falha ao cancelar processo: {error}")


def _process_detail(process, sites, equipments):
    sections = [
        ("resumo", "Resumo"), ("clientes", "Clientes"), ("filhos", "Sites filhos"),
        ("financeiro", "Financeiro"), ("equipamentos", "Equipamentos"),
        ("tarefas", "Tarefas"), ("chamados", "Chamados e links"),
        ("conciliacao", "Conciliação"), ("conclusao", "Conclusão"),
    ]
    keys = [item[0] for item in sections]
    labels = dict(sections)
    state_key = f"cancelamento_secao_{process['id']}"
    if st.session_state.get(state_key) not in keys:
        st.session_state[state_key] = "resumo"
    section = st.segmented_control(
        "Seção", keys, key=state_key, format_func=lambda value: labels[value],
        selection_mode="single", width="stretch", label_visibility="collapsed",
    ) or "resumo"
    handlers = {
        "resumo": lambda: _overview(process),
        "clientes": lambda: _clients_section(process, sites),
        "filhos": lambda: _children_section(process),
        "financeiro": lambda: _financial_section(process),
        "equipamentos": lambda: _equipment_section(process),
        "tarefas": lambda: _tasks_section(process),
        "chamados": lambda: _tickets_links_section(process),
        "conciliacao": lambda: _reconciliation_section(process, sites, equipments),
        "conclusao": lambda: _completion_section(process),
    }
    handlers[section]()


def mostrar_processos_cancelamento(sites, equipments):
    st.header("Processos de Cancelamento")
    _create_process_form(sites, equipments)
    processes = list_cancellation_processes()
    if not processes:
        st.info("Nenhum processo de cancelamento foi registrado.")
        return
    col1, col2, col3 = st.columns([2, 1, 1])
    search = col1.text_input("Buscar processo", placeholder="Site, código, responsável ou processo")
    status_filter = col2.multiselect("Status", PROCESS_STATUSES)
    priority_filter = col3.multiselect("Prioridade", PROCESS_PRIORITIES)
    filtered = []
    for process in processes:
        searchable = " ".join([
            process.get("code", ""), process.get("site", {}).get("site_name", ""),
            process.get("site", {}).get("site_label", ""), process.get("site", {}).get("aquiles", ""),
            process.get("responsible", ""), process.get("team", ""),
        ]).casefold()
        if search and search.casefold() not in searchable:
            continue
        if status_filter and process.get("status") not in status_filter:
            continue
        if priority_filter and process.get("priority") not in priority_filter:
            continue
        filtered.append(process)
    labels = {process["id"]: _process_label(process) for process in filtered}
    if st.session_state.get("cancelamento_processo_selecionado") not in labels:
        st.session_state.pop("cancelamento_processo_selecionado", None)
    selected_id = st.selectbox(
        "Processo", list(labels), index=None, placeholder="Digite para pesquisar e selecione um processo",
        format_func=lambda value: labels[value], key="cancelamento_processo_selecionado",
    )
    if not selected_id:
        df = _process_dataframe(filtered, pode_ver_custos())
        if not df.empty:
            _grid(df, "cancelamentos_processos_lista", min(580, 100 + len(df) * 34))
        return
    process = get_cancellation_process(selected_id)
    if process:
        _process_detail(process, sites, equipments)


def _calendar_dataframe(items, year, month):
    counts = {}
    for item in items:
        day = _date_value(item.get("due_date"))
        if day and day.year == year and day.month == month:
            counts.setdefault(day.day, []).append(item)
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    rows = []
    for week in weeks:
        row = {}
        for label, day in zip(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"], week):
            if not day:
                row[label] = ""
                continue
            entries = counts.get(day, [])
            overdue = sum(1 for item in entries if item.get("situation") == "Atrasado")
            row[label] = f"{day}\n{len(entries)} compromisso(s)" + (f"\n{overdue} atrasado(s)" if overdue else "")
        rows.append(row)
    return pd.DataFrame(rows)


def mostrar_agenda_cancelamentos():
    st.header("Agenda de Cancelamentos")
    processes = list_cancellation_processes()
    items = agenda_items([item for item in processes if not processo_encerrado(item)])
    reference = st.date_input("Mês", value=date.today(), format="DD/MM/YYYY", key="cancelamento_agenda_mes")
    col1, col2, col3 = st.columns(3)
    teams = col1.multiselect("Equipe", TEAMS)
    situations = col2.multiselect("Situação", ["Atrasado", "Próximos 7 dias", "Programado", "Concluído"])
    responsible = col3.multiselect("Responsável", _user_options()[1:])
    filtered = [item for item in items if (
        (not teams or item.get("team") in teams)
        and (not situations or item.get("situation") in situations)
        and (not responsible or item.get("responsible") in responsible)
    )]
    st.markdown(f"**{calendar.month_name[reference.month].capitalize()} de {reference.year}**")
    st.dataframe(_calendar_dataframe(filtered, reference.year, reference.month), use_container_width=True, hide_index=True)
    month_items = [item for item in filtered if _date_value(item.get("due_date")) and _date_value(item.get("due_date")).year == reference.year and _date_value(item.get("due_date")).month == reference.month]
    if month_items:
        _grid(pd.DataFrame(month_items).rename(columns={
            "process": "Processo", "site": "Site", "type": "Tipo", "title": "Atividade",
            "due_date": "Prazo", "status": "Status", "situation": "Situação",
            "responsible": "Responsável", "team": "Equipe",
        }).drop(columns=["process_id"], errors="ignore"), "cancelamentos_agenda_lista", min(620, 100 + len(month_items) * 34))
    else:
        st.info("Nenhum compromisso encontrado para o mês selecionado.")


def mostrar_cancelamentos(sites, equipments):
    if not pode_consultar():
        st.warning("Seu usuário não possui permissão para consultar cancelamentos de sites.")
        return
    items = [
        ("cancelamentos_dashboard", "Dashboard", mostrar_dashboard_cancelamentos),
        ("cancelamentos_processos", "Processos", lambda: mostrar_processos_cancelamento(sites, equipments)),
        ("cancelamentos_estudos", "Estudos de Migração", lambda: mostrar_estudos_migracao(sites)),
        ("cancelamentos_agenda", "Agenda", mostrar_agenda_cancelamentos),
    ]
    function = mostrar_subnavegacao(items, key="cancelamentos_subaba")
    if function:
        function()
