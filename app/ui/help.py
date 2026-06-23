import re
import unicodedata

import streamlit as st

from app.ui.branding import FAQ_FILE
from app.ui.branding import MANUAL_USO_FILE
from app.ui.navigation import mostrar_subnavegacao


def normalizar_busca(texto):

    texto = unicodedata.normalize(
        "NFKD",
        str(texto or "")
    )
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return texto.casefold()


def dividir_markdown_em_secoes(conteudo):

    secoes = []
    titulo_atual = ""
    linhas = []

    for linha in conteudo.splitlines():

        match = re.match(
            r"^(#{1,3})\s+(.+)$",
            linha
        )

        if match and match.group(1) in {
            "#",
            "##"
        }:
            if titulo_atual or linhas:
                secoes.append({
                    "titulo": titulo_atual or "Introdução",
                    "conteudo": "\n".join(linhas).strip()
                })

            titulo_atual = match.group(2).strip()
            linhas = []
        else:
            linhas.append(linha)

    if titulo_atual or linhas:
        secoes.append({
            "titulo": titulo_atual or "Introdução",
            "conteudo": "\n".join(linhas).strip()
        })

    return [
        secao
        for secao in secoes
        if secao["titulo"] or secao["conteudo"]
    ]


def carregar_secoes(caminho):

    if not caminho.exists():

        return []

    return dividir_markdown_em_secoes(
        caminho.read_text(
            encoding="utf-8"
        )
    )


def filtrar_secoes(secoes, termo):

    termo = normalizar_busca(termo)

    if not termo:

        return secoes

    return [
        secao
        for secao in secoes
        if termo in normalizar_busca(
            f"{secao['titulo']}\n{secao['conteudo']}"
        )
    ]


def resumo_secao(secao):

    texto = re.sub(
        r"\s+",
        " ",
        secao.get("conteudo", "")
    ).strip()

    return texto[:180] + ("..." if len(texto) > 180 else "")


def mostrar_secao(secao):

    st.markdown(f"### {secao['titulo']}")

    if secao.get("conteudo"):

        st.markdown(
            secao["conteudo"]
        )


def mostrar_manual_interativo():

    secoes = carregar_secoes(
        MANUAL_USO_FILE
    )

    if not secoes:
        st.warning("Manual de uso não encontrado.")
        return

    busca = st.text_input(
        "Buscar no manual",
        placeholder="Ex.: mapa, backup, contratos, usuários, produtos...",
        key="ajuda_busca_manual"
    )
    resultados = filtrar_secoes(
        secoes,
        busca
    )

    if busca:
        st.caption(
            f"{len(resultados)} resultado(s) encontrado(s)."
        )

    if not resultados:
        st.info("Nenhuma seção encontrada para a busca informada.")
        return

    opcoes = [
        secao["titulo"]
        for secao in resultados
    ]
    titulo_selecionado = st.selectbox(
        "Seção",
        opcoes,
        key="ajuda_secao_manual"
    )
    secao = next(
        item
        for item in resultados
        if item["titulo"] == titulo_selecionado
    )

    if busca and len(resultados) > 1:
        with st.expander("Resultados encontrados", expanded=False):
            for item in resultados:
                st.markdown(
                    f"**{item['titulo']}**"
                )
                if item.get("conteudo"):
                    st.caption(
                        resumo_secao(item)
                    )

    mostrar_secao(
        secao
    )


def mostrar_faq_interativo():

    perguntas = carregar_secoes(
        FAQ_FILE
    )

    if not perguntas:
        st.warning("FAQ não encontrado.")
        return

    busca = st.text_input(
        "Buscar no FAQ",
        placeholder="Ex.: senha, mapa, backup, colunas, permissão...",
        key="ajuda_busca_faq"
    )
    resultados = filtrar_secoes(
        perguntas,
        busca
    )

    if busca:
        st.caption(
            f"{len(resultados)} resposta(s) encontrada(s)."
        )

    if not resultados:
        st.info("Nenhuma resposta encontrada para a busca informada.")
        return

    for pergunta in resultados:
        with st.expander(
            pergunta["titulo"],
            expanded=bool(busca) and len(resultados) <= 3
        ):
            st.markdown(
                pergunta.get("conteudo") or ""
            )


def mostrar_ajuda_interativa():

    funcao = mostrar_subnavegacao(
        [
            (
                "manual",
                "Manual",
                mostrar_manual_interativo
            ),
            (
                "faq",
                "FAQ",
                mostrar_faq_interativo
            )
        ],
        key="ajuda_subaba"
    )

    if funcao:
        funcao()
