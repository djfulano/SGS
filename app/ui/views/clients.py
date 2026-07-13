import html
from urllib.parse import quote

import pandas as pd
import streamlit as st

from app.auth import can_view_values
from app.auth import has_permission
from app.services.clients import agrupar_clientes
from app.services.clients import filtrar_clientes
from app.services.clients import montar_base_consulta_clientes
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


def preparar_busca_clientes(df_clientes):
    df_clientes = df_clientes.copy()
    df_clientes["Assinatura"] = df_clientes["Assinatura"].astype(str)
    df_clientes["Rotulo Busca"] = df_clientes.apply(
        lambda linha: rotulo_cliente(linha.to_dict()),
        axis=1
    )

    opcoes = [""] + df_clientes["Assinatura"].tolist()
    rotulos_por_assinatura = {
        str(linha["Assinatura"]): linha["Rotulo Busca"]
        for _indice, linha in df_clientes.iterrows()
    }
    registros_por_assinatura = {
        str(linha["Assinatura"]): linha.drop(labels=["Rotulo Busca"]).to_dict()
        for _indice, linha in df_clientes.iterrows()
    }

    return opcoes, rotulos_por_assinatura, registros_por_assinatura


def selecionar_cliente(df_clientes, key_prefix):
    opcoes, rotulos_por_assinatura, registros_por_assinatura = (
        preparar_busca_clientes(df_clientes)
    )
    chave_selecao = f"{key_prefix}_selecionado"
    assinatura_abrir = str(
        st.session_state.pop("abrir_cliente_consulta", "") or ""
    ).strip()

    if assinatura_abrir:

        if assinatura_abrir in registros_por_assinatura:
            st.session_state[chave_selecao] = assinatura_abrir

        else:
            st.warning("Cliente não encontrado na base atual.")

    assinatura = st.selectbox(
        "Buscar cliente",
        opcoes,
        index=None,
        placeholder="Digite nome, assinatura, produto, gerente ou site",
        key=chave_selecao,
        format_func=lambda valor: (
            rotulos_por_assinatura.get(str(valor), "")
            if valor
            else ""
        )
    )

    if not assinatura:
        return None

    return registros_por_assinatura.get(str(assinatura))


def valor_resumo_cliente(cliente, campo, padrao="Não informado"):
    valor = cliente.get(campo)

    if pd.isna(valor):
        return padrao

    texto = str(valor or "").strip()

    return texto or padrao


def mostrar_campo_resumo(rotulo, valor):
    st.caption(rotulo)
    st.markdown(f"**{valor}**")


def mostrar_campo_resumo_multilinha(rotulo, valor):
    st.caption(rotulo)
    texto = html.escape(str(valor)).replace("\n", "<br>")
    st.markdown(
        f"<strong>{texto}</strong>",
        unsafe_allow_html=True
    )


def site_valido_cliente(cliente):
    site = valor_resumo_cliente(cliente, "Site", "")

    if not site or site == "Sem vínculo":
        return ""

    return site


def mostrar_campo_resumo_link(rotulo, valor, parametro, site):
    st.caption(rotulo)

    if not site:
        st.markdown(f"**{valor}**")
        return

    href = f"?{parametro}={quote(site)}"
    texto = html.escape(str(valor))
    st.markdown(
        f'<a href="{href}" target="_self">{texto}</a>',
        unsafe_allow_html=True
    )


def assinatura_cliente(cliente):
    assinatura = valor_resumo_cliente(cliente, "Assinatura", "")

    if assinatura == "Não informado":
        return ""

    return assinatura


def links_uteis_cliente(assinatura):
    assinatura_codificada = quote(assinatura)

    return [
        (
            "Aquiles",
            (
                "https://aquiles.directnet.net.br/AQLWEB/Paginas/"
                "Assinaturas/Assinaturas/PagAssinaturasFrm.aspx"
                f"?Operacao=V&ID={assinatura_codificada}"
                f"&CodAssin={assinatura_codificada}"
                "&CodClie=&CurrentPage=1&OrderBy="
            )
        ),
        (
            "Zabbix",
            (
                "http://neozabbix.neovia.com.br:8080/zabbix/zabbix.php"
                f"?action=search&search={assinatura_codificada}"
            )
        )
    ]


def mostrar_links_uteis_cliente(cliente):
    assinatura = assinatura_cliente(cliente)

    if not assinatura:
        st.caption("Links úteis indisponíveis para este cliente.")
        return

    st.markdown("**Links úteis**")

    links = []

    for rotulo, href in links_uteis_cliente(assinatura):
        links.append(
            f'<a href="{html.escape(href)}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(rotulo)}</a>"
        )

    st.markdown(
        " &nbsp; ".join(links),
        unsafe_allow_html=True
    )


def mostrar_vinculos_atendimento_cliente(cliente):
    vinculos = cliente.get("Vínculos de atendimento") or []

    if not isinstance(vinculos, list) or not vinculos:
        return

    st.markdown("**Sites de atendimento**")

    for vinculo in vinculos:
        site = str(vinculo.get("Site") or "").strip()
        setorial = str(vinculo.get("Setorial") or "Direto").strip()
        tipo = str(vinculo.get("Vínculo") or "Principal").strip()

        if not site:
            continue

        site_href = f"?abrir_site_gerenciamento={quote(site)}"
        topologia_href = f"?abrir_topologia_site={quote(site)}"
        st.markdown(
            (
                f"- **{html.escape(tipo)}:** "
                f'<a href="{site_href}" target="_self">'
                f"{html.escape(site)}</a> / "
                f'<a href="{topologia_href}" target="_self">'
                f"{html.escape(setorial)}</a>"
            ),
            unsafe_allow_html=True
        )


def mostrar_resumo_cliente(cliente):
    st.subheader(valor_resumo_cliente(cliente, "Cliente", "Cliente"))

    receita = (
        _formatar_moeda(cliente.get("Receita") or 0)
        if can_view_values(usuario_atual())
        else "Restrito"
    )

    site_cliente = site_valido_cliente(cliente)
    setorial = valor_resumo_cliente(cliente, "Setorial")
    campos = [
        ("Assinatura", valor_resumo_cliente(cliente, "Assinatura", "-")),
        ("Nome", valor_resumo_cliente(cliente, "Cliente")),
        ("Receita", receita),
        ("Produto", valor_resumo_cliente(cliente, "Produto")),
        ("Gerente de contas", valor_resumo_cliente(cliente, "Gerente de contas")),
        (
            "Site SNMPc",
            valor_resumo_cliente(cliente, "Site", "Sem vínculo"),
            "site"
        ),
        (
            "Setorial",
            setorial,
            "topologia"
        ),
        ("GoTo SNMPc", valor_resumo_cliente(cliente, "GoTo SNMPc")),
        ("Latitude", valor_resumo_cliente(cliente, "Latitude", "0")),
        ("Longitude", valor_resumo_cliente(cliente, "Longitude", "0")),
        ("Altitude", valor_resumo_cliente(cliente, "Altitude", "0")),
        ("Altura", valor_resumo_cliente(cliente, "Altura", "0")),
        (
            "Equipamentos",
            valor_resumo_cliente(
                cliente,
                "Equipamentos",
                "Nenhum equipamento associado"
            ),
            "multilinha"
        )
    ]

    for inicio in range(0, len(campos), 3):
        colunas = st.columns(3)

        for coluna, campo in zip(colunas, campos[inicio:inicio + 3]):
            with coluna:
                rotulo = campo[0]
                valor = campo[1]
                acao = campo[2] if len(campo) > 2 else ""

                if acao == "site":
                    mostrar_campo_resumo_link(
                        rotulo,
                        valor,
                        "abrir_site_gerenciamento",
                        site_cliente
                    )
                elif acao == "topologia":
                    mostrar_campo_resumo_link(
                        rotulo,
                        valor,
                        "abrir_topologia_site",
                        site_cliente
                    )
                elif acao == "multilinha":
                    mostrar_campo_resumo_multilinha(rotulo, valor)
                else:
                    mostrar_campo_resumo(rotulo, valor)

    mostrar_vinculos_atendimento_cliente(cliente)
    mostrar_links_uteis_cliente(cliente)


def mostrar_consulta_clientes(sites, equipamentos):
    st.header("Clientes")
    df_clientes = montar_base_consulta_clientes(sites, equipamentos)

    if df_clientes.empty:
        st.warning("Nenhum cliente ativo foi encontrado na base atual.")
        return

    cliente = selecionar_cliente(df_clientes, "clientes_consulta")

    if not cliente:
        st.info("Pesquise e selecione um cliente para abrir a consulta.")
        return

    mostrar_resumo_cliente(cliente)


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
