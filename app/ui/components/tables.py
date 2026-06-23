import hashlib
import inspect
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid
from st_aggrid import GridOptionsBuilder
from st_aggrid import GridUpdateMode
from st_aggrid import JsCode


TABLE_CALLBACKS = {
    "can_view_values": lambda: True,
    "can_view_cost_values": lambda: True,
    "can_copy_tables": lambda: True,
    "format_currency": lambda valor: valor,
    "load_preference": lambda _key, default: default,
    "save_preference": lambda _key, _value: None
}


def configurar_componentes_tabela(
    can_view_values,
    format_currency,
    load_preference,
    save_preference,
    can_view_cost_values=None,
    can_copy_tables=None
):

    TABLE_CALLBACKS.update({
        "can_view_values": can_view_values,
        "can_view_cost_values": can_view_cost_values or can_view_values,
        "can_copy_tables": can_copy_tables or (lambda: True),
        "format_currency": format_currency,
        "load_preference": load_preference,
        "save_preference": save_preference
    })


def usuario_pode_ver_valores():

    return bool(TABLE_CALLBACKS["can_view_values"]())


def usuario_pode_ver_custos():

    return bool(TABLE_CALLBACKS["can_view_cost_values"]())


def usuario_pode_copiar_tabelas():

    return bool(TABLE_CALLBACKS["can_copy_tables"]())


def formatar_moeda(valor):

    return TABLE_CALLBACKS["format_currency"](valor)


def load_user_preference(chave, padrao):

    return TABLE_CALLBACKS["load_preference"](
        chave,
        padrao
    )


def save_user_preference(chave, valor):

    TABLE_CALLBACKS["save_preference"](
        chave,
        valor
    )


def colunas_valores_clientes():

    return (
        "Receita",
        "Mensalidade"
    )


def colunas_valores_custos():

    return (
        "Custo",
        "Valor Base",
        "Valor Equipamento",
        "Valor total",
        "Valor Total",
        "Resultado",
        "Lucro"
    )


def colunas_percentuais():

    return (
        "Margem",
        "Rentabilidade"
    )


def eh_coluna_valor_cliente(coluna):
    coluna = str(coluna)

    return any(
        termo in coluna
        for termo in colunas_valores_clientes()
    )


def eh_coluna_valor_custo(coluna):
    coluna = str(coluna)

    return any(
        termo in coluna
        for termo in colunas_valores_custos()
    )


def eh_coluna_percentual(coluna):
    coluna = str(coluna)

    return any(
        termo in coluna
        for termo in colunas_percentuais()
    )


def eh_coluna_valor(coluna):

    return (
        eh_coluna_valor_cliente(coluna)
        or eh_coluna_valor_custo(coluna)
        or eh_coluna_percentual(coluna)
    )


def eh_coluna_monetaria(coluna):

    return (
        eh_coluna_valor_cliente(coluna)
        or eh_coluna_valor_custo(coluna)
    )


def formatar_percentual(valor):
    numero = pd.to_numeric(
        valor,
        errors="coerce"
    )

    if pd.isna(numero):
        return ""

    return f"{float(numero):.1%}".replace(
        ".",
        ","
    )


def formatar_dataframe_para_copia(df):

    df_copia = df.copy()

    colunas_remover = []

    if not usuario_pode_ver_valores():
        colunas_remover.extend(
            coluna
            for coluna in df_copia.columns
            if eh_coluna_valor_cliente(coluna)
        )

    if not usuario_pode_ver_custos():
        colunas_remover.extend(
            coluna
            for coluna in df_copia.columns
            if (
                eh_coluna_valor_custo(coluna)
                or eh_coluna_percentual(coluna)
            )
        )

    if colunas_remover:
        df_copia = df_copia.drop(
            columns=colunas_remover,
            errors="ignore"
        )

    for coluna in df_copia.columns:

        if eh_coluna_monetaria(coluna):

            df_copia[coluna] = df_copia[coluna].apply(
                formatar_moeda
            )

        elif eh_coluna_percentual(coluna):

            df_copia[coluna] = df_copia[coluna].apply(
                formatar_percentual
            )

    return df_copia


def preparar_dataframe_exibicao(df):

    colunas_remover = []

    if not usuario_pode_ver_valores():
        colunas_remover.extend(
            coluna
            for coluna in df.columns
            if eh_coluna_valor_cliente(coluna)
        )

    if not usuario_pode_ver_custos():
        colunas_remover.extend(
            coluna
            for coluna in df.columns
            if (
                eh_coluna_valor_custo(coluna)
                or eh_coluna_percentual(coluna)
            )
        )

    if not colunas_remover:
        return df

    return df.drop(
        columns=colunas_remover,
        errors="ignore"
    )


COLUNAS_EXIBICAO_PT_BR = {
    "Arvore": "Árvore",
    "Codigo": "Código",
    "Codigo Aquiles": "Código Aquiles",
    "Codigo Microsiga": "Código Microsiga",
    "Codigo Condominio": "Código Condomínio",
    "Abreviacao": "Abreviação",
    "Favorecido": "Favorecido",
    "Endereco": "Endereço",
    "Endereco Equipamento": "Endereço Equipamento",
    "Endereco Cliente": "Endereço Cliente",
    "Numero": "Número",
    "Ativacao": "Ativação",
    "Restricao": "Restrição",
    "Observacao": "Observação",
    "Predio": "Prédio",
    "Predios": "Prédios",
    "Predio SNMPc": "Prédio SNMPc",
    "Predio Equipamento": "Prédio Equipamento",
    "Icone": "Ícone",
    "Icones Cliente": "Ícones Cliente",
    "Status Vinculo": "Status Vínculo",
    "Vinculo": "Vínculo",
    "Sem vinculo": "Sem vínculo",
    "Identificacao": "Identificação",
    "Versao": "Versão",
    "Usuario": "Usuário",
    "Usuarios": "Usuários",
    "Modulos": "Módulos",
    "Importacao": "Importação",
    "Data Remocao": "Data Remoção",
    "Data Cancelamento": "Data Cancelamento",
    "Site Responsavel": "Site Responsável",
    "Enviado por": "Enviado por",
    "Enviado em": "Enviado em"
}


def dataframe_para_exibicao_pt_br(df):

    return df.rename(
        columns={
            coluna: COLUNAS_EXIBICAO_PT_BR.get(
                coluna,
                coluna
            )
            for coluna in df.columns
        }
    )


def mostrar_botao_copiar_texto(texto, rotulo="Copiar", discreto=False):

    if not usuario_pode_copiar_tabelas():
        return

    chave = hashlib.md5(
        texto.encode("utf-8")
    ).hexdigest()

    button_id = f"copy_{chave}"
    status_id = f"status_{chave}"
    estilo_botao = (
        """
                border: 0;
                border-radius: 4px;
                background: transparent;
                color: #57606a;
                cursor: pointer;
                font: 12px sans-serif;
                padding: 3px 6px;
        """
        if discreto
        else
        """
                border: 1px solid #d0d7de;
                border-radius: 6px;
                background: #ffffff;
                color: #24292f;
                cursor: pointer;
                font: 14px sans-serif;
                padding: 6px 12px;
        """
    )
    components.html(
        f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <style>
                html,
                body {{
                    margin: 0;
                    padding: 0;
                    background: transparent;
                    overflow: hidden;
                }}
            </style>
        </head>
        <body>
            <button
                id="{button_id}"
                style="{estilo_botao}"
            >
                {rotulo}
            </button>
            <span
                id="{status_id}"
                style="font: 12px sans-serif; margin-left: 6px; color: #57606a;"
            ></span>
        <script>
            const button = document.getElementById({json.dumps(button_id)});
            const status = document.getElementById({json.dumps(status_id)});
            const text = {json.dumps(texto)};

            function fallbackCopy(value) {{
                const textarea = document.createElement("textarea");
                textarea.value = value;
                textarea.setAttribute("readonly", "");
                textarea.style.position = "fixed";
                textarea.style.left = "-9999px";
                textarea.style.top = "0";
                document.body.appendChild(textarea);
                textarea.focus();
                textarea.select();

                try {{
                    const copied = document.execCommand("copy");
                    document.body.removeChild(textarea);
                    return copied;
                }} catch (error) {{
                    document.body.removeChild(textarea);
                    return false;
                }}
            }}

            button.addEventListener("click", async () => {{
                try {{
                    if (navigator.clipboard && window.isSecureContext) {{
                        await navigator.clipboard.writeText(text);
                    }} else if (!fallbackCopy(text)) {{
                        throw new Error("fallback copy failed");
                    }}
                    status.textContent = "Copiado";
                    setTimeout(() => status.textContent = "", 1800);
                }} catch (error) {{
                    if (fallbackCopy(text)) {{
                        status.textContent = "Copiado";
                        setTimeout(() => status.textContent = "", 1800);
                    }} else {{
                        status.textContent = "Não foi possível copiar";
                    }}
                }}
            }});
        </script>
        </body>
        </html>
        """,
        height=34,
        scrolling=False
    )


def texto_dataframe_para_copia(df):

    if df.empty:

        return ""

    return formatar_dataframe_para_copia(df).to_csv(
        sep="\t",
        index=False
    )


def colunas_site_dataframe(df):

    candidatos = [
        "Site",
        "Site SNMPc",
        "SNMPc",
        "Site Responsável",
        "Site Vinculado",
        "Site Equipamento",
        "Site Pai",
        "Site Filho"
    ]

    return [
        coluna
        for coluna in candidatos
        if coluna in df.columns
    ]


def primeira_linha_selecionada(resposta_grid):

    selecionadas = resposta_grid.get("selected_rows")

    if selecionadas is None:

        return None

    if hasattr(selecionadas, "empty"):

        if selecionadas.empty:

            return None

        return selecionadas.iloc[0].to_dict()

    if isinstance(selecionadas, list) and selecionadas:

        return selecionadas[0]

    return None


def selecionar_colunas_dataframe(df, key=None):

    colunas_disponiveis = list(df.columns)
    frame_chamador = inspect.currentframe().f_back
    if (
        frame_chamador
        and frame_chamador.f_code.co_name in {
            "mostrar_grid",
            "mostrar_dataframe_nativo"
        }
        and frame_chamador.f_back
    ):

        frame_chamador = frame_chamador.f_back

    origem_funcao = frame_chamador.f_code.co_name if frame_chamador else "grid"
    origem_linha = frame_chamador.f_lineno if frame_chamador else 0
    chave_colunas = (
        f"{key}_colunas"
        if key
        else "grid_colunas_"
        f"{origem_funcao}_"
        f"{origem_linha}_"
        f"{hashlib.md5('|'.join(colunas_disponiveis).encode('utf-8')).hexdigest()}"
    )
    chave_widget = chave_colunas
    preferencia_colunas = load_user_preference(
        chave_colunas,
        colunas_disponiveis
    )
    preferencia_colunas = [
        coluna
        for coluna in preferencia_colunas
        if coluna in colunas_disponiveis
    ] or colunas_disponiveis

    with st.expander("Colunas exibidas", expanded=False):

        colunas_controle, acao_controle = st.columns(
            [5, 1]
        )

        with acao_controle:

            if st.button(
                "Restaurar",
                key=f"{chave_widget}_restaurar",
                help="Exibir todas as colunas desta tabela."
            ):
                st.session_state[chave_widget] = colunas_disponiveis
                save_user_preference(
                    chave_colunas,
                    colunas_disponiveis
                )
                st.rerun()

        with colunas_controle:

            st.caption(
                f"{len(preferencia_colunas)} de {len(colunas_disponiveis)} colunas selecionadas."
            )

        colunas_selecionadas = st.multiselect(
            "Selecionar colunas",
            colunas_disponiveis,
            default=st.session_state.get(
                chave_widget,
                preferencia_colunas
            ),
            key=chave_widget,
            format_func=lambda coluna: COLUNAS_EXIBICAO_PT_BR.get(
                coluna,
                coluna
            )
        )

    if not colunas_selecionadas:

        st.info("Selecione ao menos uma coluna para exibir a tabela.")

        return None

    save_user_preference(
        chave_colunas,
        colunas_selecionadas
    )

    return df[colunas_selecionadas]


def chave_renderizacao_tabela(chave_base, colunas):

    assinatura_colunas = hashlib.md5(
        "|".join(
            str(coluna)
            for coluna in colunas
        ).encode("utf-8")
    ).hexdigest()[:10]

    return f"{chave_base}_render_{assinatura_colunas}"


def mostrar_grid(df, height=400, botoes_copia=None, key=None):

    frame_chamador = inspect.currentframe().f_back
    chave_grid_base = (
        key
        if key
        else (
            "grid_"
            f"{frame_chamador.f_code.co_name if frame_chamador else 'anonimo'}_"
            f"{frame_chamador.f_lineno if frame_chamador else 0}"
        )
    )

    df = preparar_dataframe_exibicao(df)
    df = selecionar_colunas_dataframe(
        df,
        key=key
    )

    if df is None:

        return

    df_exibicao = dataframe_para_exibicao_pt_br(df)
    botoes = []

    texto_tabela = texto_dataframe_para_copia(df_exibicao)

    if texto_tabela and usuario_pode_copiar_tabelas():

        botoes.append(
            (
                "Copiar tabela",
                texto_tabela
            )
        )

    if botoes_copia and usuario_pode_copiar_tabelas():

        botoes.extend(botoes_copia)

    grid_options = GridOptionsBuilder.from_dataframe(df_exibicao)

    grid_options.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True
    )

    if len(df_exibicao) > 100:

        grid_options.configure_pagination(
            enabled=True,
            paginationAutoPageSize=False,
            paginationPageSize=50
        )

    formatador_moeda = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || isNaN(params.value)) {
                return "";
            }
            return new Intl.NumberFormat(
                "pt-BR",
                { style: "currency", currency: "BRL" }
            ).format(params.value);
        }
        """
    )
    formatador_percentual = JsCode(
        """
        function(params) {
            if (params.value === null || params.value === undefined || isNaN(params.value)) {
                return "";
            }
            return new Intl.NumberFormat(
                "pt-BR",
                { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }
            ).format(params.value);
        }
        """
    )

    for coluna in df_exibicao.columns:

        if eh_coluna_monetaria(coluna):

            grid_options.configure_column(
                coluna,
                type=["numericColumn"],
                valueFormatter=formatador_moeda
            )

        elif eh_coluna_percentual(coluna):

            grid_options.configure_column(
                coluna,
                type=["numericColumn"],
                valueFormatter=formatador_percentual
            )

    colunas_site = colunas_site_dataframe(
        df_exibicao
    )

    if colunas_site:

        grid_options.configure_selection(
            selection_mode="single",
            use_checkbox=True
        )

    chave_renderizacao = chave_renderizacao_tabela(
        chave_grid_base,
        df_exibicao.columns
    )

    resposta_grid = AgGrid(
        df_exibicao,
        gridOptions=grid_options.build(),
        height=height,
        allow_unsafe_jscode=True,
        update_mode=(
            GridUpdateMode.SELECTION_CHANGED
            if colunas_site
            else GridUpdateMode.NO_UPDATE
        ),
        key=chave_renderizacao
    )

    if colunas_site:

        linha = primeira_linha_selecionada(
            resposta_grid
        )
        site = ""

        if linha:

            for coluna in colunas_site:

                site = str(
                    linha.get(coluna) or ""
                ).strip()

                if site:

                    break

        if st.button(
            "Abrir site selecionado",
            disabled=not bool(site),
            key=f"{chave_grid_base}_abrir_site_gerenciamento"
        ):

            st.session_state["abrir_site_gerenciamento"] = site
            st.session_state["proxima_aba_principal"] = "gerenciar_sites"
            st.rerun()

    if botoes:

        colunas = st.columns(
            [1] + [0.18 for _botao in botoes]
        )

        for coluna, (rotulo, texto) in zip(colunas[1:], botoes):

            with coluna:

                mostrar_botao_copiar_texto(
                    texto,
                    rotulo=rotulo,
                    discreto=True
                )


def mostrar_dataframe_nativo(df, height=400, key=None):

    df = preparar_dataframe_exibicao(df)
    df = selecionar_colunas_dataframe(
        df,
        key=key
    )

    if df is None:

        return

    df_exibicao = dataframe_para_exibicao_pt_br(df)

    chave_base = (
        key
        if key
        else "dataframe_nativo"
    )
    chave_renderizacao = chave_renderizacao_tabela(
        chave_base,
        df_exibicao.columns
    )

    st.dataframe(
        df_exibicao,
        height=height,
        use_container_width=True,
        hide_index=True,
        key=chave_renderizacao
    )
