import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.logs import registrar_log_sistema
from app.services.finance_service import AGREEMENT_COLUMNS
from app.services.finance_service import AGREEMENT_STATUSES
from app.services.finance_service import PAYMENT_COLUMNS
from app.services.finance_service import PAYMENT_STATUSES
from app.services.finance_service import carregar_acordos
from app.services.finance_service import carregar_pagamentos
from app.services.finance_service import dashboard_financeiro
from app.services.finance_service import dataframe_para_excel
from app.services.finance_service import importar_planilha_financeira
from app.services.finance_service import preparar_pagamentos_exibicao
from app.services.finance_service import salvar_acordos
from app.services.finance_service import salvar_pagamentos
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None


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
    col1.metric("Pendente", moeda(dados["total_pendente"]))
    col2.metric("Vencido", moeda(dados["total_vencido"]))
    col3.metric("Próximos 30 dias", moeda(dados["proximos_30"]))
    col4.metric("Acordos abertos", dados["acordos_abertos"])

    col1, col2, col3 = st.columns(3)
    pagamentos = dados["pagamentos"]
    acordos = dados["acordos"]
    col1.metric("Pagamentos", len(pagamentos))
    col2.metric("Acordos", len(acordos))
    col3.metric("Sem vínculo", int((pagamentos.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not pagamentos.empty else 0)


def mostrar_dashboard_financeiro():
    st.header("Financeiro")
    dados = dashboard_financeiro()
    mostrar_metricas_dashboard(dados)

    pagamentos = dados["pagamentos"]
    acordos = dados["acordos"]

    if not pagamentos.empty:
        st.subheader("Pagamentos vencidos")
        vencidos = pagamentos[pagamentos["Status Atual"].eq("Vencido")].sort_values("Data de vencimento")
        _mostrar_grid(
            vencidos.head(100),
            height=360,
            key="financeiro_dashboard_vencidos",
        )

        st.subheader("Próximos vencimentos")
        proximos = pagamentos[~pagamentos["Status Atual"].isin(["Pago", "Cancelado"])].sort_values("Data de vencimento")
        _mostrar_grid(
            proximos.head(100),
            height=360,
            key="financeiro_dashboard_proximos",
        )

    if not acordos.empty:
        st.subheader("Acordos em aberto")
        abertos = acordos[~acordos["Status"].isin(["Quitado", "Cancelado"])]
        _mostrar_grid(
            abertos.head(100),
            height=360,
            key="financeiro_dashboard_acordos",
        )


def mostrar_editor_pagamentos(df):
    if not pode("financeiro_editar"):
        _mostrar_grid(df, height=650, key="financeiro_pagamentos_grid")
        return

    st.caption("Edite status, vencimento, valores operacionais, OC/RC e observação interna. Clique em Salvar alterações para gravar.")
    colunas_editaveis = [
        "ID SGS",
        "Status",
        "Ano",
        "Prioridade",
        "Tipo",
        "Data de vencimento",
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
            "Energia": st.column_config.NumberColumn("Energia", step=0.01),
            "Outros": st.column_config.NumberColumn("Outros", step=0.01),
            "Locação": st.column_config.NumberColumn("Locação", step=0.01),
            "Subtotal": st.column_config.NumberColumn("Subtotal", step=0.01),
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
    tipos = col4.multiselect("Tipo", opcoes_coluna(df, "Tipo"), key="fin_pag_tipo")
    busca = st.text_input("Buscar", placeholder="Nome, fornecedor, Microsiga, OC, descrição", key="fin_pag_busca")

    filtrado = filtrar_dataframe(df, {"Status Atual": status, "Ano": anos, "Prioridade": prioridades, "Tipo": tipos})
    filtrado = filtro_texto(filtrado, busca, ["Nome", "Fornecedor", "Microsiga", "OC Primário", "OC Secundário", "OC NOVA", "Descrição", "Nome SNMPc"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(filtrado))
    c2.metric("Subtotal", moeda(filtrado["Subtotal"].sum() if "Subtotal" in filtrado else 0))
    c3.metric("Sem vínculo", int((filtrado.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not filtrado.empty else 0)
    mostrar_editor_pagamentos(filtrado)


def mostrar_editor_acordos(df):
    if not pode("financeiro_editar"):
        _mostrar_grid(df, height=650, key="financeiro_acordos_grid")
        return

    colunas = ["ID SGS", "Status", "Competência", "Nome", "Resp", "Aprovado Sindico", "PAGO", "Microsiga", "Nome SNMPc", "Valor Acordo", "Descrição", "Observação interna"]
    dados = df[[col for col in colunas if col in df.columns]].copy()
    editado = st.data_editor(
        dados,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=AGREEMENT_STATUSES),
            "Valor Acordo": st.column_config.NumberColumn("Valor Acordo", step=0.01),
        },
        disabled=["ID SGS", "Nome SNMPc"],
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
                if coluna in base.columns and str(base.at[idx_base, coluna]) != str(row.get(coluna, "")):
                    base.at[idx_base, coluna] = row.get(coluna, "")
                    alterados += 1
            base.at[idx_base, "Atualizado em"] = agora
        salvar_acordos(base)
        registrar_log_sistema("financeiro_acordos_editados", usuario=usuario_atual().get("username"), status="sucesso", detalhes={"alteracoes": alterados})
        st.success("Alterações salvas.")
        st.rerun()


def mostrar_acordos():
    st.header("Acordos")
    df = carregar_acordos()
    if df.empty:
        st.info("Nenhum acordo importado.")
        return
    col1, col2, col3 = st.columns(3)
    status = col1.multiselect("Status", opcoes_coluna(df, "Status"), key="fin_aco_status")
    responsaveis = col2.multiselect("Responsável", opcoes_coluna(df, "Resp"), key="fin_aco_resp")
    pago = col3.multiselect("PAGO", opcoes_coluna(df, "PAGO"), key="fin_aco_pago")
    busca = st.text_input("Buscar", placeholder="Nome, Microsiga, descrição", key="fin_aco_busca")
    filtrado = filtrar_dataframe(df, {"Status": status, "Resp": responsaveis, "PAGO": pago})
    filtrado = filtro_texto(filtrado, busca, ["Nome", "Microsiga", "Descrição", "Nome SNMPc"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(filtrado))
    c2.metric("Valor", moeda(filtrado["Valor Acordo"].sum() if "Valor Acordo" in filtrado else 0))
    c3.metric("Sem vínculo", int((filtrado.get("Site localizado", pd.Series(dtype=str)) == "Não").sum()) if not filtrado.empty else 0)
    mostrar_editor_acordos(filtrado)


def mostrar_importacao(sites):
    st.header("Importação financeira")
    if not pode("financeiro_importar"):
        st.info("Seu perfil não possui permissão para importar dados financeiros.")
        return
    arquivo = st.file_uploader("Planilha Novo Fechamento", type=["xlsm", "xlsx"], key="financeiro_importacao_arquivo")
    if not arquivo:
        st.caption(
            "Envie a planilha completa. Macros serão ignoradas; apenas os dados das abas serão lidos. "
            "Para manter o SGS leve, serão importados somente o ano corrente e anos futuros."
        )
        return
    salvar = st.checkbox("Gravar importação após prévia", value=False, key="financeiro_importacao_gravar")
    if st.button("Processar planilha", type="primary", key="financeiro_importacao_processar"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(arquivo.name).suffix) as temp:
            temp.write(arquivo.getbuffer())
            caminho = temp.name
        try:
            with st.spinner("Lendo planilha financeira..."):
                resultado = importar_planilha_financeira(caminho, sites=sites, salvar=salvar, usuario=usuario_atual().get("username", ""))
            resumo = resultado["resumo"]
            st.success("Planilha processada." if not salvar else "Importação gravada com sucesso.")
            st.markdown("**Resumo da importação**")
            st.dataframe(
                pd.DataFrame([
                    {
                        "Tipo": "Pagamentos",
                        "Importados": resumo["pagamentos"].get("importados", 0),
                        "Vinculados a site": resumo["pagamentos"].get("com_site", 0),
                        "Sem vínculo": resumo["pagamentos"].get("sem_site", 0),
                        "Sem Microsiga": resumo["pagamentos"].get("sem_microsiga", 0),
                        "Novos": resumo["pagamentos"].get("novos", 0),
                        "Atualizados": resumo["pagamentos"].get("atualizados", 0),
                        "Duplicados": resumo["pagamentos"].get("duplicados", 0),
                    },
                    {
                        "Tipo": "Acordos",
                        "Importados": resumo["acordos"].get("importados", 0),
                        "Vinculados a site": resumo["acordos"].get("com_site", 0),
                        "Sem vínculo": resumo["acordos"].get("sem_site", 0),
                        "Sem Microsiga": resumo["acordos"].get("sem_microsiga", 0),
                        "Novos": resumo["acordos"].get("novos", 0),
                        "Atualizados": resumo["acordos"].get("atualizados", 0),
                        "Duplicados": resumo["acordos"].get("duplicados", 0),
                    },
                ]),
                use_container_width=True,
                hide_index=True
            )

            sem_vinculo = resultado["pagamentos"][
                resultado["pagamentos"].get("Site localizado", pd.Series(dtype=str)).eq("Não")
            ]
            if not sem_vinculo.empty:
                st.warning(
                    "Alguns pagamentos não foram vinculados. "
                    "Normalmente isso ocorre quando o Microsiga está vazio na planilha ou não existe no cadastro de sites."
                )
                _mostrar_grid(
                    sem_vinculo[
                        [
                            coluna
                            for coluna in [
                                "Microsiga",
                                "Nome",
                                "Fornecedor",
                                "Subtotal",
                                "Descrição"
                            ]
                            if coluna in sem_vinculo.columns
                        ]
                    ].head(100),
                    height=300,
                    key="financeiro_importacao_sem_vinculo"
                )

            st.markdown("**Prévia de pagamentos**")
            _mostrar_grid(resultado["pagamentos"].head(100), height=340, key="financeiro_importacao_prev_pag")
            st.markdown("**Prévia de acordos**")
            _mostrar_grid(resultado["acordos"].head(100), height=340, key="financeiro_importacao_prev_aco")
        except Exception as erro:
            registrar_log_sistema("financeiro_importacao", usuario=usuario_atual().get("username"), status="erro", detalhes={"erro": str(erro)})
            st.error(f"Falha ao importar planilha: {erro}")


def mostrar_exportacoes():
    st.header("Exportações financeiras")
    if not pode("financeiro_exportacoes"):
        st.info("Seu perfil não possui permissão para exportar dados financeiros.")
        return
    pagamentos = preparar_pagamentos_exibicao()
    acordos = carregar_acordos()
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


def mostrar_financeiro(sites):
    itens = []
    if pode("financeiro_dashboard") or pode("financeiro"):
        itens.append(("financeiro_dashboard", "Dashboard", mostrar_dashboard_financeiro))
    if pode("financeiro_pagamentos") or pode("financeiro"):
        itens.append(("financeiro_pagamentos", "Pagamentos", mostrar_pagamentos))
    if pode("financeiro_acordos") or pode("financeiro"):
        itens.append(("financeiro_acordos", "Acordos", mostrar_acordos))
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
