import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.services.clients import agrupar_clientes
from app.services.clients import equipamentos_cliente
from app.services.clients import filtrar_clientes
from app.services.clients import montar_base_clientes
from app.services.clients import resumo_clientes
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None


def configurar_clientes(mostrar_grid, formatar_moeda, usuario_logado):
    global _mostrar_grid
    global _formatar_moeda
    global _usuario_logado

    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda
    _usuario_logado = usuario_logado


def usuario_atual():
    return _usuario_logado() or {}


def pode_ver(chave):
    return has_permission(usuario_atual(), chave)


def rotulo_cliente(linha):
    return (
        f"{linha.get('Cliente') or ''} - "
        f"{linha.get('Assinatura') or ''} / "
        f"{linha.get('Produto') or ''} - "
        f"{linha.get('Site') or 'Sem vínculo'}"
    )


def mostrar_metricas_clientes(df):
    resumo = resumo_clientes(df)
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Clientes", resumo["clientes"])
    col2.metric("Receita", _formatar_moeda(resumo["receita"]))
    col3.metric("Produtos", resumo["produtos"])
    col4.metric("Sites", resumo["sites"])
    col5.metric("Sem vínculo", resumo["sem_vinculo"])


def base_filtrada_clientes(df_clientes, key_prefix):
    termo = st.text_input(
        "Buscar cliente",
        placeholder="Nome, assinatura, produto, site, endereço ou cidade",
        key=f"{key_prefix}_busca"
    )

    return filtrar_clientes(df_clientes, termo)


def selecionar_cliente(df_clientes, key_prefix):
    df_filtrado = base_filtrada_clientes(df_clientes, key_prefix)

    if df_filtrado.empty:
        st.info("Nenhum cliente encontrado para a busca informada.")
        return None, df_filtrado

    opcoes = [""] + df_filtrado["Assinatura"].astype(str).tolist()
    registros = {
        str(linha["Assinatura"]): linha.to_dict()
        for _indice, linha in df_filtrado.iterrows()
    }

    assinatura = st.selectbox(
        "Selecionar cliente",
        opcoes,
        index=0,
        key=f"{key_prefix}_selecionado",
        format_func=lambda valor: (
            "Selecione um cliente"
            if not valor
            else rotulo_cliente(registros.get(valor, {}))
        )
    )

    if not assinatura:
        return None, df_filtrado

    return registros.get(assinatura), df_filtrado


def mostrar_ficha_cliente(cliente, equipamentos):
    st.subheader(cliente.get("Cliente") or "Cliente")
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Assinatura", cliente.get("Assinatura") or "-")
    col2.metric("Produto", cliente.get("Produto") or "-")
    col3.metric("Receita", _formatar_moeda(cliente.get("Receita") or 0))
    col4.metric("Vínculo", cliente.get("Vínculo") or "-")

    st.markdown("**Dados do cliente**")
    _mostrar_grid(
        pd.DataFrame([
            {
                "Cliente": cliente.get("Cliente") or "",
                "Assinatura": cliente.get("Assinatura") or "",
                "Produto": cliente.get("Produto") or "",
                "Receita": cliente.get("Receita") or 0,
                "CEP": cliente.get("CEP") or "",
                "Endereço": cliente.get("Endereço") or "",
                "Bairro": cliente.get("Bairro") or "",
                "Cidade": cliente.get("Cidade") or ""
            }
        ]),
        height=120,
        key="clientes_ficha_dados_cliente"
    )

    st.markdown("**Vínculo e site**")
    _mostrar_grid(
        pd.DataFrame([
            {
                "Vínculo": cliente.get("Vínculo") or "",
                "Site": cliente.get("Site") or "",
                "Setorial": cliente.get("Setorial") or "",
                "Código Aquiles": cliente.get("Código Aquiles") or "",
                "Código Microsiga": cliente.get("Código Microsiga") or "",
                "Nome Site": cliente.get("Nome Site") or "",
                "Status Site": cliente.get("Status Site") or "",
                "Cidade Site": cliente.get("Cidade Site") or ""
            }
        ]),
        height=140,
        key="clientes_ficha_dados_site"
    )

    st.markdown("**Equipamentos associados**")
    df_equipamentos = equipamentos_cliente(cliente.get("Assinatura"), equipamentos)

    if df_equipamentos.empty:
        st.info("Nenhum equipamento associado a esta assinatura foi encontrado.")
    else:
        _mostrar_grid(
            df_equipamentos,
            height=260,
            key="clientes_ficha_equipamentos"
        )


def mostrar_consulta_clientes(sites, equipamentos):
    st.header("Clientes")
    df_clientes = montar_base_clientes(sites, equipamentos)

    if df_clientes.empty:
        st.warning("Nenhum cliente ativo foi encontrado na base atual.")
        return

    cliente, df_filtrado = selecionar_cliente(df_clientes, "clientes_consulta")
    mostrar_metricas_clientes(df_filtrado)

    st.markdown("**Clientes encontrados**")
    _mostrar_grid(
        df_filtrado,
        height=360,
        key="clientes_consulta_grid"
    )

    if cliente:
        mostrar_ficha_cliente(cliente, equipamentos)


def mostrar_relatorios_clientes(sites, equipamentos):
    st.header("Relatórios de clientes")
    df_clientes = montar_base_clientes(sites, equipamentos)
    df_filtrado = base_filtrada_clientes(df_clientes, "clientes_relatorios")

    if df_filtrado.empty:
        st.info("Nenhum cliente encontrado para os filtros informados.")
        return

    mostrar_metricas_clientes(df_filtrado)
    colunas = [
        coluna
        for coluna in [
            "Produto",
            "Tipo Produto",
            "Grupo Produto",
            "Família Produto",
            "Velocidade Produto",
            "Variação Produto",
            "Site",
            "Cidade",
            "Setorial",
            "Vínculo"
        ]
        if coluna in df_filtrado.columns
    ]
    agrupar_por = st.selectbox(
        "Agrupar por",
        colunas,
        key="clientes_relatorios_agrupar"
    )

    _mostrar_grid(
        agrupar_clientes(df_filtrado, agrupar_por),
        height=420,
        key="clientes_relatorios_grid"
    )


def mostrar_insights_clientes(sites, equipamentos):
    st.header("Insights de clientes")
    df_clientes = montar_base_clientes(sites, equipamentos)

    if df_clientes.empty:
        st.info("Nenhum cliente ativo foi encontrado.")
        return

    mostrar_metricas_clientes(df_clientes)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Maiores receitas**")
        _mostrar_grid(
            df_clientes.sort_values(by="Receita", ascending=False).head(20),
            height=360,
            key="clientes_insights_maiores_receitas"
        )

    with col2:
        st.markdown("**Clientes sem vínculo**")
        _mostrar_grid(
            df_clientes[df_clientes["Vínculo"] == "Sem vínculo"].sort_values(
                by="Cliente"
            ),
            height=360,
            key="clientes_insights_sem_vinculo"
        )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Produtos mais recorrentes**")
        _mostrar_grid(
            agrupar_clientes(df_clientes, "Produto")
            .sort_values(by="Clientes", ascending=False)
            .head(20),
            height=360,
            key="clientes_insights_produtos"
        )

    with col2:
        st.markdown("**Clientes sem equipamento associado**")
        _mostrar_grid(
            df_clientes[
                df_clientes["Qtd Equipamentos"].fillna(0).astype(float) == 0
            ].sort_values(by="Cliente"),
            height=360,
            key="clientes_insights_sem_equipamento"
        )


def mostrar_clientes(sites, equipamentos):
    subabas = [
        (
            "clientes_consulta",
            "Consulta",
            lambda: mostrar_consulta_clientes(sites, equipamentos)
        ),
        (
            "clientes_relatorios",
            "Relatórios",
            lambda: mostrar_relatorios_clientes(sites, equipamentos)
        ),
        (
            "clientes_insights",
            "Insights",
            lambda: mostrar_insights_clientes(sites, equipamentos)
        )
    ]
    subabas = [
        item
        for item in subabas
        if pode_ver(item[0]) or pode_ver("clientes")
    ]

    if not subabas:
        st.warning("Seu usuário não possui permissões para o módulo Clientes.")
        return

    funcao = mostrar_subnavegacao(subabas, key="clientes_subaba")

    if funcao:
        funcao()
