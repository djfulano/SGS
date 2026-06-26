import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../.."
        )
    )
)

import pandas as pd
import streamlit as st

from app.config import CLIENTES_FILE
from app.config import IMPORTS_DIR
from app.config import PREFERENCES_FILE
from app.storage import read_json
from app.storage import write_json_atomic

from app.auth import (
    MODULES,
    can_copy_tables,
    can_manage_users,
    can_view_cost_values,
    can_view_top_summary,
    can_view_values,
    has_permission,
)
from app.data_history import (
    ensure_history_initialized,
    load_history
)
from app.importers.txt_importer import importar_estrutura
from app.importers.excel_importer import importar_clientes
from app.importers.excel_importer import ler_clientes_base
from app.importers.topos_importer import SITES_FILE
from app.importers.topos_importer import carregar_topos
from app.importers.topos_importer import chave_site as chave_cadastro_site
from app.importers.topos_importer import caminho_sites_excel
from app.importers.topos_importer import indices_topos
from app.importers.topos_importer import localizar_topo_site
from app.logs import registrar_log_sistema
from app.reports.site_financials import montar_detalhes_topos as montar_detalhes_topos_relatorio
from app.services.backup_service import inspecionar_backup
from app.services.backup_service import restaurar_backup
from app.ui.branding import favicon_sgs
from app.ui.branding import bloco_identidade_sgs
from app.ui.components.tables import configurar_componentes_tabela
from app.ui.components.tables import mostrar_botao_copiar_texto
from app.ui.components.tables import mostrar_dataframe_nativo
from app.ui.components.tables import mostrar_grid
from app.ui.navigation import mostrar_subnavegacao
from app.ui.session import preparar_sessao_usuario
from app.ui.session import usuario_logado
from app.ui.theme import aplicar_tema_visual
from app.ui.views.analysis import configurar_analises
from app.ui.views.analysis import (
    mostrar_clientes_snmpc_cancelados as mostrar_clientes_snmpc_cancelados_pagina
)
from app.ui.views.analysis import (
    mostrar_analises_conciliacao as mostrar_analises_conciliacao_pagina
)
from app.ui.views.analysis import (
    mostrar_sites_sem_clientes_base as mostrar_sites_sem_clientes_base_pagina
)
from app.ui.views.analysis import (
    pode_ver_relatorio_unificado as pode_ver_relatorio_unificado_pagina
)
from app.ui.views.clients import configurar_clientes
from app.ui.views.clients import mostrar_clientes
from app.ui.views.insights import configurar_insights
from app.ui.views.insights import mostrar_insights
from app.ui.views.site_management import (
    configurar_gerenciamento_sites,
    mostrar_gerenciamento_sites_unificado as mostrar_gerenciamento_sites_unificado_pagina
)
from app.ui.views.system import mostrar_sistema as mostrar_sistema_pagina
from app.ui.views.map import mostrar_mapa_clientes
from app.ui.views.products import configurar_produtos
from app.ui.views.products import mostrar_produtos_equipamentos
from app.ui.views.support import configurar_suporte
from app.ui.views.support import mostrar_suporte
from app.ui.views.topology import configurar_topologia
from app.ui.views.topology import montar_resumo_sites
from app.ui.views.topology import mostrar_metricas
from app.ui.views.topology import mostrar_sites_receitas
from app.ui.views.tools import configurar_ferramentas
from app.ui.views.tools import mostrar_ferramentas as mostrar_ferramentas_pagina
from app.services.data_loader import carregar_dados_dashboard
from app.services.data_loader import sistema_precisa_inicializacao
from app.services.data_loader import status_inicializacao_dados
from app.services.data_loader import versao_cache_dados
from app.services.database_service import sincronizar_banco
from app.services.site_metrics import clientes_indiretos_site as clientes_indiretos_site_metricas
from app.services.site_metrics import clientes_totais_site as clientes_totais_site_metricas
from app.services.site_metrics import receita_indireta_site as receita_indireta_site_metricas
from app.services.site_metrics import receita_site as receita_site_metricas
from app.services.site_metrics import receita_total_site as receita_total_site_metricas
from app.services.site_metrics import sites_descendentes as sites_descendentes_metricas


st.set_page_config(
    page_title="SGS",
    page_icon=favicon_sgs(),
    layout="wide",
    initial_sidebar_state="collapsed"
)

ROTULOS_MODULOS = dict(MODULES)


GRID_KEY_COUNTS = {}


aplicar_tema_visual()


def load_preferences():
    return read_json(
        PREFERENCES_FILE,
        {}
    )


def save_preferences(preferences):
    write_json_atomic(
        PREFERENCES_FILE,
        preferences
    )


def salvar_upload_primeira_execucao(upload, destino):
    destino.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(destino, "wb") as arquivo:
        arquivo.write(
            upload.getbuffer()
        )


def validar_importacao_inicial(snmpc_path, sites_path, clientes_path):
    sites_novos, assinaturas_novas, _equipamentos_novos = importar_estrutura(
        snmpc_path
    )
    carregar_topos(
        sites_path
    )
    importar_clientes(
        clientes_path,
        assinaturas_novas
    )
    ler_clientes_base(
        clientes_path
    )

    return sites_novos


def mostrar_primeira_execucao():
    st.markdown(
        bloco_identidade_sgs("sgs-primeira-execucao"),
        unsafe_allow_html=True
    )
    st.header("Primeira execução")
    st.warning(
        "Os arquivos obrigatórios do SGS ainda não foram encontrados. "
        "Restaure um backup completo ou faça a importação inicial para liberar o sistema."
    )

    status = pd.DataFrame(
        status_inicializacao_dados()
    )
    st.markdown("**Arquivos obrigatórios**")
    st.dataframe(
        status[
            [
                "nome",
                "caminho",
                "status"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    aba_restaurar, aba_importar = st.tabs([
        "Restaurar backup",
        "Importação inicial"
    ])

    with aba_restaurar:
        st.caption(
            "Use esta opção para migrar ou recuperar um ambiente completo a partir de um ZIP de backup do SGS."
        )
        backup_upload = st.file_uploader(
            "Backup ZIP",
            type=["zip"],
            key="primeira_execucao_backup"
        )
        restaurar_contracts = st.checkbox(
            "Restaurar documentos dos sites",
            value=False,
            key="primeira_execucao_contracts"
        )
        incluir_cache = st.checkbox(
            "Restaurar cache",
            value=True,
            key="primeira_execucao_cache"
        )

        caminho_backup = None
        info_backup = None

        if backup_upload:
            temp_backup = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".zip"
            )
            temp_backup.write(
                backup_upload.getbuffer()
            )
            temp_backup.close()
            caminho_backup = temp_backup.name

            try:
                info_backup = inspecionar_backup(
                    caminho_backup
                )
                st.markdown("**Conteúdo do backup**")
                st.dataframe(
                    pd.DataFrame(info_backup.get("fontes", [])),
                    use_container_width=True,
                    hide_index=True
                )

                if info_backup.get("entradas_invalidas"):
                    st.error(
                        "Este backup contém caminhos inseguros e não pode ser restaurado."
                    )
                elif not info_backup.get("restauravel"):
                    st.error(
                        "Este ZIP não contém dados restauráveis do SGS."
                    )
            except Exception as erro:
                st.error(f"Falha ao ler backup: {erro}")

        if st.button(
            "Restaurar backup e liberar sistema",
            type="primary",
            disabled=not (caminho_backup and info_backup and info_backup.get("restauravel")),
            key="primeira_execucao_restaurar"
        ):
            try:
                resultado = restaurar_backup(
                    caminho_backup,
                    usuario="primeira_execucao",
                    restaurar_contracts=restaurar_contracts,
                    incluir_cache=incluir_cache
                )
                registrar_log_sistema(
                    "primeira_execucao_restore",
                    status="sucesso",
                    detalhes=resultado
                )
                st.success(
                    "Backup restaurado. Recarregue a página para continuar."
                )
                st.stop()
            except Exception as erro:
                registrar_log_sistema(
                    "primeira_execucao_restore",
                    status="erro",
                    detalhes={
                        "erro": str(erro)
                    }
                )
                st.error(f"Falha ao restaurar backup: {erro}")

    with aba_importar:
        st.caption(
            "A importação inicial exige os três arquivos para montar a primeira base do SGS."
        )
        snmpc_upload = st.file_uploader(
            "SNMPc TXT",
            type=["txt"],
            key="primeira_execucao_snmpc"
        )
        sites_upload = st.file_uploader(
            "Sites Excel",
            type=["xlsx", "xls"],
            key="primeira_execucao_sites"
        )
        clientes_upload = st.file_uploader(
            "Clientes Excel",
            type=["xlsx", "xls"],
            key="primeira_execucao_clientes"
        )

        if st.button(
            "Validar e importar base inicial",
            type="primary",
            key="primeira_execucao_importar"
        ):
            if not all([
                snmpc_upload,
                sites_upload,
                clientes_upload
            ]):
                st.error(
                    "Envie SNMPc TXT, Sites Excel e Clientes Excel para concluir a importação inicial."
                )
                st.stop()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                snmpc_temp = temp_dir / "SNMPc.txt"
                sites_temp = temp_dir / "Sites.xlsx"
                clientes_temp = temp_dir / "clientes.xlsx"
                salvar_upload_primeira_execucao(
                    snmpc_upload,
                    snmpc_temp
                )
                salvar_upload_primeira_execucao(
                    sites_upload,
                    sites_temp
                )
                salvar_upload_primeira_execucao(
                    clientes_upload,
                    clientes_temp
                )

                try:
                    sites_novos = validar_importacao_inicial(
                        snmpc_temp,
                        sites_temp,
                        clientes_temp
                    )
                    salvar_upload_primeira_execucao(
                        snmpc_upload,
                        IMPORTS_DIR / "SNMPc.txt"
                    )
                    salvar_upload_primeira_execucao(
                        sites_upload,
                        IMPORTS_DIR / "Sites.xlsx"
                    )
                    salvar_upload_primeira_execucao(
                        clientes_upload,
                        CLIENTES_FILE
                    )
                    sincronizar_banco(
                        sites_novos
                    )
                    registrar_log_sistema(
                        "primeira_execucao_importacao",
                        status="sucesso",
                        detalhes={
                            "sites": len(sites_novos)
                        }
                    )
                    st.success(
                        "Importação inicial concluída. Recarregue a página para continuar."
                    )
                    st.stop()
                except Exception as erro:
                    registrar_log_sistema(
                        "primeira_execucao_importacao",
                        status="erro",
                        detalhes={
                            "erro": str(erro)
                        }
                    )
                    st.error(f"Falha ao validar importação inicial: {erro}")


def preference_user_key():

    usuario = usuario_logado() or {}

    return usuario.get("username") or "_anonimo"


def load_user_preference(chave, default=None):

    preferences = load_preferences()

    return preferences.get(
        preference_user_key(),
        {}
    ).get(
        chave,
        default
    )


def save_user_preference(chave, valor):

    preferences = load_preferences()
    usuario = preference_user_key()
    preferences.setdefault(
        usuario,
        {}
    )[chave] = valor
    save_preferences(preferences)


def usuario_pode_ver_valores():

    return can_view_values(
        usuario_logado()
    )


def usuario_pode_ver_custos():

    return can_view_cost_values(
        usuario_logado()
    )


def usuario_pode_copiar_tabelas():

    return can_copy_tables(
        usuario_logado()
    )


if sistema_precisa_inicializacao():
    mostrar_primeira_execucao()
    st.stop()


preparar_sessao_usuario()


@st.cache_resource(show_spinner=True)
def carregar_dados(versao_cache):

    try:
        dados = carregar_dados_dashboard()

    except Exception as erro:

        registrar_log_sistema(
            "carregar_dados",
            usuario=(
                usuario_logado() or {}
            ).get("username"),
            status="erro",
            detalhes={
                "versao_cache": str(versao_cache),
                "erro": str(erro)
            }
        )
        raise

    totais = dados["totais"]
    registrar_log_sistema(
        "carregar_dados",
        usuario=(
            usuario_logado() or {}
        ).get("username"),
        status="sucesso",
        detalhes={
            "versao_cache": str(versao_cache),
            **totais
        }
    )

    return (
        dados["sites"],
        dados["clientes_sem_site"],
        dados["clientes_cancelados"],
        dados["clientes_snmpc_cancelados"],
        dados["equipamentos"],
        dados.get("enlaces_sites", [])
    )


def carregar_dados_de_arquivos(estrutura_path, clientes_path):

    sites_novos, assinaturas_novas, equipamentos_novos = importar_estrutura(
        estrutura_path
    )

    importar_clientes(
        clientes_path,
        assinaturas_novas
    )

    return sites_novos, assinaturas_novas, equipamentos_novos


def receita_site(site):

    return receita_site_metricas(site)


def formatar_moeda(valor):

    if (
        not usuario_pode_ver_valores()
        and not usuario_pode_ver_custos()
    ):

        return "Restrito"

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return valor

    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def clientes_indiretos_site(site):

    return clientes_indiretos_site_metricas(site)


def clientes_totais_site(site):

    return clientes_totais_site_metricas(site)


def receita_indireta_site(site):

    return receita_indireta_site_metricas(site)


def receita_total_site(site):

    return receita_total_site_metricas(site)


def sites_descendentes(site):

    return sites_descendentes_metricas(site)


def montar_detalhes_topos(sites):

    return montar_detalhes_topos_relatorio(sites)


def detalhes_topos_cacheados(sites):

    chave_cache = versao_cache_dados()
    estado = st.session_state.get("detalhes_topos_cache")

    if (
        estado
        and estado.get("chave") == chave_cache
    ):

        return estado["dados"].copy()

    df_detalhes = montar_detalhes_topos(sites)
    st.session_state["detalhes_topos_cache"] = {
        "chave": chave_cache,
        "dados": df_detalhes.copy()
    }

    return df_detalhes


def mostrar_detalhes_financeiros_sites(sites):

    st.header("Detalhes financeiros")

    df_detalhes = detalhes_topos_cacheados(sites)

    if df_detalhes.empty:

        st.info("A planilha imports/Sites.xlsx não possui registros válidos.")

        return

    tipos = sorted(
        valor
        for valor in df_detalhes["Tipo"].dropna().unique()
        if str(valor).strip()
    )
    status = sorted(
        valor
        for valor in df_detalhes["Status Cadastro"].dropna().unique()
        if str(valor).strip()
    )
    status_ativos = [
        valor
        for valor in status
        if str(valor).strip().lower() == "ativo"
    ]

    col_sites, col1, col2, col3 = st.columns(
        [2, 1, 1, 1]
    )

    with col_sites:

        opcoes_sites = sorted(
            str(valor).strip()
            for valor in df_detalhes["Site SNMPc"].dropna().unique()
            if str(valor).strip()
        )
        sites_ja_selecionados = st.session_state.get(
            "detalhes_financeiros_sites",
            []
        )
        opcoes_sites = sorted(
            set(opcoes_sites) | set(sites_ja_selecionados)
        )
        sites_selecionados = st.multiselect(
            "Sites",
            opcoes_sites,
            key="detalhes_financeiros_sites"
        )
        incluir_filhos = st.checkbox(
            "Incluir sites filhos",
            value=True,
            key="detalhes_financeiros_incluir_filhos"
        )

    with col1:

        tipos_selecionados = st.multiselect(
            "Tipos",
            tipos,
            default=tipos
        )

    with col2:

        status_selecionados = st.multiselect(
            "Status",
            status,
            default=status_ativos or status,
            key="detalhes_financeiros_status"
        )

    with col3:

        somente_estrutura = st.checkbox(
            "Somente sites no SNMPc",
            value=False
        )

    df_filtrado = df_detalhes.copy()

    if tipos_selecionados:

        df_filtrado = df_filtrado[
            df_filtrado["Tipo"].isin(tipos_selecionados)
        ]

    if status_selecionados:

        df_filtrado = df_filtrado[
            df_filtrado["Status Cadastro"].isin(status_selecionados)
        ]

    if somente_estrutura:

        df_filtrado = df_filtrado[
            df_filtrado["No SNMPc"] == "Sim"
        ]

    if sites_selecionados:
        sites_consulta = set(sites_selecionados)

        if incluir_filhos:

            for nome_site in sites_selecionados:

                site = sites.get(nome_site)

                if not site:

                    continue

                sites_consulta.update(
                    site_filho.nome
                    for site_filho in sites_descendentes(site)
                )

        df_filtrado = df_filtrado[
            df_filtrado["Site SNMPc"].isin(sites_consulta)
        ]

    col1, col2, col3, col4, col5 = st.columns(5)

    receita_total = df_filtrado["Receita Total"].sum()
    custo_total = df_filtrado["Custo"].sum()
    resultado_total = df_filtrado["Resultado"].sum()
    margem_total = (
        resultado_total / receita_total
        if receita_total
        else 0
    )

    col1.metric("Sites", len(df_filtrado))
    col2.metric("Receita Total", formatar_moeda(receita_total))
    col3.metric("Custo Total", formatar_moeda(custo_total))
    col4.metric("Resultado", formatar_moeda(resultado_total))
    col5.metric("Margem", f"{margem_total:.1%}")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Sites negativos",
        int((df_filtrado["Resultado"] < 0).sum())
    )
    col2.metric(
        "Sites sem custo",
        int((df_filtrado["Custo"] <= 0).sum())
    )
    col3.metric(
        "Sites fora do SNMPc",
        int((df_filtrado["No SNMPc"] == "Nao").sum())
    )

    colunas_financeiras = [
        "Site SNMPc",
        "No SNMPc",
        "Codigo",
        "Microsiga",
        "Codigo Condominio",
        "Abreviacao",
        "SNMPc",
        "Tipo",
        "Nome Cadastro",
        "Status Cadastro",
        "Relacionamento",
        "Favorecido",
        "Custo",
        "Receita Direta",
        "Receita Indireta",
        "Receita Com Filhos",
        "Receita Total",
        "Resultado",
        "Margem %",
        "Clientes Diretos",
        "Clientes Indiretos",
        "Clientes Total"
    ]

    mostrar_grid(
        df_filtrado[colunas_financeiras].sort_values(
            by=[
                "Tipo",
                "Resultado",
                "Site SNMPc",
                "SNMPc"
            ],
            ascending=[
                True,
                True,
                True,
                True
            ]
        ),
        height=620,
        key="detalhes_sites_topos"
    )


def valor_exibicao_site(valor):

    if pd.isna(valor):

        return ""

    if isinstance(valor, float) and valor.is_integer():

        return str(int(valor))

    return str(valor)


def rotulo_site_gerenciamento(linha):

    nome_snmpc = (
        valor_exibicao_site(linha.get("Site SNMPc"))
        or valor_exibicao_site(linha.get("SNMPc"))
    )
    codigo = valor_exibicao_site(
        linha.get("Codigo")
    )
    nome = valor_exibicao_site(
        linha.get("Nome Cadastro")
    )
    microsiga = valor_exibicao_site(
        linha.get("Microsiga")
    )

    return (
        f"{nome_snmpc or '-'} - {codigo or '-'} / "
        f"{nome or '-'} - {microsiga or '-'}"
    )


def rotulos_sites_por_nome(sites):

    df_detalhes = detalhes_topos_cacheados(
        sites
    )

    if df_detalhes.empty:

        return {
            nome: nome
            for nome in sites.keys()
        }

    rotulos = {}

    for _, linha in df_detalhes.iterrows():

        nome_site = valor_exibicao_site(
            linha.get("Site SNMPc")
        )

        if nome_site:

            rotulos[nome_site] = rotulo_site_gerenciamento(
                linha
            )

    for nome in sites.keys():

        rotulos.setdefault(
            nome,
            nome
        )

    return rotulos


def formatador_site(rotulos):

    return lambda nome: rotulos.get(
        nome,
        nome
    )


configurar_componentes_tabela(
    usuario_pode_ver_valores,
    formatar_moeda,
    load_user_preference,
    save_user_preference,
    usuario_pode_ver_custos,
    usuario_pode_copiar_tabelas
)

configurar_topologia(
    mostrar_grid,
    mostrar_dataframe_nativo,
    mostrar_botao_copiar_texto,
    formatar_moeda
)

configurar_gerenciamento_sites(
    mostrar_grid,
    formatar_moeda,
    usuario_logado,
    carregar_dados
)

configurar_analises(
    usuario_logado,
    mostrar_grid,
    formatar_moeda,
    detalhes_topos_cacheados
)

configurar_produtos(
    mostrar_grid,
    formatar_moeda,
    lambda chave: has_permission(
        usuario_logado(),
        chave
    )
)

configurar_clientes(
    mostrar_grid,
    formatar_moeda,
    usuario_logado
)

configurar_insights(
    mostrar_grid,
    formatar_moeda,
    usuario_logado
)

configurar_ferramentas(
    usuario_logado,
    mostrar_grid,
    rotulos_sites_por_nome,
    formatador_site
)

configurar_suporte(
    usuario_logado,
    mostrar_grid
)


def seletor_site_gerenciamento(df_detalhes):

    parametro = "gerenciamento_site_idx"
    selecionado = st.query_params.get(
        parametro
    )

    try:

        selecionado = int(selecionado) if selecionado not in (None, "") else None

    except (TypeError, ValueError):

        selecionado = None

    if selecionado not in set(df_detalhes.index):

        selecionado = None

    opcoes = [
        {
            "index": int(indice),
            "label": str(linha["Busca"])
        }
        for indice, linha in df_detalhes.sort_values(
            by=[
                "Tipo",
                "Busca"
            ]
        ).iterrows()
    ]
    valor_inicial = (
        str(df_detalhes.loc[selecionado, "Busca"])
        if selecionado is not None
        else ""
    )

    st.html(
        f"""
        <div style="font-family: sans-serif; width: 100%;">
            <label
                for="site-search"
                style="display:block; font-size:14px; margin-bottom:6px; color:#31333f;"
            >
                Site
            </label>
            <input
                id="site-search"
                autocomplete="off"
                placeholder="Digite para pesquisar e selecione um site"
                value={json.dumps(valor_inicial)}
                style="
                    width: 100%;
                    box-sizing: border-box;
                    border: 1px solid var(--site-border);
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 14px;
                    color: var(--site-text);
                    background: var(--site-bg);
                "
            />
            <div
                id="site-results"
                style="
                    display: none;
                    width: 100%;
                    max-height: 220px;
                    overflow-y: auto;
                    border: 1px solid var(--site-border);
                    border-top: 0;
                    border-radius: 0 0 6px 6px;
                    background: var(--site-bg);
                    box-sizing: border-box;
                    position: relative;
                    z-index: 9999;
                "
            ></div>
        </div>
        <style>
            :root {{
                --site-bg: #ffffff;
                --site-hover: #f6f8fa;
                --site-border: #d0d7de;
                --site-text: #24292f;
                --site-muted: #6e7781;
            }}

            @media (prefers-color-scheme: dark) {{
                :root {{
                    --site-bg: #0e1117;
                    --site-hover: #1f2937;
                    --site-border: #3f4652;
                    --site-text: #fafafa;
                    --site-muted: #a3aab7;
                }}
            }}
        </style>
        <script>
            const options = {json.dumps(opcoes, ensure_ascii=False)};
            const input = document.getElementById("site-search");
            const results = document.getElementById("site-results");
            const paramName = {json.dumps(parametro)};

            function destinationUrl(index) {{
                try {{
                    const url = new URL(window.parent.location.href);
                    url.searchParams.set(paramName, String(index));
                    return url.toString();
                }} catch (error) {{
                    return "?" + encodeURIComponent(paramName) + "=" + encodeURIComponent(String(index));
                }}
            }}

            function render() {{
                const query = input.value.trim().toLowerCase();
                results.innerHTML = "";

                if (!query) {{
                    results.style.display = "none";
                    const url = new URL(window.parent.location.href);
                    if (url.searchParams.has(paramName)) {{
                        url.searchParams.delete(paramName);
                        window.parent.history.replaceState({{}}, "", url.toString());
                    }}
                    return;
                }}

                const matches = options
                    .filter((option) => option.label.toLowerCase().includes(query))
                    .slice(0, 50);

                if (!matches.length) {{
                    const empty = document.createElement("div");
                    empty.textContent = "Nenhum site encontrado";
                    empty.style.padding = "8px 10px";
                    empty.style.color = "var(--site-muted)";
                    empty.style.fontSize = "13px";
                    results.appendChild(empty);
                    results.style.display = "block";
                    return;
                }}

                for (const option of matches) {{
                    const item = document.createElement("a");
                    item.href = destinationUrl(option.index);
                    item.target = "_parent";
                    item.textContent = option.label;
                    item.style.display = "block";
                    item.style.width = "100%";
                    item.style.border = "0";
                    item.style.background = "var(--site-bg)";
                    item.style.color = "var(--site-text)";
                    item.style.textAlign = "left";
                    item.style.padding = "8px 10px";
                    item.style.fontSize = "13px";
                    item.style.cursor = "pointer";
                    item.style.textDecoration = "none";
                    item.onmouseenter = () => item.style.background = "var(--site-hover)";
                    item.onmouseleave = () => item.style.background = "var(--site-bg)";
                    results.appendChild(item);
                }}

                results.style.display = "block";
            }}

            input.addEventListener("input", render);
            input.addEventListener("focus", render);
        </script>
        """,
        unsafe_allow_javascript=True
    )

    return selecionado


def mostrar_gerenciamento_sites_unificado(sites):

    mostrar_gerenciamento_sites_unificado_pagina(
        sites,
        detalhes_topos_cacheados,
        rotulo_site_gerenciamento
    )



def mostrar_tabela_clientes_cancelados(df_cancelados, key):

    busca = st.text_input(
        "Buscar cliente cancelado",
        key=f"busca_{key}"
    )

    if busca:

        filtro = pd.Series(
            False,
            index=df_cancelados.index
        )

        for coluna in df_cancelados.columns:

            filtro = filtro | df_cancelados[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_cancelados = df_cancelados[filtro]

    st.metric(
        "Clientes cancelados",
        len(df_cancelados)
    )

    if "Data Cancelamento" in df_cancelados.columns:

        df_cancelados = df_cancelados.sort_values(
            by="Data Cancelamento",
            ascending=False
        )

    mostrar_grid(
        df_cancelados,
        height=560,
        key=key
    )


def mostrar_clientes_cancelados_historico():

    st.header("Clientes cancelados")

    history = load_history()
    cancelados = list(
        history.get(
            "cancelled_clients",
            {}
        ).values()
    )

    if not cancelados:

        st.success(
            "Nenhum cliente cancelado registrado desde o início do novo controle."
        )

        return

    st.caption(
        "Esta lista compara a base de clientes da importação anterior com a base atual."
    )

    mostrar_tabela_clientes_cancelados(
        pd.DataFrame(cancelados),
        key="grid_clientes_cancelados_reais"
    )


def mostrar_sites_removidos():

    st.header("Sites removidos")

    history = load_history()
    removidos = list(
        history.get(
            "removed_sites",
            {}
        ).values()
    )

    if not removidos:

        st.success(
            "Nenhum site removido registrado no histórico de importações."
        )

        return

    df_sites_removidos = pd.DataFrame([
        {
            "Site": site.get("Site"),
            "Tipo": site.get("Tipo"),
            "Predio": site.get("Predio"),
            "Pai": site.get("Pai"),
            "Data Remocao": site.get("Data Remocao"),
            "Clientes": len(site.get("Clientes", []))
        }
        for site in removidos
    ])

    busca = st.text_input(
        "Buscar site removido"
    )

    if busca:

        filtro = pd.Series(
            False,
            index=df_sites_removidos.index
        )

        for coluna in df_sites_removidos.columns:

            filtro = filtro | df_sites_removidos[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_sites_removidos = df_sites_removidos[filtro]

    st.metric(
        "Sites removidos",
        len(df_sites_removidos)
    )

    mostrar_grid(
        df_sites_removidos.sort_values(
            by="Data Remocao",
            ascending=False
        ),
        height=300
    )

    opcoes = df_sites_removidos["Site"].tolist()

    site_escolhido = st.selectbox(
        "Detalhar clientes do site removido",
        opcoes,
        index=None,
        placeholder="Digite para pesquisar e selecione um site removido"
    )

    if site_escolhido is None:

        return

    site_data = next(
        site
        for site in removidos
        if site.get("Site") == site_escolhido
    )

    clientes = site_data.get(
        "Clientes",
        []
    )

    if not clientes:

        st.info(
            "Este site removido não tinha clientes ativos registrados."
        )

        return

    st.markdown("**Clientes do site removido**")

    mostrar_grid(
        pd.DataFrame(clientes),
        height=420
    )


def pode_ver_relatorio_unificado(chave):

    return pode_ver_relatorio_unificado_pagina(
        chave
    )


def mostrar_analises_conciliacao(
    sites,
    df_sites,
    equipamentos,
    clientes_sem_site,
    clientes_snmpc_cancelados
):

    mostrar_analises_conciliacao_pagina(
        sites,
        df_sites,
        equipamentos,
        clientes_sem_site,
        clientes_snmpc_cancelados,
        mostrar_sites_sem_clientes_base_pagina,
        mostrar_clientes_snmpc_cancelados_pagina
    )


def mostrar_ferramentas(sites, equipamentos, enlaces_sites=None):

    mostrar_ferramentas_pagina(
        sites,
        equipamentos,
        enlaces_sites
    )


def mostrar_sistema():

    mostrar_sistema_pagina(
        usuario_logado(),
        carregar_dados,
        carregar_dados_de_arquivos,
        mostrar_grid,
        ROTULOS_MODULOS,
        sites=sites
    )


def mostrar_historico():

    itens = []

    if (
        has_permission(
            usuario_logado(),
            "sites_removidos"
        )
        or has_permission(
            usuario_logado(),
            "historico"
        )
    ):
        itens.append(
            (
                "sites_removidos",
                "Sites removidos",
                mostrar_sites_removidos
            )
        )

    if (
        has_permission(
            usuario_logado(),
            "clientes_cancelados"
        )
        or has_permission(
            usuario_logado(),
            "historico"
        )
    ):
        itens.append(
            (
                "clientes_cancelados",
                "Clientes cancelados",
                mostrar_clientes_cancelados_historico
            )
        )

    funcao = mostrar_subnavegacao(
        itens,
        key="historico_subaba"
    )

    if funcao:
        funcao()


sites, clientes_sem_site, clientes_cancelados, clientes_snmpc_cancelados, equipamentos, enlaces_sites = carregar_dados(
    versao_cache_dados()
)

ensure_history_initialized(
    sites,
    active_clients_base=ler_clientes_base(CLIENTES_FILE)
)

df_sites = montar_resumo_sites(sites)

if can_view_top_summary(
    usuario_logado()
):
    mostrar_metricas(df_sites)

abas_disponiveis = [
    (
        "sites",
        "Topologia",
        lambda: mostrar_sites_receitas(
            sites,
            df_sites
        )
    ),
    (
        "gerenciar_sites",
        "Gerenciamento de Sites",
        lambda: mostrar_gerenciamento_sites_unificado(sites)
    ),
    (
        "clientes",
        "Clientes",
        lambda: mostrar_clientes(
            sites,
            equipamentos
        )
    ),
    (
        "insights",
        "Insights",
        lambda: mostrar_insights(
            sites,
            equipamentos
        )
    ),
    (
        "analises_conciliacao",
        "Análises e Conciliação",
        lambda: mostrar_analises_conciliacao(
            sites,
            df_sites,
            equipamentos,
            clientes_sem_site,
            clientes_snmpc_cancelados
        )
    ),
    (
        "ferramentas",
        "Equipamentos",
        lambda: mostrar_ferramentas(
            sites,
            equipamentos,
            enlaces_sites
        )
    ),
    (
        "suporte",
        "Suporte",
        lambda: mostrar_suporte(
            sites,
            equipamentos
        )
    ),
    (
        "mapa",
        "Mapa",
        lambda: mostrar_mapa_clientes(
            sites,
            enlaces_sites
        )
    ),
    (
        "produtos",
        "Produtos",
        lambda: mostrar_produtos_equipamentos(
            sites,
            equipamentos
        )
    ),
    (
        "historico",
        "Histórico",
        mostrar_historico
    ),
    (
        "sistema",
        "Sistema",
        mostrar_sistema
    )
]

def permissao_aba(aba):

    chave = aba[0]

    if chave == "usuarios":

        return True

    if has_permission(
        usuario_logado(),
        chave
    ):

        return True

    if chave == "gerenciar_sites":

        return any(
            has_permission(
                usuario_logado(),
                permissao_antiga
            )
            for permissao_antiga in [
                "detalhes_sites",
                "detalhes_contratuais",
                "gerenciar_sites_resumo_financeiro",
                "gerenciar_sites_detalhes",
                "gerenciar_sites_arquivos",
                "gerenciar_sites_contatos",
                "gerenciar_sites_editar"
            ]
        )

    if chave == "ferramentas":

        return any(
            has_permission(
                usuario_logado(),
                permissao_ferramenta
            )
            for permissao_ferramenta in [
                "enlaces",
                "equipamentos_por_site",
                "buscar_equipamentos",
                "base_equipamentos",
                "editar_base_equipamentos"
            ]
        )

    if chave == "suporte":

        return any(
            has_permission(
                usuario_logado(),
                permissao_suporte
            )
            for permissao_suporte in [
                "suporte",
                "suporte_agendamento",
                "retirada",
                "predios"
            ]
        )

    if chave == "produtos":

        return (
            has_permission(
                usuario_logado(),
                "produtos"
            )
            or has_permission(
                usuario_logado(),
                "sva"
            )
            or has_permission(
                usuario_logado(),
                "editar_produtos"
            )
        )

    if chave == "clientes":

        return (
            has_permission(
                usuario_logado(),
                "clientes"
            )
            or any(
                has_permission(
                    usuario_logado(),
                    permissao_clientes
                )
                for permissao_clientes in [
                    "clientes_consulta",
                    "clientes_relatorios",
                    "clientes_insights"
                ]
            )
        )

    if chave == "insights":

        usuario = usuario_logado()

        return (
            can_view_values(usuario)
            and can_view_cost_values(usuario)
            and (
                has_permission(
                    usuario,
                    "insights"
                )
                or any(
                    has_permission(
                        usuario,
                        permissao_insights
                    )
                    for permissao_insights in [
                        "insights_visao_geral",
                        "insights_financeiro",
                        "insights_clientes",
                        "insights_sites",
                        "insights_operacional",
                        "insights_riscos"
                    ]
                )
            )
        )

    if chave == "historico":

        return any(
            has_permission(
                usuario_logado(),
                permissao_historico
            )
            for permissao_historico in [
                "historico",
                "sites_removidos",
                "clientes_cancelados"
            ]
        )

    if chave == "sistema":

        return (
            can_manage_users(
                usuario_logado()
            )
            or any(
                has_permission(
                    usuario_logado(),
                    permissao_sistema
                )
                for permissao_sistema in [
                    "importacao",
                    "importar_dados",
                    "logs",
                    "configuracoes",
                    "editar_configuracoes",
                    "gerenciar_perfis",
                    "usuarios"
                ]
            )
        )

    if chave == "analises_conciliacao":

        return any(
            pode_ver_relatorio_unificado(
                permissao_relatorio
            )
            for permissao_relatorio in [
                "conciliacao_sites",
                "ranking",
                "custos_receita",
                "sites_deficitarios",
                "sites_documentos",
                "sem_vinculo",
                "sites_sem_clientes",
                "clientes_snmpc_cancelados"
            ]
        )

    if chave == "clientes_snmpc_cancelados":

        return has_permission(
            usuario_logado(),
            "clientes_cancelados"
        )

    if chave == "sites_sem_clientes":

        return (
            has_permission(
                usuario_logado(),
                "sem_vinculo"
            )
            or has_permission(
                usuario_logado(),
                "sites"
            )
        )

    return False


abas_permitidas = [
    aba
    for aba in abas_disponiveis
    if permissao_aba(aba)
]

if not abas_permitidas:

    st.warning(
        "Seu usuário não possui permissões de visualização."
    )

    st.stop()

rotulos_abas_permitidas = {
    key: label
    for key, label, _funcao in abas_permitidas
}
funcoes_abas_permitidas = {
    key: funcao
    for key, _label, funcao in abas_permitidas
}
chaves_abas_permitidas = [
    key
    for key, _label, _funcao in abas_permitidas
]

proxima_aba_principal = st.session_state.pop(
    "proxima_aba_principal",
    None
)

if proxima_aba_principal in {
    "sites_removidos",
    "clientes_cancelados"
}:
    st.session_state["historico_subaba"] = proxima_aba_principal
    proxima_aba_principal = "historico"

if proxima_aba_principal == "sva":
    st.session_state["produtos_subaba"] = "sva"
    proxima_aba_principal = "produtos"

if proxima_aba_principal in chaves_abas_permitidas:

    st.session_state["aba_principal"] = proxima_aba_principal

if st.session_state.get("aba_principal") in {
    "sites_removidos",
    "clientes_cancelados"
}:
    st.session_state["historico_subaba"] = st.session_state["aba_principal"]
    st.session_state["aba_principal"] = "historico"

if st.session_state.get("aba_principal") == "sva":
    st.session_state["produtos_subaba"] = "sva"
    st.session_state["aba_principal"] = "produtos"

if st.session_state.get("aba_principal") not in chaves_abas_permitidas:

    st.session_state["aba_principal"] = chaves_abas_permitidas[0]

aba_principal = st.segmented_control(
    "Navegação principal",
    chaves_abas_permitidas,
    selection_mode="single",
    key="aba_principal",
    format_func=lambda chave: rotulos_abas_permitidas.get(
        chave,
        chave
    ),
    label_visibility="collapsed",
    width="stretch"
)

if not aba_principal:

    aba_principal = chaves_abas_permitidas[0]

funcoes_abas_permitidas[aba_principal]()

st.markdown(
    """
    <div class="sgt-footer">
        NEOVIA SOLUTIONS 2026 - Desenvolvido por Fernando Floret
    </div>
    """,
    unsafe_allow_html=True
)
