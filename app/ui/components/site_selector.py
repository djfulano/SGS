import pandas as pd
import streamlit as st


SITE_SEARCH_PLACEHOLDER = "Digite para pesquisar e selecione um site"


def _valor_registro(registro, *campos):
    for campo in campos:
        valor = (
            registro.get(campo)
            if hasattr(registro, "get")
            else getattr(registro, campo, None)
        )

        if valor is None or pd.isna(valor):
            continue

        texto = str(valor).strip()

        if texto:
            return texto[:-2] if texto.endswith(".0") else texto

    return ""


def rotulo_busca_site(registro):
    nome_snmpc = _valor_registro(
        registro,
        "Site SNMPc",
        "SNMPc",
        "nome"
    )
    codigo_aquiles = _valor_registro(
        registro,
        "Codigo",
        "Código Aquiles",
        "codigo_topos"
    )
    nome = _valor_registro(
        registro,
        "Nome Cadastro",
        "Nome",
        "nome_cadastro"
    )
    microsiga = _valor_registro(
        registro,
        "Microsiga",
        "Código Microsiga",
        "microsiga"
    )

    return (
        f"{nome_snmpc or '-'} - {codigo_aquiles or '-'} / "
        f"{nome or '-'} - {microsiga or '-'}"
    )


def selecionar_site_pesquisavel(
    opcoes,
    rotulos,
    key,
    rotulo="Site"
):
    return st.selectbox(
        rotulo,
        list(opcoes),
        index=None,
        placeholder=SITE_SEARCH_PLACEHOLDER,
        format_func=lambda opcao: rotulos.get(opcao, str(opcao)),
        key=key
    )
