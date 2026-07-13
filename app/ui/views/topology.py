import hashlib
import re

import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.config import CLIENTES_FILE
from app.services.product_catalog import infer_product_fields
from app.services.product_catalog import load_product_catalog
from app.services.products import carregar_clientes_excel_sva
from app.services.products import eh_produto_sva
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import clientes_totais_site
from app.services.site_metrics import custo_indireto_site
from app.services.site_metrics import custo_site
from app.services.site_metrics import custo_total_site
from app.services.site_metrics import montar_escopo_sites
from app.services.site_metrics import montar_resumo_selecao_sites
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import receita_total_site
from app.services.site_metrics import sites_descendentes
from app.ui.components.tables import primeira_linha_selecionada


_mostrar_grid = None
_mostrar_dataframe_nativo = None
_mostrar_botao_copiar_texto = None
_formatar_moeda = None
_usuario_logado = None


def configurar_topologia(
    mostrar_grid,
    mostrar_dataframe_nativo,
    mostrar_botao_copiar_texto,
    formatar_moeda,
    usuario_logado=None
):

    global _mostrar_grid
    global _mostrar_dataframe_nativo
    global _mostrar_botao_copiar_texto
    global _formatar_moeda
    global _usuario_logado

    _mostrar_grid = mostrar_grid
    _mostrar_dataframe_nativo = mostrar_dataframe_nativo
    _mostrar_botao_copiar_texto = mostrar_botao_copiar_texto
    _formatar_moeda = formatar_moeda
    _usuario_logado = usuario_logado


def mostrar_grid(*args, **kwargs):

    return _mostrar_grid(*args, **kwargs)


def mostrar_dataframe_nativo(*args, **kwargs):

    return _mostrar_dataframe_nativo(*args, **kwargs)


def mostrar_botao_copiar_texto(*args, **kwargs):

    return _mostrar_botao_copiar_texto(*args, **kwargs)


def formatar_moeda(valor):

    return _formatar_moeda(valor)


def usuario_atual():

    if _usuario_logado:

        return _usuario_logado() or {}

    return {}


def usuario_pode_ver_custos():

    return has_permission(
        usuario_atual(),
        "visualizar_valores_custos"
    )


def formatar_custo(valor):

    if not usuario_pode_ver_custos():
        return "Restrito"

    return formatar_moeda(valor)


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
            if velocidade >= 100
        )
    }


def montar_metricas_banda_telecom_sites(sites_usados, catalogo=None):
    velocidades = []

    for site in sites_usados:
        for cliente in site.clientes:
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
            if velocidade >= 100
        )
    }


def montar_resumo_sites(sites):

    dados = []

    for site in sites.values():

        clientes_diretos = len(site.clientes)
        clientes_indiretos = clientes_indiretos_site(site)
        receita_direta = receita_site(site)
        receita_indireta = receita_indireta_site(site)
        custo_direto = custo_site(site)
        custo_indireto = custo_indireto_site(site)

        dados.append({
            "Site": site.nome,
            "Nome": getattr(site, "nome_cadastro", ""),
            "Tipo": site.tipo,
            "Status Cadastro": getattr(site, "status_cadastro", ""),
            "Clientes Diretos": clientes_diretos,
            "Clientes Indiretos": clientes_indiretos,
            "Clientes Total": clientes_diretos + clientes_indiretos,
            "Receita Direta": receita_direta,
            "Receita Indireta": receita_indireta,
            "Receita Total": receita_direta + receita_indireta,
            "Custo": custo_direto,
            "Custo Direto": custo_direto,
            "Custo Indireto": custo_indireto,
            "Custo Total": custo_direto + custo_indireto
        })

    return pd.DataFrame(dados)


def contar_sites_ativos_resumo(df_sites):
    if df_sites.empty or "Status Cadastro" not in df_sites.columns:
        return 0

    return int(
        df_sites["Status Cadastro"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq("ativo")
        .sum()
    )


def montar_tabela_sites_usados(sites_usados, incluir_filhos):

    dados = []

    for site in sites_usados.values():

        clientes_diretos = len(site.clientes)
        receita_direta = receita_site(site)
        custo_direto = custo_site(site)

        if incluir_filhos:

            clientes_indiretos = clientes_indiretos_site(site)
            receita_indireta = receita_indireta_site(site)
            custo_indireto = custo_indireto_site(site)

        else:

            clientes_indiretos = 0
            receita_indireta = 0
            custo_indireto = 0

        dados.append({
            "Site": site.nome,
            "Tipo": site.tipo,
            "Clientes Diretos": clientes_diretos,
            "Receita Direta": receita_direta,
            "Clientes Indiretos": clientes_indiretos,
            "Receita Indireta": receita_indireta,
            "Clientes Totais": clientes_diretos + clientes_indiretos,
            "Receita Total": receita_direta + receita_indireta,
            "Custo Direto": custo_direto,
            "Custo Indireto": custo_indireto,
            "Custo Total": custo_direto + custo_indireto
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

        for vinculo in site.listar_vinculos_clientes():
            cliente = vinculo["cliente"]
            setorial = vinculo.get("setorial")

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": cliente.num_assinatura,
                "Receita": cliente.receita,
                "Vínculo": vinculo.get("tipo") or "Principal",
                "Tipo Vinculo": (
                    "Adicional"
                    if vinculo.get("tipo") == "Adicional"
                    else "Setorial"
                    if tipo_vinculo_site == "Direto" and setorial
                    else tipo_vinculo_site
                ),
                "Site do Cliente": site.nome,
                "Setorial": setorial or "Direto",
                "Predio": vinculo.get("predio") or "",
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

        for vinculo in site_atual.listar_vinculos_clientes():
            cliente = vinculo["cliente"]
            setorial = vinculo.get("setorial")
            tipo_vinculo = "Site filho"

            if vinculo.get("tipo") == "Adicional":
                tipo_vinculo = "Adicional"
            elif site_atual is site:

                if setorial:

                    tipo_vinculo = "Setorial"

                else:

                    tipo_vinculo = "Direto"

            dados.append({
                "Cliente": cliente.nome,
                "Assinatura": cliente.num_assinatura,
                "Receita": cliente.receita,
                "Vínculo": vinculo.get("tipo") or "Principal",
                "Tipo Vinculo": tipo_vinculo,
                "Site do Cliente": site_atual.nome,
                "Site Origem": site_origem.nome,
                "Setorial": setorial or "Direto",
                "Predio": vinculo.get("predio") or ""
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
        contar_sites_ativos_resumo(df_sites)
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

    if st.session_state.pop("limpar_busca_sites_pendente", False):
        st.session_state["tipos_sites_multiplos"] = tipos_disponiveis
        st.session_state["sites_selecionados_multiplos"] = []
        st.session_state["incluir_filhos_sites"] = True
        st.session_state["mostrar_clientes_sites_selecionados"] = False
        st.session_state["topologia_site_para_adicionar_versao"] = (
            st.session_state.get("topologia_site_para_adicionar_versao", 0)
            + 1
        )

    if "tipos_sites_multiplos" not in st.session_state:
        st.session_state["tipos_sites_multiplos"] = tipos_disponiveis

    if "sites_selecionados_multiplos" not in st.session_state:
        st.session_state["sites_selecionados_multiplos"] = []

    if "topologia_site_para_adicionar_versao" not in st.session_state:
        st.session_state["topologia_site_para_adicionar_versao"] = 0

    tipos_estado = st.session_state.get(
        "tipos_sites_multiplos",
        tipos_disponiveis
    )
    tipos_estado = [
        tipo
        for tipo in tipos_estado
        if tipo in tipos_disponiveis
    ] or tipos_disponiveis

    opcoes_site = sorted(
        nome_site
        for nome_site in nomes_sites
        if sites[nome_site].tipo in tipos_estado
    )

    sites_ja_selecionados = [
        nome_site
        for nome_site in st.session_state.get(
            "sites_selecionados_multiplos",
            []
        )
        if nome_site in sites
    ]

    opcoes_site = sorted(
        set(opcoes_site) | set(sites_ja_selecionados)
    )

    chave_adicionar_site = (
        "topologia_site_para_adicionar_"
        f"{st.session_state['topologia_site_para_adicionar_versao']}"
    )
    site_para_adicionar = st.selectbox(
        "Sites",
        opcoes_site,
        index=None,
        placeholder="Digite para pesquisar e selecione um site",
        key=chave_adicionar_site
    )

    if site_para_adicionar:
        sites_atualizados = list(sites_ja_selecionados)

        if site_para_adicionar not in sites_atualizados:
            sites_atualizados.append(site_para_adicionar)

        st.session_state["sites_selecionados_multiplos"] = sites_atualizados
        st.session_state["topologia_site_para_adicionar_versao"] += 1
        st.rerun()

    sites_escolhidos = list(sites_ja_selecionados)
    st.session_state["sites_selecionados_multiplos"] = sites_escolhidos

    if sites_escolhidos:
        st.caption(f"{len(sites_escolhidos)} site(s) selecionado(s)")

        for indice, nome_site in enumerate(sites_escolhidos):
            col_site, col_remover = st.columns(
                [
                    0.86,
                    0.14
                ],
                vertical_alignment="center"
            )

            with col_site:
                st.markdown(f"- {nome_site}")

            with col_remover:
                chave_remover = hashlib.md5(nome_site.encode()).hexdigest()

                if st.button(
                    "Remover",
                    key=f"remover_site_topologia_{indice}_{chave_remover}",
                    type="secondary",
                    use_container_width=True
                ):
                    st.session_state["sites_selecionados_multiplos"] = [
                        site_escolhido
                        for site_escolhido in sites_escolhidos
                        if site_escolhido != nome_site
                    ]
                    st.session_state["mostrar_clientes_sites_selecionados"] = False
                    st.rerun()

    col_tipos, col_limpar = st.columns(
        [
            0.84,
            0.16
        ],
        vertical_alignment="bottom"
    )

    with col_tipos:
        tipos_selecionados = st.multiselect(
            "Tipos",
            tipos_disponiveis,
            default=tipos_estado,
            key="tipos_sites_multiplos"
        )

    with col_limpar:
        if st.button(
            "Limpar",
            key="limpar_busca_sites",
            type="secondary",
            use_container_width=True
        ):
            st.session_state["limpar_busca_sites_pendente"] = True
            st.rerun()

    if not tipos_selecionados:
        st.info("Selecione ao menos um tipo para carregar opções de sites.")

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
    catalogo_produtos = load_product_catalog()
    metricas_banda = montar_metricas_banda_telecom_sites(
        usados.values(),
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

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Custo direto",
        formatar_custo(resumo["custo_direto"])
    )

    col2.metric(
        "Custo indireto",
        formatar_custo(resumo["custo_indireto"])
    )

    col3.metric(
        "Custo total",
        formatar_custo(resumo["custo_total"])
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Maior banda Telecom ativa",
        maior_banda
    )

    col2.metric(
        "Somatória das bandas ativas",
        soma_banda
    )

    col3.metric(
        "Produtos a partir de 100 Mbps",
        metricas_banda["acima_100_mbps"]
    )

    texto_resumo = "\n".join([
        f"Total de clientes\t{resumo['clientes_total']}",
        f"Total de receita\t{formatar_moeda(resumo['receita_total'])}",
        f"Sites usados\t{len(usados)}",
        f"Clientes diretos\t{resumo['clientes_diretos']}",
        f"Receita direta\t{formatar_moeda(resumo['receita_direta'])}",
        f"Clientes indiretos\t{resumo['clientes_indiretos']}",
        f"Receita indireta\t{formatar_moeda(resumo['receita_indireta'])}",
        f"Custo direto\t{formatar_custo(resumo['custo_direto'])}",
        f"Custo indireto\t{formatar_custo(resumo['custo_indireto'])}",
        f"Custo total\t{formatar_custo(resumo['custo_total'])}",
        f"Maior banda Telecom ativa\t{maior_banda}",
        f"Somatória das bandas ativas\t{soma_banda}",
        (
            "Produtos a partir de 100 Mbps\t"
            f"{metricas_banda['acima_100_mbps']}"
        )
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

        resposta_clientes = mostrar_grid(
            df_clientes_selecionados,
            height=520,
            key="grid_clientes_sites_selecionados",
            habilitar_selecao=True,
            mostrar_abrir_site=False
        )
        cliente_selecionado = primeira_linha_selecionada(
            resposta_clientes or {}
        )
        assinatura_selecionada = str(
            (cliente_selecionado or {}).get("Assinatura") or ""
        ).strip()

        if st.button(
            "Abrir cliente selecionado",
            key="topologia_abrir_cliente_consulta",
            type="secondary",
            disabled=not bool(assinatura_selecionada)
        ):

            usuario = usuario_atual()

            if not (
                has_permission(usuario, "clientes")
                or has_permission(usuario, "clientes_consulta")
            ):
                st.warning(
                    "Seu usuário não possui permissão para abrir Clientes > Consulta."
                )

            else:
                st.session_state["abrir_cliente_consulta"] = assinatura_selecionada
                st.session_state["clientes_subaba"] = "clientes_consulta"
                st.session_state["proxima_aba_principal"] = "clientes"
                st.rerun()


def mostrar_detalhe_site(site):

    st.subheader(site.nome)

    clientes_diretos_qtd = len(site.clientes)
    clientes_indiretos_qtd = clientes_indiretos_site(site)
    receita_direta = receita_site(site)
    receita_indireta = receita_indireta_site(site)
    custo_direto = custo_site(site)
    custo_indireto = custo_indireto_site(site)
    custo_total = custo_total_site(site)
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
        "Custo direto",
        formatar_custo(custo_direto)
    )

    col2.metric(
        "Custo indireto",
        formatar_custo(custo_indireto)
    )

    col3.metric(
        "Custo total",
        formatar_custo(custo_total)
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
        "Produtos a partir de 100 Mbps",
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
        f"Custo Direto\t{formatar_custo(custo_direto)}",
        f"Custo Indireto\t{formatar_custo(custo_indireto)}",
        f"Custo Total\t{formatar_custo(custo_total)}",
        f"Maior banda Telecom ativa no site\t{maior_banda}",
        f"Somatória das bandas ativas\t{soma_banda}",
        (
            "Produtos a partir de 100 Mbps\t"
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

    vinculos_site = site.listar_vinculos_clientes()
    clientes_diretos = [
        vinculo
        for vinculo in vinculos_site
        if not vinculo.get("setorial")
    ]

    if clientes_diretos:

        st.markdown("**Diretamente conectados**")

        mostrar_grid(
            pd.DataFrame([
                {
                    "Vínculo": vinculo.get("tipo") or "Principal",
                    "Cliente": vinculo["cliente"].nome,
                    "Assinatura": vinculo["cliente"].num_assinatura,
                    "Receita": vinculo["cliente"].receita,
                    "Setorial": "Direto"
                }
                for vinculo in clientes_diretos
            ]),
            height=220,
            key=chave_site("grid_clientes_diretos", site)
        )

    setoriais = {}

    for vinculo in vinculos_site:
        setorial = vinculo.get("setorial")

        if setorial:
            setoriais.setdefault(setorial, []).append(vinculo)

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

            for vinculo in setoriais.get(nome_setorial, []):
                cliente = vinculo["cliente"]

                clientes_setoriais.append({
                    "Vínculo": vinculo.get("tipo") or "Principal",
                    "Setorial": nome_setorial,
                    "Cliente": cliente.nome,
                    "Assinatura": cliente.num_assinatura,
                    "Receita": cliente.receita,
                    "Predio": vinculo.get("predio") or ""
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
