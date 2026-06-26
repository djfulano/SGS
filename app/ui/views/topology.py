import hashlib
import re

import pandas as pd
import streamlit as st

from app.config import CLIENTES_FILE
from app.services.product_catalog import infer_product_fields
from app.services.product_catalog import load_product_catalog
from app.services.products import carregar_clientes_excel_sva
from app.services.products import eh_produto_sva
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import clientes_totais_site
from app.services.site_metrics import montar_escopo_sites
from app.services.site_metrics import montar_resumo_selecao_sites
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import receita_total_site
from app.services.site_metrics import sites_descendentes


_mostrar_grid = None
_mostrar_dataframe_nativo = None
_mostrar_botao_copiar_texto = None
_formatar_moeda = None


def configurar_topologia(
    mostrar_grid,
    mostrar_dataframe_nativo,
    mostrar_botao_copiar_texto,
    formatar_moeda
):

    global _mostrar_grid
    global _mostrar_dataframe_nativo
    global _mostrar_botao_copiar_texto
    global _formatar_moeda

    _mostrar_grid = mostrar_grid
    _mostrar_dataframe_nativo = mostrar_dataframe_nativo
    _mostrar_botao_copiar_texto = mostrar_botao_copiar_texto
    _formatar_moeda = formatar_moeda


def mostrar_grid(*args, **kwargs):

    return _mostrar_grid(*args, **kwargs)


def mostrar_dataframe_nativo(*args, **kwargs):

    return _mostrar_dataframe_nativo(*args, **kwargs)


def mostrar_botao_copiar_texto(*args, **kwargs):

    return _mostrar_botao_copiar_texto(*args, **kwargs)


def formatar_moeda(valor):

    return _formatar_moeda(valor)


def normalizar_velocidade_mbps(valor):
    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None

    texto = str(valor or "").strip()

    if not texto:
        return None

    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*"
        r"(GBPS|GIGA|GB|G|MBPS|MB|M|KBPS|KB|K)\b",
        texto,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    numero = float(
        match.group(1).replace(
            ",",
            "."
        )
    )
    unidade = match.group(2).upper()

    if unidade in {"GBPS", "GIGA", "GB", "G"}:
        return numero * 1000

    if unidade in {"KBPS", "KB", "K"}:
        return numero / 1000

    return numero


def _linha_catalogo_produto(catalogo, produto):
    if catalogo is None or catalogo.empty or "Nome" not in catalogo.columns:
        return {}

    produto_normalizado = str(produto or "").strip().casefold()

    if not produto_normalizado:
        return {}

    nomes = catalogo["Nome"].astype(str).str.strip().str.casefold()
    linhas = catalogo.loc[nomes == produto_normalizado]

    if linhas.empty:
        return {}

    return linhas.iloc[-1].to_dict()


def velocidade_telecom_produto_mbps(produto, catalogo=None):
    produto = str(produto or "").strip()

    if not produto:
        return None

    linha_catalogo = _linha_catalogo_produto(
        catalogo,
        produto
    )
    inferido = infer_product_fields(produto)

    tipo = (
        str(linha_catalogo.get("Tipo") or inferido.get("Tipo") or "")
        .strip()
        .casefold()
    )

    if tipo != "telecom":
        return None

    for valor in [
        linha_catalogo.get("Velocidade"),
        inferido.get("Velocidade"),
        produto
    ]:
        velocidade = normalizar_velocidade_mbps(valor)

        if velocidade:
            return velocidade

    return None


def formatar_banda_mbps(valor):
    if not valor or valor <= 0:
        return "0 Mbps"

    if valor >= 1000:
        valor_gbps = valor / 1000
        texto = f"{valor_gbps:g}".replace(
            ".",
            ","
        )
        return f"{texto} Gbps"

    texto = f"{valor:g}".replace(
        ".",
        ","
    )
    return f"{texto} Mbps"


def montar_metricas_banda_telecom_site(site, catalogo=None):
    velocidades = []

    for site_atual in sites_descendentes(site):
        for cliente in site_atual.clientes:
            velocidade = velocidade_telecom_produto_mbps(
                getattr(cliente, "produto", ""),
                catalogo
            )

            if velocidade:
                velocidades.append(velocidade)

    return {
        "maior_mbps": max(velocidades) if velocidades else None,
        "soma_mbps": sum(velocidades),
        "acima_100_mbps": sum(
            1
            for velocidade in velocidades
            if velocidade > 100
        )
    }


def montar_resumo_sites(sites):

    dados = []

    for site in sites.values():

        clientes_diretos = len(site.clientes)
        clientes_indiretos = clientes_indiretos_site(site)
        receita_direta = receita_site(site)
        receita_indireta = receita_indireta_site(site)

        dados.append({
            "Site": site.nome,
            "Tipo": site.tipo,
            "Clientes Diretos": clientes_diretos,
            "Clientes Indiretos": clientes_indiretos,
            "Clientes Total": clientes_diretos + clientes_indiretos,
            "Receita Direta": receita_direta,
            "Receita Indireta": receita_indireta,
            "Receita Total": receita_direta + receita_indireta
        })

    return pd.DataFrame(dados)


def montar_tabela_sites_usados(sites_usados, incluir_filhos):

    dados = []

    for site in sites_usados.values():

        clientes_diretos = len(site.clientes)
        receita_direta = receita_site(site)

        if incluir_filhos:

            clientes_indiretos = clientes_indiretos_site(site)
            receita_indireta = receita_indireta_site(site)

        else:

            clientes_indiretos = 0
            receita_indireta = 0

        dados.append({
            "Site": site.nome,
            "Tipo": site.tipo,
            "Clientes Diretos": clientes_diretos,
            "Receita Direta": receita_direta,
            "Clientes Indiretos": clientes_indiretos,
            "Receita Indireta": receita_indireta,
            "Clientes Totais": clientes_diretos + clientes_indiretos,
            "Receita Total": receita_direta + receita_indireta
        })

    return pd.DataFrame(dados)


def montar_clientes_sites_usados(selecionados, usados):

    dados = []

    for site in usados.values():

        tipo_vinculo_site = (
            "Direto"
            if site.nome in selecionados
            else "Site filho"
        )

        for cliente in site.clientes:

            setorial = getattr(cliente, "setorial", None)

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": cliente.num_assinatura,
                "Receita": cliente.receita,
                "Tipo Vinculo": (
                    "Setorial"
                    if tipo_vinculo_site == "Direto" and setorial
                    else tipo_vinculo_site
                ),
                "Site do Cliente": site.nome,
                "Setorial": setorial or "Direto",
                "Predio": getattr(cliente, "predio_estrutura", None) or "",
                "Produto": getattr(cliente, "produto", ""),
                "Endereco": getattr(cliente, "endereco_completo", ""),
                "Bairro": getattr(cliente, "bairro", ""),
                "Cidade": getattr(cliente, "cidade", "")
            })

    return pd.DataFrame(dados)


def chave_site(prefixo, site):

    digest = hashlib.md5(
        site.nome.encode("utf-8")
    ).hexdigest()

    return f"{prefixo}_{digest}"


def montar_clientes_data(clientes):

    dados = []

    for cliente in clientes:

        dados.append({
            "Cliente": cliente.nome,
            "Assinatura": cliente.num_assinatura,
            "Receita": cliente.receita,
            "Setorial": getattr(cliente, "setorial", None) or "Direto"
        })

    return pd.DataFrame(dados)


def montar_clientes_completos_site(site):

    dados = []

    def adicionar_clientes(site_atual, site_origem):

        for cliente in site_atual.clientes:

            setorial = getattr(cliente, "setorial", None)
            tipo_vinculo = "Site filho"

            if site_atual is site:

                if setorial:

                    tipo_vinculo = "Setorial"

                else:

                    tipo_vinculo = "Direto"

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": cliente.num_assinatura,
                "Receita": cliente.receita,
                "Tipo Vinculo": tipo_vinculo,
                "Site do Cliente": site_atual.nome,
                "Site Origem": site_origem.nome,
                "Setorial": setorial or "Direto",
                "Predio": getattr(cliente, "predio_estrutura", None) or ""
            })

        for filho in site_atual.filhos:

            adicionar_clientes(
                filho,
                filho
            )

    adicionar_clientes(
        site,
        site
    )

    return pd.DataFrame(dados)


def montar_sites_data(sites):

    dados = []

    for site in sites:

        clientes_diretos = len(site.clientes)
        clientes_indiretos = clientes_indiretos_site(site)
        receita_direta = receita_site(site)
        receita_indireta = receita_indireta_site(site)

        dados.append({
            "Site": site.nome,
            "Tipo": site.tipo,
            "Clientes Diretos": clientes_diretos,
            "Clientes Indiretos": clientes_indiretos,
            "Clientes Total": clientes_diretos + clientes_indiretos,
            "Receita Direta": receita_direta,
            "Receita Indireta": receita_indireta,
            "Receita Total": receita_direta + receita_indireta
        })

    return pd.DataFrame(dados)


def mostrar_metricas(df_sites):

    df_clientes_excel = carregar_clientes_excel_sva(
        CLIENTES_FILE,
        str(CLIENTES_FILE.stat().st_mtime)
    )

    if df_clientes_excel.empty:

        assinaturas_ativas = 0
        clientes_sva = 0
        clientes_telecom = 0

    else:

        df_clientes_excel = df_clientes_excel[
            df_clientes_excel["Assinatura"].astype(str).str.strip() != ""
        ].drop_duplicates(
            subset=["Assinatura"]
        )
        assinaturas_ativas = len(df_clientes_excel)
        clientes_sva = int(
            df_clientes_excel["Produto"].apply(eh_produto_sva).sum()
        )
        clientes_telecom = assinaturas_ativas - clientes_sva

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Assinaturas ativas",
        assinaturas_ativas
    )

    col2.metric(
        "Clientes Telecom",
        clientes_telecom
    )

    col3.metric(
        "Clientes SVA",
        clientes_sva
    )

    col4.metric(
        "Sites",
        len(df_sites)
    )


def mostrar_sites_receitas(sites, df_sites):

    st.header("Sites e receitas")

    nomes_sites = sorted(
        sites.keys()
    )

    st.markdown("**Filtros**")

    tipos_disponiveis = [
        tipo
        for tipo in [
            "POP",
            "BH",
            "REP",
            "DC"
        ]
        if tipo in set(df_sites["Tipo"].dropna())
    ]

    if st.button(
        "Limpar busca",
        key="limpar_busca_sites"
    ):

        st.session_state["tipos_sites_multiplos"] = tipos_disponiveis
        st.session_state["sites_selecionados_multiplos"] = []
        st.session_state["incluir_filhos_sites"] = True
        st.session_state["mostrar_clientes_sites_selecionados"] = False
        st.rerun()

    tipos_selecionados = st.multiselect(
        "Tipos",
        tipos_disponiveis,
        default=tipos_disponiveis,
        key="tipos_sites_multiplos"
    )

    opcoes_site = sorted(
        nome_site
        for nome_site in nomes_sites
        if sites[nome_site].tipo in tipos_selecionados
    )

    sites_ja_selecionados = st.session_state.get(
        "sites_selecionados_multiplos",
        []
    )

    opcoes_site = sorted(
        set(opcoes_site) | set(sites_ja_selecionados)
    )

    sites_escolhidos = st.multiselect(
        "Sites",
        opcoes_site,
        key="sites_selecionados_multiplos"
    )

    incluir_filhos = st.checkbox(
        "Incluir sites filhos",
        value=True,
        key="incluir_filhos_sites"
    )

    if not sites_escolhidos:

        st.info(
            "Selecione um ou mais sites para carregar o resumo."
        )

        return

    sites_selecionados = [
        sites[nome_site]
        for nome_site in sites_escolhidos
        if nome_site in sites
    ]

    selecionados, usados = montar_escopo_sites(
        sites_selecionados,
        incluir_filhos
    )

    resumo = montar_resumo_selecao_sites(
        selecionados,
        usados
    )

    col_acao_mapa, _col_acao_vazio = st.columns([1, 4])

    with col_acao_mapa:

        if st.button(
            "Carregar mapa",
            key="topologia_carregar_mapa"
        ):
            st.session_state["mapa_sites_escolhidos"] = sites_escolhidos
            st.session_state["mapa_incluir_filhos"] = incluir_filhos
            st.session_state["mapa_incluir_clientes"] = True
            st.session_state["proxima_aba_principal"] = "mapa"
            st.rerun()

    st.markdown("**Resumo dos sites selecionados**")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total de clientes",
        resumo["clientes_total"]
    )

    col2.metric(
        "Total de receita",
        formatar_moeda(
            resumo["receita_total"]
        )
    )

    col3.metric(
        "Sites usados",
        len(usados)
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Clientes diretos",
        resumo["clientes_diretos"]
    )

    col2.metric(
        "Receita direta",
        formatar_moeda(
            resumo["receita_direta"]
        )
    )

    col3.metric(
        "Clientes indiretos",
        resumo["clientes_indiretos"]
    )

    col4.metric(
        "Receita indireta",
        formatar_moeda(
            resumo["receita_indireta"]
        )
    )

    texto_resumo = "\n".join([
        f"Total de clientes\t{resumo['clientes_total']}",
        f"Total de receita\t{formatar_moeda(resumo['receita_total'])}",
        f"Sites usados\t{len(usados)}",
        f"Clientes diretos\t{resumo['clientes_diretos']}",
        f"Receita direta\t{formatar_moeda(resumo['receita_direta'])}",
        f"Clientes indiretos\t{resumo['clientes_indiretos']}",
        f"Receita indireta\t{formatar_moeda(resumo['receita_indireta'])}"
    ])

    _col1, col2 = st.columns([1, 0.18])

    with col2:

        mostrar_botao_copiar_texto(
            texto_resumo,
            rotulo="Copiar resumo",
            discreto=True
        )

    st.markdown("**Sites usados**")

    df_usados = montar_tabela_sites_usados(
        usados,
        incluir_filhos
    )

    if not df_usados.empty:

        df_usados = df_usados.sort_values(
            by="Site"
        )

    mostrar_grid(
        df_usados,
        height=360,
        key="grid_sites_usados"
    )

    chave_clientes_selecionados = "mostrar_clientes_sites_selecionados"

    if chave_clientes_selecionados not in st.session_state:

        st.session_state[chave_clientes_selecionados] = False

    if st.button(
        "Mostrar tabela completa de clientes",
        key="botao_clientes_sites_selecionados"
    ):

        st.session_state[chave_clientes_selecionados] = not st.session_state[
            chave_clientes_selecionados
        ]

    if st.session_state[chave_clientes_selecionados]:

        df_clientes_selecionados = montar_clientes_sites_usados(
            selecionados,
            usados
        )

        st.markdown("**Clientes dos dados selecionados**")

        if df_clientes_selecionados.empty:

            st.info(
                "Os sites selecionados não possuem clientes."
            )

        else:

            df_clientes_selecionados = df_clientes_selecionados.sort_values(
                by=[
                    "Site do Cliente",
                    "Setorial",
                    "Cliente"
                ]
            )

            mostrar_grid(
                df_clientes_selecionados,
                height=520,
                key="grid_clientes_sites_selecionados"
            )


def mostrar_detalhe_site(site):

    st.subheader(site.nome)

    clientes_diretos_qtd = len(site.clientes)
    clientes_indiretos_qtd = clientes_indiretos_site(site)
    receita_direta = receita_site(site)
    receita_indireta = receita_indireta_site(site)
    clientes_total = clientes_diretos_qtd + clientes_indiretos_qtd
    receita_total = receita_direta + receita_indireta
    catalogo_produtos = load_product_catalog()
    metricas_banda = montar_metricas_banda_telecom_site(
        site,
        catalogo_produtos
    )
    maior_banda = (
        formatar_banda_mbps(metricas_banda["maior_mbps"])
        if metricas_banda["maior_mbps"]
        else "Não localizado"
    )
    soma_banda = formatar_banda_mbps(
        metricas_banda["soma_mbps"]
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total de clientes",
        clientes_total
    )

    col2.metric(
        "Total de receita",
        formatar_moeda(receita_total)
    )

    col3.metric(
        "Tipo",
        site.tipo
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Clientes diretos",
        clientes_diretos_qtd
    )

    col2.metric(
        "Receita direta",
        formatar_moeda(receita_direta)
    )

    col3.metric(
        "Clientes indiretos",
        clientes_indiretos_qtd
    )

    col4.metric(
        "Receita indireta",
        formatar_moeda(receita_indireta)
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Maior banda Telecom ativa no site",
        maior_banda
    )

    col2.metric(
        "Somatória das bandas ativas",
        soma_banda
    )

    col3.metric(
        "Produtos acima de 100 Mbps",
        metricas_banda["acima_100_mbps"]
    )

    resumo_site = "\n".join([
        f"Site\t{site.nome}",
        f"Tipo\t{site.tipo}",
        f"Clientes Diretos\t{clientes_diretos_qtd}",
        f"Receita Direta\t{formatar_moeda(receita_direta)}",
        f"Clientes Indiretos\t{clientes_indiretos_qtd}",
        f"Receita Indireta\t{formatar_moeda(receita_indireta)}",
        f"Clientes Total\t{clientes_total}",
        f"Receita Total\t{formatar_moeda(receita_total)}",
        f"Maior banda Telecom ativa no site\t{maior_banda}",
        f"Somatória das bandas ativas\t{soma_banda}",
        (
            "Produtos superiores a 100 Mbps\t"
            f"{metricas_banda['acima_100_mbps']}"
        )
    ])

    mostrar_botao_copiar_texto(
        resumo_site,
        rotulo="Copiar resumo do site"
    )

    chave_lista_completa = f"lista_completa_{site.nome}"

    if chave_lista_completa not in st.session_state:

        st.session_state[chave_lista_completa] = False

    if st.button(
        "Visualizar lista completa de clientes",
        key=f"botao_{chave_lista_completa}"
    ):

        st.session_state[chave_lista_completa] = not st.session_state[
            chave_lista_completa
        ]

    if st.session_state[chave_lista_completa]:

        df_clientes_completo = montar_clientes_completos_site(site)

        st.markdown("**Lista completa de clientes**")

        if df_clientes_completo.empty:

            st.info(
                "Este site não possui clientes diretos ou indiretos."
            )

        else:

            df_clientes_completo = df_clientes_completo.sort_values(
                by=[
                    "Site do Cliente",
                    "Setorial",
                    "Cliente"
                ]
            )

            mostrar_grid(
                df_clientes_completo,
                height=520,
                key=chave_site("grid_clientes_completo", site)
            )

    if site.filhos:

        st.markdown("**Sites filhos**")

        df_filhos = montar_sites_data(site.filhos).sort_values(
            by="Receita Total",
            ascending=False
        )

        mostrar_dataframe_nativo(
            df_filhos,
            height=260,
            key=chave_site("tabela_filhos", site)
        )

    clientes_diretos = [
        cliente
        for cliente in site.clientes
        if not getattr(cliente, "setorial", None)
    ]

    if clientes_diretos:

        st.markdown("**Diretamente conectados**")

        mostrar_grid(
            montar_clientes_data(clientes_diretos),
            height=220,
            key=chave_site("grid_clientes_diretos", site)
        )

    setoriais = getattr(
        site,
        "setoriais",
        {}
    )

    sites_por_setorial = getattr(
        site,
        "sites_por_setorial",
        {}
    )

    nomes_setoriais = sorted(
        set(
            setoriais.keys()
        ) | set(
            sites_por_setorial.keys()
        )
    )

    if nomes_setoriais:

        clientes_setoriais = []

        for nome_setorial in nomes_setoriais:

            for cliente in setoriais.get(nome_setorial, []):

                clientes_setoriais.append({
                    "Setorial": nome_setorial,
                    "Cliente": cliente.nome,
                    "Assinatura": cliente.num_assinatura,
                    "Receita": cliente.receita,
                    "Predio": getattr(cliente, "predio_estrutura", None) or ""
                })

        if clientes_setoriais:

            st.markdown("**Clientes por setorial**")

            mostrar_grid(
                pd.DataFrame(clientes_setoriais).sort_values(
                    by=[
                        "Setorial",
                        "Cliente"
                    ]
                ),
                height=320,
                key=chave_site("grid_clientes_setoriais", site)
            )

        sites_setoriais = []

        for nome_setorial in nomes_setoriais:

            for site_filho in sites_por_setorial.get(nome_setorial, []):

                sites_setoriais.append({
                    "Setorial": nome_setorial,
                    "Site": site_filho.nome,
                    "Tipo": site_filho.tipo,
                    "Clientes Diretos": len(site_filho.clientes),
                    "Receita Direta": receita_site(site_filho),
                    "Clientes Indiretos": clientes_indiretos_site(site_filho),
                    "Receita Indireta": receita_indireta_site(site_filho),
                    "Clientes Totais": clientes_totais_site(site_filho),
                    "Receita Total": receita_total_site(site_filho)
                })

        if sites_setoriais:

            st.markdown("**Sites filhos por setorial**")

            mostrar_dataframe_nativo(
                pd.DataFrame(sites_setoriais).sort_values(
                    by=[
                        "Setorial",
                        "Site"
                    ]
                ),
                height=320,
                key=chave_site("tabela_sites_setoriais", site)
            )

    if not clientes_diretos and not nomes_setoriais:

        st.info(
            "Este site não possui clientes vinculados."
        )
