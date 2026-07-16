from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from app.auth import can_view_cost_values
from app.auth import can_view_values
from app.auth import has_permission
from app.logs import registrar_log_sistema
from app.services.feasibility_history import CLASSIFICACOES
from app.services.feasibility_history import default_dashboard_period
from app.services.feasibility_history import export_records_excel
from app.services.feasibility_history import load_imports
from app.services.feasibility_history import preview_import
from app.services.feasibility_history import records_dataframe
from app.services.feasibility_history import save_import
from app.services.feasibility_history import site_opportunity_ranking
from app.ui.components.tables import primeira_linha_selecionada
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None


def configurar_gestao_viabilidades(usuario_logado, mostrar_grid, formatar_moeda):
    global _mostrar_grid
    global _formatar_moeda
    global _usuario_logado
    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda


def usuario_atual():
    return _usuario_logado() if _usuario_logado else {}


def pode(permission):
    return has_permission(usuario_atual(), permission)


def opcoes(df, column):
    if df is None or df.empty or column not in df.columns:
        return []
    values = set()
    for value in df[column].dropna():
        for part in str(value).split(";"):
            part = part.strip()
            if part:
                values.add(part)
    return sorted(values)


def filtrar_registros(
    df,
    inicio=None,
    fim=None,
    classificacoes=None,
    sites=None,
    produtos=None,
    gerentes=None,
    cidades=None,
    tipos=None,
    status=None,
    termo="",
):
    result = df.copy()
    dates = pd.to_datetime(result.get("Data Início"), errors="coerce")
    if inicio is not None:
        result = result[dates >= pd.Timestamp(inicio)]
        dates = pd.to_datetime(result.get("Data Início"), errors="coerce")
    if fim is not None:
        result = result[dates <= pd.Timestamp(fim)]

    exact_filters = {
        "Classificação": classificacoes,
        "Gerente de Contas": gerentes,
        "Cidade": cidades,
        "Tipo Projeto": tipos,
        "Status Projeto": status,
    }
    for column, values in exact_filters.items():
        if values and column in result.columns:
            result = result[result[column].astype(str).isin(values)]

    for column, values in [("Sites localizados", sites), ("Produtos", produtos)]:
        if not values or column not in result.columns:
            continue
        mask = pd.Series(False, index=result.index)
        source = result[column].fillna("").astype(str)
        for value in values:
            mask |= source.str.split(";").apply(
                lambda parts: value in [part.strip() for part in parts]
            )
        result = result[mask]

    if termo:
        mask = pd.Series(False, index=result.index)
        for column in [
            "Projeto",
            "Nome Projeto",
            "Endereço Completo",
            "Gerente de Contas",
            "Produtos",
            "Sites candidatos",
        ]:
            if column in result.columns:
                mask |= result[column].astype(str).str.contains(
                    termo, case=False, regex=False, na=False
                )
        result = result[mask]
    return result.copy()


def _common_filters(df, prefix, include_period=True):
    start = end = None
    if include_period:
        default_start, default_end = default_dashboard_period()
        col1, col2 = st.columns(2)
        start = col1.date_input(
            "Período inicial", value=default_start, key=f"{prefix}_inicio"
        )
        end = col2.date_input(
            "Período final", value=default_end, key=f"{prefix}_fim"
        )

    row1 = st.columns(3)
    classifications = row1[0].multiselect(
        "Classificação", CLASSIFICACOES, key=f"{prefix}_classificacao"
    )
    sites = row1[1].multiselect(
        "Site candidato", opcoes(df, "Sites localizados"), key=f"{prefix}_site"
    )
    products = row1[2].multiselect(
        "Produto", opcoes(df, "Produtos"), key=f"{prefix}_produto"
    )
    row2 = st.columns(4)
    managers = row2[0].multiselect(
        "Gerente de contas", opcoes(df, "Gerente de Contas"), key=f"{prefix}_gc"
    )
    cities = row2[1].multiselect(
        "Cidade", opcoes(df, "Cidade"), key=f"{prefix}_cidade"
    )
    types = row2[2].multiselect(
        "Tipo", opcoes(df, "Tipo Projeto"), key=f"{prefix}_tipo"
    )
    statuses = row2[3].multiselect(
        "Status do projeto", opcoes(df, "Status Projeto"), key=f"{prefix}_status"
    )
    return {
        "inicio": start,
        "fim": end,
        "classificacoes": classifications,
        "sites": sites,
        "produtos": products,
        "gerentes": managers,
        "cidades": cities,
        "tipos": types,
        "status": statuses,
    }


def _show_grid(df, **kwargs):
    if _mostrar_grid:
        return _mostrar_grid(df, **kwargs)
    return st.dataframe(df, use_container_width=True, hide_index=True)


def _hide_site_values(df):
    result = df.copy()
    if not can_view_values(usuario_atual()):
        result = result.drop(columns=["Receita atual"], errors="ignore")
    if not can_view_cost_values(usuario_atual()):
        result = result.drop(columns=["Custo atual"], errors="ignore")
    return result


def _group_ranking(df, column, title, limit=20):
    if df.empty or column not in df.columns:
        st.info(f"Sem dados para {title.lower()}.")
        return
    exploded = df.assign(**{column: df[column].fillna("").astype(str).str.split(";")})
    exploded = exploded.explode(column)
    exploded[column] = exploded[column].astype(str).str.strip()
    exploded = exploded[exploded[column] != ""]
    ranking = (
        exploded.groupby(column, as_index=False)
        .size()
        .rename(columns={"size": "Solicitações"})
        .sort_values("Solicitações", ascending=False)
        .head(limit)
    )
    st.markdown(f"**{title}**")
    _show_grid(ranking, height=min(500, 80 + len(ranking) * 31), key=f"gestao_via_{column}")


def mostrar_dashboard(sites):
    st.header("Dashboard de viabilidades")
    df = records_dataframe(sites=sites)
    if df.empty:
        st.info("Nenhuma viabilidade foi importada.")
        return

    with st.expander("Filtros", expanded=True):
        filters = _common_filters(df, "gestao_via_dashboard")
    filtered = filtrar_registros(df, **filters)

    metrics = st.columns(6)
    metrics[0].metric("Solicitações", len(filtered))
    metrics[1].metric("Projetos distintos", filtered["Projeto"].nunique() if not filtered.empty else 0)
    for index, classification in enumerate(CLASSIFICACOES, start=2):
        metrics[index].metric(
            classification,
            int((filtered["Classificação"] == classification).sum()) if not filtered.empty else 0,
        )

    st.subheader("Evolução mensal")
    dates = pd.to_datetime(filtered.get("Data Início"), errors="coerce")
    monthly = filtered.assign(Mês=dates.dt.to_period("M").astype(str))
    monthly = monthly[monthly["Mês"] != "NaT"].groupby("Mês", as_index=False).size()
    monthly = monthly.rename(columns={"size": "Solicitações"})
    if monthly.empty:
        st.info("Sem datas válidas no período selecionado.")
    else:
        figure = px.line(monthly, x="Mês", y="Solicitações", markers=True)
        figure.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=340)
        st.plotly_chart(figure, use_container_width=True)

    st.subheader("Sites com oportunidades de atendimento")
    ranking = _hide_site_values(site_opportunity_ranking(filtered, sites))
    if ranking.empty:
        st.info("Nenhum caminho viável ou condicional foi localizado no período.")
    else:
        _show_grid(ranking, height=500, key="gestao_via_ranking_sites")

    col1, col2, col3 = st.columns(3)
    with col1:
        _group_ranking(filtered, "Produtos", "Produtos")
    with col2:
        _group_ranking(filtered, "Gerente de Contas", "Gerentes de contas")
    with col3:
        _group_ranking(filtered, "Cidade", "Cidades")

    st.subheader("Caminhos sem correspondência")
    unresolved = filtered[
        filtered.get("Caminhos não localizados", pd.Series(index=filtered.index, dtype=str))
        .fillna("").astype(str).str.strip().ne("")
    ][["Projeto", "Data Início", "Caminho", "Caminhos não localizados", "Cidade"]]
    if unresolved.empty:
        st.success("Todos os caminhos do período foram conciliados.")
    else:
        _show_grid(unresolved, height=350, key="gestao_via_caminhos_pendentes")


def _consultation_columns(df):
    columns = [
        "ID SGS",
        "Projeto",
        "Data Início",
        "Nome Projeto",
        "Tipo Projeto",
        "Status Projeto",
        "Classificação",
        "Condições",
        "Gerente de Contas",
        "Produtos",
        "Cidade",
        "Endereço Completo",
        "Sites candidatos",
        "Valor Mensal",
        "Valor Instalação",
    ]
    if not can_view_values(usuario_atual()):
        columns = [column for column in columns if column not in {"Valor Mensal", "Valor Instalação"}]
    return [column for column in columns if column in df.columns]


def _show_record_detail(record):
    st.subheader(f"Projeto {record.get('Projeto', '')}")
    top = st.columns(4)
    top[0].metric("Classificação", record.get("Classificação", ""))
    top[1].metric("Status", record.get("Status Projeto", ""))
    top[2].metric("Gerente", record.get("Gerente de Contas", "") or "Não informado")
    top[3].metric("Data início", record.get("Data Início", "") or "Não informada")
    st.markdown(f"**Endereço:** {record.get('Endereço Completo') or 'Não informado'}")
    st.markdown(f"**Produtos:** {record.get('Produtos') or 'Não informado'}")
    st.markdown(f"**Sites candidatos:** {record.get('Sites candidatos') or 'Não localizado'}")
    st.markdown(f"**Caminho original:** {record.get('Caminho') or 'Não informado'}")
    st.markdown(f"**Laudo RF:** {record.get('Laudo RF Viabilidade') or 'Não informado'}")
    st.markdown(f"**Justificativa:** {record.get('Justificativa RF') or 'Não informada'}")
    st.markdown(f"**Observações:** {record.get('Observação Viabilidade') or 'Não informadas'}")

    source = record.get("Dados Fonte") or {}
    if isinstance(source, dict) and source:
        hidden = {"Vlr Mens Total", "Vlr Inst Total"} if not can_view_values(usuario_atual()) else set()
        details = pd.DataFrame([
            {"Campo": key, "Valor": value}
            for key, value in source.items()
            if key not in hidden and str(value).strip()
        ])
        with st.expander("Todos os campos da fonte"):
            st.dataframe(details, use_container_width=True, hide_index=True, height=420)


def mostrar_consulta(sites):
    st.header("Consulta de viabilidades")
    df = records_dataframe(sites=sites)
    if df.empty:
        st.info("Nenhuma viabilidade foi importada.")
        return
    term = st.text_input(
        "Buscar",
        placeholder="Projeto, endereço, gerente, produto ou site",
        key="gestao_via_consulta_busca",
    )
    with st.expander("Filtros", expanded=False):
        filters = _common_filters(df, "gestao_via_consulta", include_period=False)
    filtered = filtrar_registros(df, termo=term, **filters)
    st.caption(f"{len(filtered)} solicitação(ões) encontrada(s).")

    response = _show_grid(
        filtered[_consultation_columns(filtered)],
        height=480,
        key="gestao_via_consulta_grid",
        habilitar_selecao=True,
        mostrar_abrir_site=False,
    )
    selected = primeira_linha_selecionada(response) if isinstance(response, dict) else None
    if selected:
        selected_id = selected.get("ID SGS")
        rows = filtered[filtered["ID SGS"] == selected_id]
        if not rows.empty:
            _show_record_detail(rows.iloc[0].to_dict())

    export = export_records_excel(filtered, include_proposal_values=can_view_values(usuario_atual()))
    st.download_button(
        "Baixar resultados em Excel",
        data=export,
        file_name=f"viabilidades_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="gestao_via_consulta_exportar",
    )


def _preview_summary(batch):
    columns = st.columns(4)
    columns[0].metric("Novos", batch.get("Novos", 0))
    columns[1].metric("Atualizados", batch.get("Atualizados", 0))
    columns[2].metric("Inalterados", batch.get("Inalterados", 0))
    columns[3].metric("Inválidos", batch.get("Inválidos", 0))
    columns = st.columns(4)
    columns[0].metric("Viáveis diretos", batch.get("Viáveis diretos", 0))
    columns[1].metric("Condicionais", batch.get("Viáveis condicionais", 0))
    columns[2].metric("Não viáveis", batch.get("Não viáveis", 0))
    columns[3].metric("Pendentes", batch.get("Pendentes", 0))
    columns = st.columns(2)
    columns[0].metric("Caminhos localizados", batch.get("Caminhos localizados", 0))
    columns[1].metric("Caminhos não localizados", batch.get("Caminhos não localizados", 0))


def mostrar_importacao(sites):
    st.header("Importação de viabilidades")
    st.caption(
        "O SGS lê a aba PreVendas, preserva todas as linhas e não armazena a planilha original."
    )
    upload = st.file_uploader(
        "Relatório de viabilidades",
        type=["xlsx", "xlsm"],
        key="gestao_via_importacao_arquivo",
    )

    if st.button(
        "Gerar prévia",
        disabled=upload is None,
        key="gestao_via_importacao_previa",
    ):
        try:
            with st.spinner("Lendo e conciliando as viabilidades..."):
                preview = preview_import(
                    upload,
                    sites=sites,
                    filename=upload.name,
                    user=usuario_atual().get("username", ""),
                )
            st.session_state["gestao_via_importacao_resultado"] = preview
        except Exception as error:
            st.session_state.pop("gestao_via_importacao_resultado", None)
            registrar_log_sistema(
                "gestao_viabilidades_importacao",
                usuario=usuario_atual().get("username"),
                status="erro",
                detalhes={"erro": str(error)},
            )
            st.error(f"Falha ao gerar prévia: {error}")

    preview = st.session_state.get("gestao_via_importacao_resultado")
    if preview:
        st.subheader("Prévia da importação")
        _preview_summary(preview["batch"])
        preview_df = records_dataframe(preview["records"], sites=sites)
        _show_grid(
            preview_df[_consultation_columns(preview_df)].head(100),
            height=380,
            key="gestao_via_importacao_grid",
            mostrar_abrir_site=False,
        )
        st.caption("A prévia exibe no máximo as primeiras 100 linhas.")
        confirmation = st.checkbox(
            "Confirmo a gravação desta importação",
            key="gestao_via_importacao_confirmar",
        )
        if st.button(
            "Gravar importação",
            disabled=not confirmation,
            type="primary",
            key="gestao_via_importacao_gravar",
        ):
            try:
                batch = save_import(preview)
                registrar_log_sistema(
                    "gestao_viabilidades_importacao",
                    usuario=usuario_atual().get("username"),
                    status="sucesso",
                    detalhes={
                        "arquivo": batch.get("Arquivo"),
                        "novos": batch.get("Novos"),
                        "atualizados": batch.get("Atualizados"),
                    },
                )
                st.session_state.pop("gestao_via_importacao_resultado", None)
                st.success("Importação gravada com sucesso.")
                st.rerun()
            except Exception as error:
                st.error(f"Falha ao gravar importação: {error}")

    st.subheader("Histórico de importações")
    history = pd.DataFrame(load_imports())
    if history.empty:
        st.info("Nenhuma importação gravada.")
    else:
        history = history.sort_values("Importado em", ascending=False)
        _show_grid(history, height=350, key="gestao_via_importacoes_historico", mostrar_abrir_site=False)


def mostrar_gestao_viabilidades(sites):
    user = usuario_atual()
    tabs = [
        ("gestao_viabilidades_dashboard", "Dashboard", lambda: mostrar_dashboard(sites)),
        ("gestao_viabilidades_consulta", "Consulta", lambda: mostrar_consulta(sites)),
        ("gestao_viabilidades_importar", "Importação", lambda: mostrar_importacao(sites)),
    ]
    allowed = [
        tab for tab in tabs
        if has_permission(user, "gestao_viabilidades") or has_permission(user, tab[0])
    ]
    if not allowed:
        st.warning("Seu usuário não possui permissões para Gestão de Viabilidades.")
        return
    function = mostrar_subnavegacao(allowed, key="gestao_viabilidades_subaba")
    if function:
        function()
