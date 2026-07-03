import pandas as pd
import streamlit as st

from app.auth import can_view_cost_values
from app.auth import can_view_values
from app.auth import has_permission
from app.services.insights import alertas_gerenciais
from app.services.insights import agrupar_clientes
from app.services.insights import agrupar_sites
from app.services.insights import clientes_sem_equipamento
from app.services.insights import clientes_sem_vinculo
from app.services.insights import equipamentos_sem_catalogo
from app.services.insights import mapa_distancias_dataframe
from app.services.insights import mapa_nao_plotados_dataframe
from app.services.insights import preparar_bases_insights
from app.services.insights import produtos_sem_catalogo
from app.services.insights import ranking_clientes
from app.services.insights import ranking_sites
from app.services.insights import resumo_geral_filtrado
from app.services.insights import sites_cadastro_incompleto
from app.services.insights import sites_deficitarios
from app.services.insights import sites_relacionamento_critico
from app.services.insights import sites_sem_clientes
from app.services.insights import sites_sem_contato
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None


def configurar_insights(mostrar_grid, formatar_moeda, usuario_logado):
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


def pode_acessar_insights():
    usuario = usuario_atual()

    return (
        has_permission(usuario, "insights")
        and can_view_values(usuario)
        and can_view_cost_values(usuario)
    )


def opcoes_coluna(df, coluna):
    if df.empty or coluna not in df.columns:
        return []

    return sorted(
        valor
        for valor in df[coluna].dropna().astype(str).str.strip().unique()
        if valor
    )


def filtrar_por_multiselect(df, coluna, valores):
    if df.empty or not valores or coluna not in df.columns:
        return df

    return df[df[coluna].astype(str).isin(valores)].copy()


def aplicar_filtros_clientes_por_sites(df_clientes, df_sites, incluir_sem_vinculo=True):
    if df_clientes.empty or df_sites.empty or "Site" not in df_clientes.columns:
        return df_clientes

    sites_validos = set(df_sites["Site SNMPc"].dropna().astype(str))
    filtro = df_clientes["Site"].astype(str).isin(sites_validos)
    if incluir_sem_vinculo:
        filtro = filtro | df_clientes["Vínculo"].astype(str).eq("Sem vínculo")

    return df_clientes[filtro].copy()


def bases_filtradas(sites, equipamentos):
    apenas_ativos = st.checkbox(
        "Considerar apenas sites ativos",
        value=True,
        key="insights_apenas_ativos"
    )
    df_sites, df_clientes = preparar_bases_insights(
        sites,
        equipamentos,
        apenas_ativos=apenas_ativos
    )

    with st.expander("Filtros gerenciais", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            cidades = st.multiselect(
                "Cidade",
                opcoes_coluna(df_sites, "Cidade"),
                key="insights_filtro_cidade"
            )
            contratos = st.multiselect(
                "Contrato",
                opcoes_coluna(df_sites, "Contrato"),
                key="insights_filtro_contrato"
            )

        with col2:
            categorias = st.multiselect(
                "Categoria",
                opcoes_coluna(df_sites, "Categoria"),
                key="insights_filtro_categoria"
            )
            perfis = st.multiselect(
                "Perfil",
                opcoes_coluna(df_sites, "Perfil"),
                key="insights_filtro_perfil"
            )

        with col3:
            produtos = st.multiselect(
                "Produto",
                opcoes_coluna(df_clientes, "Produto"),
                key="insights_filtro_produto"
            )
            vinculos = st.multiselect(
                "Vínculo",
                opcoes_coluna(df_clientes, "Vínculo"),
                key="insights_filtro_vinculo"
            )

    filtros_site_ativos = any([
        cidades,
        contratos,
        categorias,
        perfis
    ])

    for coluna, valores in [
        ("Cidade", cidades),
        ("Contrato", contratos),
        ("Categoria", categorias),
        ("Perfil", perfis)
    ]:
        df_sites = filtrar_por_multiselect(
            df_sites,
            coluna,
            valores
        )

    df_clientes = aplicar_filtros_clientes_por_sites(
        df_clientes,
        df_sites,
        incluir_sem_vinculo=not filtros_site_ativos
    )
    df_clientes = filtrar_por_multiselect(
        df_clientes,
        "Produto",
        produtos
    )
    df_clientes = filtrar_por_multiselect(
        df_clientes,
        "Vínculo",
        vinculos
    )

    return df_sites, df_clientes, apenas_ativos


def mostrar_metricas_resumo(resumo):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receita", _formatar_moeda(resumo["Receita"]))
    col2.metric("Custo", _formatar_moeda(resumo["Custo"]))
    col3.metric("Resultado", _formatar_moeda(resumo["Resultado"]))
    col4.metric("Margem", f"{resumo['Margem %']:.1%}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sites", resumo["Sites"])
    col2.metric("Clientes", resumo["Clientes"])
    col3.metric("Produtos", resumo["Produtos"])
    col4.metric("Equipamentos", resumo["Equipamentos"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sites deficitários", resumo["Sites Deficitários"])
    col2.metric("Sites sem clientes", resumo["Sites Sem Clientes"])
    col3.metric("Clientes sem vínculo", resumo["Clientes Sem Vínculo"])
    col4.metric("Itens não plotados", resumo["Itens Não Plotados"])


def mostrar_tabela(df, height, key, vazio="Nenhum dado encontrado para este indicador."):
    if df is None or df.empty:
        st.info(vazio)
        return

    _mostrar_grid(
        df,
        height=height,
        key=key
    )


def mostrar_visao_geral(sites, equipamentos, df_sites, df_clientes, apenas_ativos):
    st.header("Insights")
    resumo = resumo_geral_filtrado(
        df_sites,
        df_clientes,
        equipamentos
    )

    mostrar_metricas_resumo(resumo)

    st.markdown("**Alertas gerenciais**")
    mostrar_tabela(
        alertas_gerenciais(
            df_sites,
            df_clientes,
            equipamentos
        ),
        height=360,
        key="insights_alertas_gerenciais"
    )


def mostrar_financeiro(_sites, _equipamentos, df_sites, _df_clientes, _apenas_ativos):
    st.header("Insights financeiros")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sites deficitários**")
        mostrar_tabela(
            sites_deficitarios(df_sites),
            height=360,
            key="insights_financeiro_deficitarios"
        )

    with col2:
        st.markdown("**Sites com custo sem clientes**")
        mostrar_tabela(
            sites_sem_clientes(df_sites),
            height=360,
            key="insights_financeiro_sem_clientes"
        )

    st.markdown("**Ranking financeiro por site**")
    mostrar_tabela(
        ranking_sites(
            df_sites,
            "Resultado",
            ascendente=True,
            limite=50
        ),
        height=420,
        key="insights_financeiro_ranking_sites"
    )

    st.markdown("**Concentração por cidade**")
    mostrar_tabela(
        agrupar_sites(
            df_sites,
            "Cidade"
        ),
        height=360,
        key="insights_financeiro_cidade"
    )


def mostrar_clientes(_sites, _equipamentos, _df_sites, df_clientes, _apenas_ativos):
    st.header("Insights de clientes")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Maiores clientes por receita**")
        mostrar_tabela(
            ranking_clientes(
                df_clientes,
                "Receita",
                ascendente=False,
                limite=50
            ),
            height=380,
            key="insights_clientes_receita"
        )

    with col2:
        st.markdown("**Clientes sem vínculo**")
        mostrar_tabela(
            clientes_sem_vinculo(df_clientes),
            height=380,
            key="insights_clientes_sem_vinculo"
        )

    st.markdown("**Receita por produto**")
    mostrar_tabela(
        agrupar_clientes(
            df_clientes,
            "Produto"
        ),
        height=420,
        key="insights_clientes_produtos"
    )

    if "Família Produto" in df_clientes.columns:
        st.markdown("**Receita por família de produto**")
        mostrar_tabela(
            agrupar_clientes(
                df_clientes,
                "Família Produto"
            ),
            height=360,
            key="insights_clientes_familia_produto"
        )


def mostrar_sites(_sites, _equipamentos, df_sites, _df_clientes, _apenas_ativos):
    st.header("Insights de sites")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sites sem clientes**")
        mostrar_tabela(
            sites_sem_clientes(df_sites),
            height=360,
            key="insights_sites_sem_clientes"
        )

    with col2:
        st.markdown("**Sites com cadastro incompleto**")
        mostrar_tabela(
            sites_cadastro_incompleto(df_sites),
            height=360,
            key="insights_sites_cadastro_incompleto"
        )

    for coluna, titulo, chave in [
        ("Status Cadastro", "Sites por status", "status"),
        ("Categoria", "Sites por categoria", "categoria"),
        ("Perfil", "Sites por perfil", "perfil"),
        ("Contrato", "Sites por contrato", "contrato"),
        ("Relacionamento", "Sites por relacionamento", "relacionamento")
    ]:
        if coluna in df_sites.columns:
            st.markdown(f"**{titulo}**")
            mostrar_tabela(
                agrupar_sites(
                    df_sites,
                    coluna
                ),
                height=300,
                key=f"insights_sites_{chave}"
            )


def mostrar_operacional(_sites, equipamentos, _df_sites, df_clientes, _apenas_ativos):
    st.header("Insights operacionais")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Equipamentos sem cadastro**")
        mostrar_tabela(
            equipamentos_sem_catalogo(equipamentos),
            height=360,
            key="insights_operacional_equipamentos_sem_catalogo"
        )

    with col2:
        st.markdown("**Produtos sem cadastro**")
        mostrar_tabela(
            produtos_sem_catalogo(df_clientes),
            height=360,
            key="insights_operacional_produtos_sem_catalogo"
        )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Clientes sem equipamento associado**")
        mostrar_tabela(
            clientes_sem_equipamento(df_clientes),
            height=360,
            key="insights_operacional_clientes_sem_equipamento"
        )

    with col2:
        st.markdown("**Itens não plotados no mapa**")
        mostrar_tabela(
            mapa_nao_plotados_dataframe(),
            height=360,
            key="insights_operacional_nao_plotados"
        )

    st.markdown("**Distâncias armazenadas no mapa**")
    mostrar_tabela(
        mapa_distancias_dataframe(),
        height=360,
        key="insights_operacional_distancias"
    )


def mostrar_riscos(_sites, _equipamentos, df_sites, _df_clientes, _apenas_ativos):
    st.header("Insights de riscos")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sites com relacionamento crítico**")
        mostrar_tabela(
            sites_relacionamento_critico(df_sites),
            height=380,
            key="insights_riscos_relacionamento"
        )

    with col2:
        st.markdown("**Sites sem contato cadastrado**")
        mostrar_tabela(
            sites_sem_contato(df_sites),
            height=380,
            key="insights_riscos_sem_contato"
        )

    st.markdown("**Sites com cadastro incompleto**")
    mostrar_tabela(
        sites_cadastro_incompleto(df_sites),
        height=420,
        key="insights_riscos_cadastro_incompleto"
    )


def mostrar_insights(sites, equipamentos):
    if not pode_acessar_insights():
        st.warning(
            "Acesso restrito. O módulo Insights exige permissão para Insights, valores de clientes e valores de custos."
        )
        return

    df_sites, df_clientes, apenas_ativos = bases_filtradas(
        sites,
        equipamentos
    )

    subabas = [
        ("insights_visao_geral", "Visão Geral", mostrar_visao_geral),
        ("insights_financeiro", "Financeiro", mostrar_financeiro),
        ("insights_clientes", "Clientes", mostrar_clientes),
        ("insights_sites", "Sites", mostrar_sites),
        ("insights_operacional", "Operacional", mostrar_operacional),
        ("insights_riscos", "Riscos", mostrar_riscos)
    ]
    subabas = [
        (
            chave,
            rotulo,
            lambda funcao=funcao: funcao(
                sites,
                equipamentos,
                df_sites,
                df_clientes,
                apenas_ativos
            )
        )
        for chave, rotulo, funcao in subabas
        if pode_ver(chave) or pode_ver("insights")
    ]

    if not subabas:
        st.warning("Seu usuário não possui permissões para as subabas de Insights.")
        return

    funcao = mostrar_subnavegacao(
        subabas,
        key="insights_subaba"
    )

    if funcao:
        funcao()
