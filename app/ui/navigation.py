import streamlit as st


def preparar_navegacao_mapa_endereco(session_state, endereco):
    endereco = str(endereco or "").strip()

    if not endereco:
        return False

    session_state["mapa_subaba"] = "mapa_geral"
    session_state["mapa_geral_busca"] = endereco
    session_state.pop("mapa_geral_busca_limpar_pendente", None)
    session_state["proxima_aba_principal"] = "mapa"

    return True


def mostrar_subnavegacao(itens, key, label="Subnavegação"):

    if not itens:

        return None

    chaves = [
        chave
        for chave, _rotulo, _funcao in itens
    ]
    rotulos = {
        chave: rotulo
        for chave, rotulo, _funcao in itens
    }

    if st.session_state.get(key) not in chaves:

        st.session_state[key] = chaves[0]

    selecionado = st.segmented_control(
        label,
        chaves,
        selection_mode="single",
        key=key,
        format_func=lambda chave: rotulos.get(
            chave,
            chave
        ),
        label_visibility="collapsed",
        width="stretch"
    )

    if not selecionado:

        selecionado = chaves[0]

    return next(
        funcao
        for chave, _rotulo, funcao in itens
        if chave == selecionado
    )
