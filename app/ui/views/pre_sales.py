import streamlit as st

from app.auth import has_permission
from app.services.pre_sales import montar_opcoes_sites_pre_venda
from app.services.pre_sales import montar_resumo_pre_venda
from app.services.site_metrics import formatar_banda_mbps
from app.ui.components.site_selector import rotulo_busca_site
from app.ui.components.site_selector import selecionar_site_pesquisavel
from app.ui.components.tables import mostrar_botao_copiar_texto


_formatar_moeda = None
_usuario_logado = None


def configurar_pre_venda(formatar_moeda, usuario_logado):
    global _formatar_moeda
    global _usuario_logado

    _formatar_moeda = formatar_moeda
    _usuario_logado = usuario_logado


def _usuario_atual():
    return _usuario_logado() if _usuario_logado else {}


def _moeda(valor, permissao):
    if not has_permission(_usuario_atual(), permissao):
        return "Restrito"

    return _formatar_moeda(valor)


def mostrar_pre_venda(sites):
    st.header("Pré-Venda")
    st.caption("Resumo comercial, técnico e financeiro do site selecionado.")

    opcoes = montar_opcoes_sites_pre_venda(sites)

    if not opcoes:
        st.info("Nenhum site cadastrado foi encontrado.")
        return

    rotulos = {
        chave: rotulo_busca_site(registro)
        for chave, registro in opcoes.items()
    }
    chaves = sorted(opcoes, key=lambda chave: rotulos[chave].casefold())
    chave_site = selecionar_site_pesquisavel(
        chaves,
        rotulos,
        key="pre_venda_site_selecionado",
    )

    if chave_site is None:
        st.info("Pesquise e selecione um site para carregar o resumo.")
        return

    registro = opcoes[chave_site]
    resumo = montar_resumo_pre_venda(registro)
    maior_banda = (
        formatar_banda_mbps(resumo["maior_banda_mbps"])
        if resumo["maior_banda_mbps"]
        else "Não localizado"
    )
    soma_banda = formatar_banda_mbps(resumo["soma_banda_mbps"])
    receita_total = _moeda(
        resumo["receita_total"],
        "visualizar_valores_clientes",
    )
    receita_direta = _moeda(
        resumo["receita_direta"],
        "visualizar_valores_clientes",
    )
    receita_indireta = _moeda(
        resumo["receita_indireta"],
        "visualizar_valores_clientes",
    )
    custo_direto = _moeda(
        resumo["custo_direto"],
        "visualizar_valores_custos",
    )
    custo_indireto = _moeda(
        resumo["custo_indireto"],
        "visualizar_valores_custos",
    )
    custo_total = _moeda(
        resumo["custo_total"],
        "visualizar_valores_custos",
    )

    st.subheader(rotulos[chave_site])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", resumo["status"])
    col2.metric("Total de clientes", resumo["clientes_total"])
    col3.metric("Total de receita", receita_total)
    col4.metric("Sites filhos", resumo["sites_filhos"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Clientes diretos", resumo["clientes_diretos"])
    col2.metric("Receita direta", receita_direta)
    col3.metric("Clientes indiretos", resumo["clientes_indiretos"])
    col4.metric("Receita indireta", receita_indireta)

    col1, col2, col3 = st.columns(3)
    col1.metric("Custo direto", custo_direto)
    col2.metric("Custo indireto", custo_indireto)
    col3.metric("Custo total", custo_total)

    col1, col2, col3 = st.columns(3)
    col1.metric("Maior banda Telecom ativa", maior_banda)
    col2.metric("Somatória das bandas ativas", soma_banda)
    col3.metric(
        "Produtos a partir de 100 Mbps",
        resumo["produtos_100_mbps"],
    )

    col1, col2 = st.columns(2)
    col1.metric("Rádio Principal", resumo["radio_principal"])
    col2.metric("Rádios instalados", resumo["radios_instalados"])

    texto = "\n".join([
        f"Site\t{rotulos[chave_site]}",
        f"Status\t{resumo['status']}",
        f"Total de clientes\t{resumo['clientes_total']}",
        f"Total de receita\t{receita_total}",
        f"Sites filhos\t{resumo['sites_filhos']}",
        f"Clientes diretos\t{resumo['clientes_diretos']}",
        f"Receita direta\t{receita_direta}",
        f"Clientes indiretos\t{resumo['clientes_indiretos']}",
        f"Receita indireta\t{receita_indireta}",
        f"Custo direto\t{custo_direto}",
        f"Custo indireto\t{custo_indireto}",
        f"Custo total\t{custo_total}",
        f"Maior banda Telecom ativa\t{maior_banda}",
        f"Somatória das bandas ativas\t{soma_banda}",
        f"Produtos a partir de 100 Mbps\t{resumo['produtos_100_mbps']}",
        f"Rádio Principal\t{resumo['radio_principal']}",
        f"Rádios instalados\t{resumo['radios_instalados']}",
    ])
    mostrar_botao_copiar_texto(
        texto,
        rotulo="Copiar resumo",
        discreto=True,
    )
