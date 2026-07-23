import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from app.auth import has_permission
from app.logs import registrar_log_sistema
from app.services.finance_service import AGREEMENT_COLUMNS
from app.services.finance_service import AGREEMENT_STATUSES
from app.services.finance_service import PAYMENT_COLUMNS
from app.services.finance_service import PAYMENT_STATUSES
from app.services.finance_service import analisar_conciliacao_financeira
from app.services.finance_service import carregar_acordos
from app.services.finance_service import carregar_pagamentos
from app.services.finance_service import dashboard_financeiro
from app.services.finance_service import dataframe_para_excel
from app.services.finance_service import exportar_conciliacao_financeira_excel
from app.services.finance_service import historico_financeiro_site
from app.services.finance_service import importar_planilha_financeira
from app.services.finance_service import preparar_acordos_exibicao
from app.services.finance_service import preparar_pagamentos_exibicao
from app.services.finance_service import salvar_acordos
from app.services.finance_service import salvar_pagamentos
from app.services.finance_service import sites_financeiros_cadastrados
from app.services.critical_alerts import status_alertas_criticos
from app.ui.components.site_selector import rotulo_busca_site
from app.ui.components.site_selector import selecionar_site_pesquisavel
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None

COLUNAS_MONETARIAS_FINANCEIRO = {
    "Multa",
    "Juros",
    "Energia",
    "Outros",
    "Locação",
    "Subtotal",
    "Valor principal",
    "Ajustes",
    "Valor Total a Pagar",
    "Valor auxiliar",
    "Multa auxiliar",
    "Mora auxiliar",
    "Total a pagar auxiliar",
    "Total pago auxiliar",
    "Diferença a pagar auxiliar",
    "Valor Acordo",
    "Multa + Juros",
    "Valor",
    "Valor acumulado",
    "Saldo em aberto",
}


def configurar_financeiro(usuario_logado, mostrar_grid, formatar_moeda):
    global _mostrar_grid
    global _formatar_moeda
    global _usuario_logado
    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda
    _usuario_logado = usuario_logado


def usuario_atual():
    return _usuario_logado() if _usuario_logado else {}


def pode(chave):
    return has_permission(usuario_atual(), chave)


def moeda(valor):
    return _formatar_moeda(valor) if _formatar_moeda else valor


def formatar_tabela_financeira(df):
    resultado = df.copy()
    for coluna in COLUNAS_MONETARIAS_FINANCEIRO.intersection(resultado.columns):
        resultado[coluna] = resultado[coluna].apply(moeda)
    return resultado


def configurar_grafico_monetario(figura, coluna_valor):
    figura.update_yaxes(tickprefix="R$ ", separatethousands=True)
    for trace in figura.data:
        valores = getattr(trace, "y", None)
        if valores is None:
            continue
        trace.customdata = [moeda(valor) for valor in valores]
        trace.hovertemplate = (
            f"%{{x}}<br>{getattr(trace, 'name', '') or coluna_valor}: "
            "%{customdata}<extra></extra>"
        )
    figura.update_layout(yaxis_title="Valor (R$)")
    return figura


def opcoes_coluna(df, coluna):
    if df.empty or coluna not in df.columns:
        return []
    return sorted(
        valor
        for valor in df[coluna].dropna().astype(str).str.strip().unique()
        if valor
    )


def filtrar_dataframe(df, filtros):
    resultado = df.copy()
    for coluna, valores in filtros.items():
        if not valores or coluna not in resultado.columns:
            continue
        resultado = resultado[resultado[coluna].astype(str).isin(valores)]
    return resultado


def filtro_texto(df, termo, colunas):
    if not termo or df.empty:
        return df
    mask = pd.Series(False, index=df.index)
    for coluna in colunas:
        if coluna in df.columns:
            mask = mask | df[coluna].astype(str).str.contains(
                termo,
                case=False,
                regex=False,
                na=False,
            )
    return df[mask]


def mostrar_metricas_dashboard(dados):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total em atraso", moeda(dados["total_vencido"]))
    col2.metric("Valor total de acordos", moeda(dados["total_acordos_abertos"]))
    col3.metric("Sites com acordo", dados["sites_com_acordo"])
    col4.metric("Sites em atraso sem acordo", dados["sites_atrasados_sem_acordo"])

    col1, col2, col3 = st.columns(3)
    col1.metric("A vencer em 30 dias", moeda(dados["proximos_30"]))
    col2.metric("Obrigações sem vínculo", dados["sem_vinculo_quantidade"])
    col3.metric("Valor sem vínculo", moeda(dados["sem_vinculo_valor"]))


def mostrar_dashboard_financeiro():
    st.header("Financeiro")
    dados = dashboard_financeiro()
    mostrar_metricas_dashboard(dados)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Valores programados por mês")
        serie = dados["programacao_mensal"]
        if serie.empty:
            st.info("Não há valores programados a partir do mês atual.")
        else:
            figura = px.bar(
                serie,
                x="Mês",
                y=["Mensalidades", "Acordos"],
                barmode="stack",
                labels={"value": "Valor", "variable": "Tipo"},
                color_discrete_map={
                    "Mensalidades": "#2f80ed",
                    "Acordos": "#f2c94c",
                },
            )
            configurar_grafico_monetario(figura, "Valor")
            figura.add_scatter(
                x=serie["Mês"],
                y=serie["Total"],
                mode="text",
                text=[moeda(valor) for valor in serie["Total"]],
                textposition="top center",
                hoverinfo="skip",
                showlegend=False,
                cliponaxis=False,
            )
            figura.update_layout(legend_title_text="")
            st.plotly_chart(figura, use_container_width=True)
    with col2:
        st.subheader("Origem mensal dos débitos")
        serie = dados["origem_mensal"]
        if serie.empty:
            st.info("Não há vencimentos para exibir.")
        else:
            figura = px.bar(serie, x="Mês", y="Valor")
            st.plotly_chart(configurar_grafico_monetario(figura, "Valor"), use_container_width=True)

    st.subheader("Acumulado dos débitos vencidos")
    acumulado = dados["acumulado_atrasados"]
    if acumulado.empty:
        st.info("Não há débitos vencidos.")
    else:
        figura = px.line(acumulado, x="Mês", y="Valor acumulado", markers=True)
        st.plotly_chart(configurar_grafico_monetario(figura, "Valor acumulado"), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Aging dos atrasados")
        _mostrar_grid(formatar_tabela_financeira(dados["aging"]), height=280, key="financeiro_dashboard_aging")
    with col2:
        st.subheader("Sites com maior saldo em aberto")
        _mostrar_grid(formatar_tabela_financeira(dados["ranking_saldos"]), height=420, key="financeiro_dashboard_ranking")

    st.subheader("Obrigações vencidas")
    vencidos = dados["atrasados"].sort_values("Data de vencimento") if not dados["atrasados"].empty else dados["atrasados"]
    if vencidos.empty:
        st.info("Não há obrigações vencidas em aberto.")
    else:
        _mostrar_grid(formatar_tabela_financeira(vencidos.head(200)), height=420, key="financeiro_dashboard_vencidos")


def mostrar_editor_pagamentos(df):
    if not pode("financeiro_editar"):
        _mostrar_grid(formatar_tabela_financeira(df), height=650, key="financeiro_pagamentos_grid")
        return

    st.caption("Edite status, vencimento, valores operacionais, OC/RC e observação interna. Clique em Salvar alterações para gravar.")
    colunas_editaveis = [
        "ID SGS",
        "Status",
        "Ano",
        "Prioridade",
        "Tipo",
        "Tipo de despesa",
        "Data de vencimento",
        "Data programada pagamento",
        "Nome",
        "Fornecedor",
        "Microsiga",
        "Nome SNMPc",
        "RC NOVA",
        "OC NOVA",
        "OC Primário",
        "OC Secundário",
        "Energia",
        "Outros",
        "Locação",
        "Subtotal",
        "Descrição",
        "Observação interna",
    ]
    dados = df[[col for col in colunas_editaveis if col in df.columns]].copy()
    editado = st.data_editor(
        dados,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=PAYMENT_STATUSES),
            "Energia": st.column_config.NumberColumn("Energia", step=0.01, format="R$ %.2f"),
            "Outros": st.column_config.NumberColumn("Outros", step=0.01, format="R$ %.2f"),
            "Locação": st.column_config.NumberColumn("Locação", step=0.01, format="R$ %.2f"),
            "Subtotal": st.column_config.NumberColumn("Subtotal", step=0.01, format="R$ %.2f"),
        },
        disabled=["ID SGS", "Nome SNMPc"],
        key="financeiro_pagamentos_editor",
    )
    if st.button("Salvar alterações", type="primary", key="financeiro_pagamentos_salvar"):
        base = carregar_pagamentos()
        por_id = {row["ID SGS"]: idx for idx, row in base.iterrows()}
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alterados = 0
        for _idx, row in editado.iterrows():
            chave = row.get("ID SGS")
            if chave not in por_id:
                continue
            idx_base = por_id[chave]
            for coluna in editado.columns:
                if coluna == "ID SGS":
                    continue
                if coluna in base.columns and str(base.at[idx_base, coluna]) != str(row.get(coluna, "")):
                    base.at[idx_base, coluna] = row.get(coluna, "")
                    alterados += 1
            base.at[idx_base, "Atualizado em"] = agora
        salvar_pagamentos(base)
        registrar_log_sistema("financeiro_pagamentos_editados", usuario=usuario_atual().get("username"), status="sucesso", detalhes={"alteracoes": alterados})
        st.success("Alterações salvas.")
        st.rerun()


def mostrar_pagamentos():
    st.header("Pagamentos")
    df = preparar_pagamentos_exibicao()
    if df.empty:
        st.info("Nenhum pagamento importado.")
        return

    col1, col2, col3, col4 = st.columns(4)
    status = col1.multiselect("Status", opcoes_coluna(df, "Status Atual"), key="fin_pag_status")
    anos = col2.multiselect("Ano", opcoes_coluna(df, "Ano"), key="fin_pag_ano")
    prioridades = col3.multiselect("Prioridade", opcoes_coluna(df, "Prioridade"), key="fin_pag_prioridade")
    tipos = col4.multiselect("Tipo de despesa", opcoes_coluna(df, "Tipo de despesa"), key="fin_pag_tipo")
    busca = st.text_input("Buscar", placeholder="Favorecido, Microsiga, OC ou descrição", key="fin_pag_busca")

    filtrado = filtrar_dataframe(df, {"Status Atual": status, "Ano": anos, "Prioridade": prioridades, "Tipo de despesa": tipos})
    filtrado = filtro_texto(filtrado, busca, ["Favorecido", "Nome", "Fornecedor", "Microsiga", "OC / Conta Contábil", "OC Primário", "Descrição", "Nome SNMPc"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(filtrado))
    c2.metric("Subtotal", moeda(filtrado["Subtotal"].sum() if "Subtotal" in filtrado else 0))
    c3.metric("Sem vínculo", int((filtrado.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not filtrado.empty else 0)
    mostrar_editor_pagamentos(filtrado)


def mostrar_editor_acordos(df):
    if not pode("financeiro_editar"):
        _mostrar_grid(formatar_tabela_financeira(df), height=650, key="financeiro_acordos_grid")
        return

    colunas = ["ID SGS", "ID Pagamento", "Status", "Competência", "Data de vencimento", "Data programada pagamento", "Prioridade", "Favorecido", "Microsiga", "Nome SNMPc", "Valor Acordo", "Descrição", "Observação interna"]
    dados = df[[col for col in colunas if col in df.columns]].copy()
    if "Data de vencimento" in dados.columns:
        dados["Data de vencimento"] = pd.to_datetime(
            dados["Data de vencimento"],
            errors="coerce",
        ).dt.date
    editado = st.data_editor(
        dados,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=AGREEMENT_STATUSES),
            "Data de vencimento": st.column_config.DateColumn(
                "Data de vencimento",
                format="DD/MM/YYYY",
            ),
            "Valor Acordo": st.column_config.NumberColumn("Valor Acordo", step=0.01, format="R$ %.2f"),
        },
        disabled=["ID SGS", "ID Pagamento", "Nome SNMPc"],
        key="financeiro_acordos_editor",
    )
    if st.button("Salvar alterações", type="primary", key="financeiro_acordos_salvar"):
        base = carregar_acordos()
        por_id = {row["ID SGS"]: idx for idx, row in base.iterrows()}
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alterados = 0
        for _idx, row in editado.iterrows():
            chave = row.get("ID SGS")
            if chave not in por_id:
                continue
            idx_base = por_id[chave]
            for coluna in editado.columns:
                if coluna == "ID SGS":
                    continue
                valor = row.get(coluna, "")
                if coluna == "Data de vencimento":
                    valor = (
                        valor.isoformat()
                        if not pd.isna(valor) and hasattr(valor, "isoformat")
                        else ""
                    )
                if coluna in base.columns and str(base.at[idx_base, coluna]) != str(valor):
                    base.at[idx_base, coluna] = valor
                    alterados += 1
            base.at[idx_base, "Atualizado em"] = agora
        salvar_acordos(base)
        registrar_log_sistema("financeiro_acordos_editados", usuario=usuario_atual().get("username"), status="sucesso", detalhes={"alteracoes": alterados})
        st.success("Alterações salvas.")
        st.rerun()


def mostrar_acordos():
    st.header("Acordos")
    df = preparar_acordos_exibicao()
    if df.empty:
        st.info("Nenhum acordo importado.")
        return
    col1, col2, col3 = st.columns(3)
    status = col1.multiselect("Status", opcoes_coluna(df, "Status"), key="fin_aco_status")
    prioridades = col2.multiselect("Prioridade", opcoes_coluna(df, "Prioridade"), key="fin_aco_prioridade")
    negociacoes = col3.multiselect("Aprovação/Negociação", opcoes_coluna(df, "Aprovação/Negociação"), key="fin_aco_negociacao")
    busca = st.text_input("Buscar", placeholder="Favorecido, Microsiga ou descrição", key="fin_aco_busca")
    filtrado = filtrar_dataframe(df, {"Status": status, "Prioridade": prioridades, "Aprovação/Negociação": negociacoes})
    filtrado = filtro_texto(filtrado, busca, ["Favorecido", "Nome", "Microsiga", "Descrição", "Nome SNMPc"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(filtrado))
    c2.metric("Valor", moeda(filtrado["Valor Acordo"].sum() if "Valor Acordo" in filtrado else 0))
    c3.metric("Sem vínculo", int((filtrado.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not filtrado.empty else 0)
    mostrar_editor_acordos(filtrado)


def mostrar_conciliacao_financeira(sites):
    st.header("Conciliação financeira")
    st.caption(
        "Conferência informativa entre pagamentos, acordos e o cadastro atual de "
        "Sites. Esta tela não altera os dados financeiros."
    )
    with st.spinner("Analisando vínculos e dados financeiros..."):
        problemas = analisar_conciliacao_financeira(sites)
    if problemas.empty:
        st.success("Nenhuma inconsistência financeira foi encontrada.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Inconsistências", len(problemas))
    metrics[1].metric("Pagamentos", int(problemas["Origem"].eq("Pagamento").sum()))
    metrics[2].metric("Acordos", int(problemas["Origem"].eq("Acordo").sum()))
    metrics[3].metric(
        "Cadastro de Sites",
        int(problemas["Origem"].eq("Cadastro de Sites").sum()),
    )

    row1 = st.columns(3)
    tipos = row1[0].multiselect(
        "Tipo do problema",
        opcoes_coluna(problemas, "Tipo do problema"),
        key="financeiro_conciliacao_tipo",
    )
    origens = row1[1].multiselect(
        "Origem",
        opcoes_coluna(problemas, "Origem"),
        key="financeiro_conciliacao_origem",
    )
    status = row1[2].multiselect(
        "Status",
        opcoes_coluna(problemas, "Status"),
        key="financeiro_conciliacao_status",
    )
    row2 = st.columns(2)
    microsigas = row2[0].multiselect(
        "Código Microsiga",
        opcoes_coluna(problemas, "Microsiga extraído"),
        key="financeiro_conciliacao_microsiga",
    )
    sites_filtro = row2[1].multiselect(
        "Vínculo atual",
        opcoes_coluna(problemas, "Vínculo atual"),
        key="financeiro_conciliacao_site",
    )
    busca = st.text_input(
        "Buscar",
        placeholder="Favorecido, ID, descrição ou ação sugerida",
        key="financeiro_conciliacao_busca",
    )
    filtrado = filtrar_dataframe(problemas, {
        "Tipo do problema": tipos,
        "Origem": origens,
        "Status": status,
        "Microsiga extraído": microsigas,
        "Vínculo atual": sites_filtro,
    })
    filtrado = filtro_texto(
        filtrado,
        busca,
        ["Favorecido", "ID SGS", "Descrição", "Ação sugerida"],
    )

    st.metric("Inconsistências filtradas", len(filtrado))
    _mostrar_grid(
        formatar_tabela_financeira(filtrado),
        height=560,
        key="financeiro_conciliacao_grid",
    )
    st.download_button(
        "Baixar conciliação em Excel",
        data=exportar_conciliacao_financeira_excel(filtrado),
        file_name=f"sgs_conciliacao_financeira_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=filtrado.empty,
        key="financeiro_conciliacao_exportar",
    )


def _sites_para_historico(sites):
    return sorted(
        sites_financeiros_cadastrados(sites),
        key=lambda site: (
            str(site.get("nome_cadastro") or "").casefold(),
            str(site.get("nome") or "").casefold(),
        ),
    )


def mostrar_historico_financeiro_site(sites):
    st.header("Histórico financeiro por Site")
    opcoes_sites = _sites_para_historico(sites)
    if not opcoes_sites:
        st.info("Nenhum site cadastrado foi encontrado.")
        return
    site_por_nome = {
        str(site.get("nome") or ""): site for site in opcoes_sites
    }
    rotulos = {
        nome: rotulo_busca_site(site)
        for nome, site in site_por_nome.items()
    }
    nome_site = selecionar_site_pesquisavel(
        list(site_por_nome),
        rotulos,
        key="financeiro_historico_site_selecionado",
    )

    if nome_site is None:
        st.info("Pesquise e selecione um site para abrir o histórico financeiro.")
        return

    site = site_por_nome[nome_site]
    microsiga = site.get("microsiga", "")

    identificacao = st.columns(4)
    identificacao[0].metric("Nome", site.get("nome_cadastro") or "Não informado")
    identificacao[1].metric("Nome SNMPc", nome_site or "Não informado")
    identificacao[2].metric("Código Aquiles", site.get("codigo_topos") or "Não informado")
    identificacao[3].metric("Código Microsiga", microsiga or "Não informado")
    if not str(microsiga or "").strip():
        st.warning("O site não possui Código Microsiga e não pode ser relacionado à base financeira.")
        return

    historico = historico_financeiro_site(microsiga)
    row1 = st.columns(4)
    row1[0].metric("Valor em atraso", moeda(historico["valor_em_atraso"]))
    row1[1].metric("Parcelas vencidas", historico["parcelas_vencidas"])
    row1[2].metric("Valor futuro em aberto", moeda(historico["valor_futuro"]))
    row1[3].metric("Parcelas futuras", historico["parcelas_futuras"])
    row2 = st.columns(4)
    row2[0].metric("Acordos abertos", historico["quantidade_acordos_abertos"])
    row2[1].metric("Valor dos acordos", moeda(historico["valor_acordos_abertos"]))
    row2[2].metric("Pagamentos realizados", historico["quantidade_realizada"])
    row2[3].metric("Valor realizado", moeda(historico["valor_realizado"]))

    secoes = [
        (
            "Pagamentos realizados",
            historico["realizados"],
            ["Data de vencimento", "Competência", "Favorecido", "Tipo de despesa", "Subtotal", "Status Atual", "Descrição"],
            False,
        ),
        (
            "Pendências",
            historico["pendencias"],
            ["Data de vencimento", "Competência", "Favorecido", "Tipo de despesa", "Subtotal", "Status Atual", "Prioridade", "Descrição"],
            True,
        ),
        (
            "Acordos",
            historico["acordos"],
            ["Data de vencimento", "Competência", "Favorecido", "Valor Acordo", "Status", "Prioridade", "Descrição"],
            True,
        ),
    ]
    for indice, (titulo, dataframe, colunas, crescente) in enumerate(secoes):
        st.subheader(titulo)
        if dataframe.empty:
            st.info(f"Nenhum registro em {titulo.lower()} para este site.")
            continue
        dados = dataframe.copy()
        if "Data de vencimento" in dados.columns:
            dados["_ordem_data"] = pd.to_datetime(
                dados["Data de vencimento"], errors="coerce"
            )
            dados = dados.sort_values("_ordem_data", ascending=crescente).drop(
                columns=["_ordem_data"]
            )
        dados = dados[[coluna for coluna in colunas if coluna in dados.columns]]
        _mostrar_grid(
            formatar_tabela_financeira(dados),
            height=min(480, 90 + len(dados) * 31),
            key=f"financeiro_historico_site_{indice}",
        )


def mostrar_importacao(sites):
    st.header("Importação financeira")
    if not pode("financeiro_importar"):
        st.info("Seu perfil não possui permissão para importar dados financeiros.")
        return
    arquivo = st.file_uploader("Planilha financeira", type=["xls", "xlsx", "xlsm"], key="financeiro_importacao_arquivo")
    if not arquivo:
        st.caption(
            "Envie TOPO EM ABERTO ou Novo Fechamento. No formato TOPO EM ABERTO, todos os anos são importados porque o arquivo contém somente obrigações abertas."
        )
        return

    def processar(salvar=False, substituir=False):
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(arquivo.name).suffix) as temp:
            temp.write(arquivo.getbuffer())
            caminho = temp.name
        try:
            with st.spinner("Lendo planilha financeira..."):
                return importar_planilha_financeira(
                    caminho,
                    sites=sites,
                    salvar=salvar,
                    usuario=usuario_atual().get("username", ""),
                    substituir_base_antiga=substituir,
                )
        finally:
            Path(caminho).unlink(missing_ok=True)

    if st.button("Gerar prévia", type="primary", key="financeiro_importacao_processar"):
        try:
            st.session_state["financeiro_importacao_previa"] = processar()
        except Exception as erro:
            registrar_log_sistema("financeiro_importacao", usuario=usuario_atual().get("username"), status="erro", detalhes={"erro": str(erro)})
            st.error(f"Falha ao importar planilha: {erro}")

    resultado = st.session_state.get("financeiro_importacao_previa")
    if not resultado:
        return

    resumo = resultado["resumo"]
    st.success(f"Prévia processada. Formato detectado: {resultado['formato']}.")
    st.markdown("**Resumo da importação**")
    st.dataframe(
        pd.DataFrame([
            {
                "Tipo": "Pagamentos",
                "Importados": resumo["pagamentos"].get("importados", 0),
                "Vinculados a site": resumo["pagamentos"].get("com_site", 0),
                "Sem vínculo": resumo["pagamentos"].get("sem_site", 0),
                "Sem Microsiga": resumo["pagamentos"].get("sem_microsiga", 0),
                "Vencidos": resumo["pagamentos"].get("vencidos", 0),
                "Programados": resumo["pagamentos"].get("programados", 0),
                "Novos": resumo["pagamentos"].get("novos", 0),
                "Atualizados": resumo["pagamentos"].get("atualizados", 0),
                "Inalterados": resumo["pagamentos"].get("duplicados", 0),
            },
            {
                "Tipo": "Acordos",
                "Importados": resumo["acordos"].get("importados", 0),
                "Vinculados a site": resumo["acordos"].get("com_site", 0),
                "Sem vínculo": resumo["acordos"].get("sem_site", 0),
                "Sem Microsiga": resumo["acordos"].get("sem_microsiga", 0),
                "Vencidos": "",
                "Programados": "",
                "Novos": resumo["acordos"].get("novos", 0),
                "Atualizados": resumo["acordos"].get("atualizados", 0),
                "Inalterados": resumo["acordos"].get("duplicados", 0),
            },
        ]),
        use_container_width=True,
        hide_index=True,
    )

    sem_vinculo = resultado["pagamentos"][
        resultado["pagamentos"].get("Site localizado", pd.Series(dtype=str)).eq("Não")
    ]
    if not sem_vinculo.empty:
        st.warning("Existem obrigações cujo sufixo Microsiga do favorecido não foi localizado no cadastro de Sites.")
        _mostrar_grid(
            formatar_tabela_financeira(sem_vinculo[[coluna for coluna in ["Favorecido", "Microsiga", "Subtotal", "Vencimento original", "Tipo de despesa"] if coluna in sem_vinculo.columns]].head(100)),
            height=300,
            key="financeiro_importacao_sem_vinculo",
        )

    st.markdown("**Prévia de pagamentos**")
    _mostrar_grid(formatar_tabela_financeira(resultado["pagamentos"].head(100)), height=340, key="financeiro_importacao_prev_pag")
    st.markdown("**Prévia de acordos**")
    _mostrar_grid(formatar_tabela_financeira(resultado["acordos"].head(100)), height=340, key="financeiro_importacao_prev_aco")

    substituir = False
    if resultado["requer_substituicao_base_antiga"]:
        st.warning("Esta é a primeira importação de TOPO EM ABERTO. A base financeira anterior será substituída.")
        substituir = st.checkbox(
            "Confirmo a substituição da base financeira antiga",
            key="financeiro_importacao_substituir",
        )
    confirmar = st.checkbox("Confirmo a gravação desta importação", key="financeiro_importacao_confirmar")
    bloqueado = not confirmar or (resultado["requer_substituicao_base_antiga"] and not substituir)
    if st.button("Gravar importação", type="primary", disabled=bloqueado, key="financeiro_importacao_gravar"):
        try:
            processar(salvar=True, substituir=substituir)
            st.session_state.pop("financeiro_importacao_previa", None)
            st.success("Importação gravada com sucesso.")
            st.rerun()
        except Exception as erro:
            registrar_log_sistema(
                "financeiro_importacao",
                usuario=usuario_atual().get("username"),
                status="erro",
                detalhes={"erro": str(erro)},
            )
            st.error(f"Falha ao importar planilha: {erro}")


def mostrar_exportacoes():
    st.header("Exportações financeiras")
    if not pode("financeiro_exportacoes"):
        st.info("Seu perfil não possui permissão para exportar dados financeiros.")
        return
    pagamentos = preparar_pagamentos_exibicao()
    acordos = preparar_acordos_exibicao()
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Baixar pagamentos Excel",
            data=dataframe_para_excel(pagamentos, "Pagamentos"),
            file_name="sgs_pagamentos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=pagamentos.empty,
            key="financeiro_exportar_pagamentos",
        )
    with col2:
        st.download_button(
            "Baixar acordos Excel",
            data=dataframe_para_excel(acordos, "Acordos"),
            file_name="sgs_acordos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=acordos.empty,
            key="financeiro_exportar_acordos",
        )


def mostrar_alertas_financeiros():
    st.header("Alertas financeiros")
    st.caption(
        "Vencimentos de sites críticos e acordos dentro da janela configurada."
    )
    with st.spinner("Calculando vencimentos..."):
        dados = status_alertas_criticos()

    metricas = st.columns(4)
    metricas[0].metric("Sites críticos", len(dados["sites"]))
    metricas[1].metric("Acordos", len(dados["acordos"]))
    metricas[2].metric("Atrasados", dados["atrasados"])
    metricas[3].metric("Total de alertas", dados["total"])

    pode_ver_valores = pode("visualizar_valores_custos")

    st.subheader("Sites críticos")
    sites_alerta = dados["sites"].copy()
    if not pode_ver_valores and "Valor" in sites_alerta.columns:
        sites_alerta = sites_alerta.drop(columns=["Valor"])
    if sites_alerta.empty:
        st.info("Nenhum site crítico está dentro da janela de alerta.")
    else:
        _mostrar_grid(
            formatar_tabela_financeira(sites_alerta),
            height=min(560, max(140, 70 + len(sites_alerta) * 34)),
            key="financeiro_alertas_sites_grid",
        )

    st.subheader("Acordos")
    acordos_alerta = dados["acordos"].copy()
    if not pode_ver_valores and "Valor" in acordos_alerta.columns:
        acordos_alerta = acordos_alerta.drop(columns=["Valor"])
    if acordos_alerta.empty:
        st.info("Nenhum acordo está dentro da janela de alerta.")
    else:
        _mostrar_grid(
            formatar_tabela_financeira(acordos_alerta),
            height=min(560, max(140, 70 + len(acordos_alerta) * 34)),
            key="financeiro_alertas_acordos_grid",
        )

    diagnosticos = pd.concat(
        [dados["diagnosticos_sites"], dados["diagnosticos_acordos"]],
        ignore_index=True,
    )
    if not diagnosticos.empty:
        with st.expander("Pendências de cadastro", expanded=False):
            st.dataframe(diagnosticos, use_container_width=True, hide_index=True)


def mostrar_financeiro(sites):
    itens = []
    if pode("financeiro_dashboard") or pode("financeiro"):
        itens.append(("financeiro_dashboard", "Dashboard", mostrar_dashboard_financeiro))
    if pode("financeiro_alertas_criticos"):
        itens.append((
            "financeiro_alertas_criticos",
            "Alertas",
            mostrar_alertas_financeiros,
        ))
    if pode("financeiro_historico_site") or pode("financeiro"):
        itens.append((
            "financeiro_historico_site",
            "Histórico por Site",
            lambda: mostrar_historico_financeiro_site(sites),
        ))
    if pode("financeiro_pagamentos") or pode("financeiro"):
        itens.append(("financeiro_pagamentos", "Pagamentos", mostrar_pagamentos))
    if pode("financeiro_acordos") or pode("financeiro"):
        itens.append(("financeiro_acordos", "Acordos", mostrar_acordos))
    if pode("financeiro_conciliacao") or pode("financeiro"):
        itens.append((
            "financeiro_conciliacao",
            "Conciliação",
            lambda: mostrar_conciliacao_financeira(sites),
        ))
    if pode("financeiro_importar") or pode("financeiro"):
        itens.append(("financeiro_importar", "Importação", lambda: mostrar_importacao(sites)))
    if pode("financeiro_exportacoes") or pode("financeiro"):
        itens.append(("financeiro_exportacoes", "Exportações", mostrar_exportacoes))

    if not itens:
        st.warning("Seu usuário não possui permissões para o módulo Financeiro.")
        return

    funcao = mostrar_subnavegacao(itens, key="financeiro_subaba")
    if funcao:
        funcao()
