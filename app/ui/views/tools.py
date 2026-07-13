import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.ui.navigation import mostrar_subnavegacao
from app.services.equipment_catalog import EQUIPMENT_CATALOG_COLUMNS
from app.services.equipment_catalog import equipment_catalog_template_excel
from app.services.equipment_catalog import enrich_equipments_with_catalog
from app.services.equipment_catalog import ensure_catalog_from_equipments
from app.services.equipment_catalog import import_equipment_catalog_excel
from app.services.equipment_catalog import load_equipment_catalog
from app.services.equipment_catalog import save_equipment_catalog
from app.services.site_metrics import sites_descendentes


_usuario_logado = None
_mostrar_grid = None
_rotulos_sites_por_nome = None
_formatador_site = None


def configurar_ferramentas(
    usuario_logado,
    mostrar_grid=None,
    rotulos_sites_por_nome=None,
    formatador_site=None
):
    global _usuario_logado
    global _mostrar_grid
    global _rotulos_sites_por_nome
    global _formatador_site

    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid
    _rotulos_sites_por_nome = rotulos_sites_por_nome
    _formatador_site = formatador_site


def montar_predios_site(site):
    dados = []

    for site_atual in sites_descendentes(site):
        if getattr(site_atual, "predio", None):
            dados.append({
                "Tipo Registro": "Site",
                "Nome": site_atual.nome,
                "Assinatura": "",
                "Predio": site_atual.predio,
                "Site Responsavel": site_atual.nome,
                "Setorial": "",
                "Status Cliente": ""
            })

        assinaturas_ativas = {
            cliente.num_assinatura
            for cliente in site_atual.clientes
        }

        for cliente_estrutura in getattr(
            site_atual,
            "clientes_estrutura",
            []
        ):
            predio = cliente_estrutura.get("predio")

            if not predio:
                continue

            assinatura = cliente_estrutura.get("assinatura")

            dados.append({
                "Tipo Registro": "Cliente",
                "Nome": cliente_estrutura.get("nome"),
                "Assinatura": assinatura,
                "Predio": predio,
                "Site Responsavel": site_atual.nome,
                "Setorial": cliente_estrutura.get("setorial") or "Direto",
                "Status Cliente": (
                    "Ativo"
                    if assinatura in assinaturas_ativas
                    else "Cancelado"
                )
            })

    return pd.DataFrame(dados)


def mostrar_predios(sites):
    st.header("Prédios por site")

    rotulos = _rotulos_sites_por_nome(
        sites
    )
    opcoes_site = sorted(sites.keys())

    site_escolhido = st.selectbox(
        "Site para extrair prédios",
        opcoes_site,
        index=None,
        placeholder="Digite para pesquisar e selecione um site",
        format_func=_formatador_site(rotulos)
    )

    if site_escolhido is None:
        st.info(
            "Escolha um site para listar os prédios vinculados a ele."
        )
        return

    site = sites[site_escolhido]
    df_predios = montar_predios_site(site)

    if df_predios.empty:
        st.warning(
            "Nenhum prédio foi encontrado para este site."
        )
        return

    predios_unicos = df_predios["Predio"].nunique()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Registros",
        len(df_predios)
    )
    col2.metric(
        "Prédios únicos",
        predios_unicos
    )
    col3.metric(
        "Clientes",
        int(
            (df_predios["Tipo Registro"] == "Cliente").sum()
        )
    )

    df_predios = df_predios.sort_values(
        by=[
            "Tipo Registro",
            "Site Responsavel",
            "Setorial",
            "Nome"
        ]
    )

    codigos_predios = ",".join(
        df_predios["Predio"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda coluna: coluna != ""]
        .drop_duplicates()
        .tolist()
    )

    _mostrar_grid(
        df_predios,
        height=560,
        botoes_copia=[
            (
                "Copiar códigos dos prédios",
                codigos_predios
            )
        ]
    )


def montar_equipamentos_site(site, incluir_filhos=True):
    sites_consulta = (
        sites_descendentes(site)
        if incluir_filhos
        else [site]
    )

    dados = []

    for site_atual in sites_consulta:
        for equipamento in getattr(
            site_atual,
            "equipamentos",
            []
        ):
            setorial = equipamento.get("Setorial") or "Direto"
            parent = equipamento.get("Parent") or ""
            nome = equipamento.get("Equipamento") or ""
            icone = equipamento.get("Icone") or ""

            dados.append({
                "Arvore": " > ".join(
                    parte
                    for parte in [
                        site_atual.nome,
                        setorial,
                        icone,
                        parent,
                        nome
                    ]
                    if parte
                ),
                "Site": site_atual.nome,
                "Setorial": setorial,
                "Parent": parent,
                "Equipamento": nome,
                "Endereco": equipamento.get("Endereco") or "",
                "Icone": icone,
                "Status": equipamento.get("Status") or "",
                "Predio": equipamento.get("Predio") or "",
                "Assinatura": equipamento.get("Assinatura") or "",
                "Cliente Estrutura": equipamento.get("Cliente Estrutura") or ""
            })

    return pd.DataFrame(dados)


def montar_quantificador_equipamentos(df_equipamentos):
    if df_equipamentos.empty:
        return pd.DataFrame()

    return (
        df_equipamentos
        .groupby(
            ["Icone"],
            dropna=False
        )
        .size()
        .reset_index(name="Quantidade")
        .sort_values(
            by="Quantidade",
            ascending=False
        )
    )


def assinaturas_ativas_sites(sites):
    assinaturas = set()

    for site in sites.values():
        for cliente in site.clientes:
            assinaturas.add(cliente.num_assinatura)

    return assinaturas


def adicionar_vinculos_atendimento_equipamentos(df_equipamentos, sites):
    if df_equipamentos.empty or "Assinatura" not in df_equipamentos.columns:
        return df_equipamentos

    vinculos_por_assinatura = {}

    for site in (sites or {}).values():
        for cliente in site.clientes:
            assinatura = str(cliente.num_assinatura or "").strip()
            vinculos = getattr(cliente, "vinculos_atendimento", [])
            vinculos_por_assinatura[assinatura] = {
                "Sites Atendimento": ", ".join(
                    getattr(vinculo.get("site"), "nome", "")
                    for vinculo in vinculos
                    if vinculo.get("site") is not None
                ),
                "Setoriais Atendimento": ", ".join(
                    str(vinculo.get("setorial") or "Direto")
                    for vinculo in vinculos
                ),
                "Vínculos Atendimento": ", ".join(
                    str(vinculo.get("tipo") or "Principal")
                    for vinculo in vinculos
                )
            }

    resultado = df_equipamentos.copy()

    for coluna in [
        "Sites Atendimento",
        "Setoriais Atendimento",
        "Vínculos Atendimento"
    ]:
        resultado[coluna] = resultado["Assinatura"].apply(
            lambda assinatura: vinculos_por_assinatura.get(
                str(assinatura or "").strip(),
                {}
            ).get(coluna, "")
        )

    return resultado


def marcar_status_cliente_equipamentos(df_equipamentos, assinaturas_ativas):
    if df_equipamentos.empty or "Assinatura" not in df_equipamentos.columns:
        return df_equipamentos

    df_marcado = df_equipamentos.copy()

    def status_cliente(assinatura):
        assinatura = str(assinatura).strip()

        if not assinatura:
            return "Infraestrutura"

        if assinatura in assinaturas_ativas:
            return "Ativo"

        return "Cancelado"

    df_marcado["Status Cliente"] = df_marcado["Assinatura"].apply(
        status_cliente
    )

    return df_marcado


def mostrar_consulta_equipamentos(sites, equipamentos):
    st.header("Equipamentos por Site")

    assinaturas_ativas = assinaturas_ativas_sites(sites)

    rotulos = _rotulos_sites_por_nome(
        sites
    )
    opcoes_site = [
        "Todos os sites"
    ]
    opcoes_site.extend(
        sorted(sites.keys())
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        site_escolhido = st.selectbox(
            "Site para consultar equipamentos",
            opcoes_site,
            index=None,
            placeholder="Digite para pesquisar e selecione um site",
            format_func=lambda nome: (
                "Todos os sites"
                if nome == "Todos os sites"
                else rotulos.get(nome, nome)
            )
        )

    with col2:
        incluir_filhos = st.checkbox(
            "Incluir sites filhos",
            value=True
        )

    if site_escolhido is None:
        st.info("Pesquise e selecione um site ou escolha Todos os sites.")
        return

    if site_escolhido == "Todos os sites":
        df_equipamentos = pd.DataFrame(equipamentos)

        if not df_equipamentos.empty:
            df_equipamentos = df_equipamentos[[
                "Arvore",
                "Site",
                "Setorial",
                "Parent",
                "Icone",
                "Equipamento",
                "Endereco",
                "Status",
                "Predio",
                "Assinatura",
                "Cliente Estrutura"
            ]]
    else:
        site_base = sites[site_escolhido]
        df_equipamentos = montar_equipamentos_site(
            site_base,
            incluir_filhos=incluir_filhos
        )

    if df_equipamentos.empty:
        st.warning(
            "Nenhum equipamento encontrado para a consulta."
        )
        return

    df_equipamentos = marcar_status_cliente_equipamentos(
        df_equipamentos,
        assinaturas_ativas
    )
    df_equipamentos = enrich_equipments_with_catalog(
        df_equipamentos
    )
    df_equipamentos = adicionar_vinculos_atendimento_equipamentos(
        df_equipamentos,
        sites
    )

    col1, col2 = st.columns(2)

    with col1:
        busca = st.text_input(
            "Buscar equipamento"
        )

    with col2:
        busca_assinatura = st.text_input(
            "Buscar assinatura"
        )

    somente_cancelados = st.checkbox(
        "Mostrar somente equipamentos de clientes cancelados",
        value=False
    )

    icones = sorted(
        valor
        for valor in df_equipamentos["Icone"].dropna().unique()
        if str(valor).strip()
    )

    icones_selecionados = st.multiselect(
        "Filtrar por icone",
        icones,
        default=icones
    )

    if icones_selecionados:
        df_equipamentos = df_equipamentos[
            df_equipamentos["Icone"].isin(icones_selecionados)
        ]

    if somente_cancelados:
        df_equipamentos = df_equipamentos[
            df_equipamentos["Status Cliente"] == "Cancelado"
        ]

    if busca_assinatura:
        df_equipamentos = df_equipamentos[
            df_equipamentos["Assinatura"].astype(str).str.contains(
                busca_assinatura,
                case=False,
                regex=False,
                na=False
            )
        ]

    if busca:
        filtro = pd.Series(
            False,
            index=df_equipamentos.index
        )

        for coluna in df_equipamentos.columns:
            filtro = filtro | df_equipamentos[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_equipamentos = df_equipamentos[filtro]

    if df_equipamentos.empty:
        st.warning(
            "Nenhum equipamento encontrado para os filtros informados."
        )
        return

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Equipamentos",
        len(df_equipamentos)
    )
    col2.metric(
        "Tipos por icone",
        df_equipamentos["Icone"].nunique()
    )
    col3.metric(
        "Sites com equipamentos",
        df_equipamentos["Site"].nunique()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Infraestrutura",
        int(
            (df_equipamentos["Status Cliente"] == "Infraestrutura").sum()
        )
    )
    col2.metric(
        "Clientes ativos",
        int(
            (df_equipamentos["Status Cliente"] == "Ativo").sum()
        )
    )
    col3.metric(
        "Clientes cancelados",
        int(
            (df_equipamentos["Status Cliente"] == "Cancelado").sum()
        )
    )

    df_ranking_equipamentos = montar_quantificador_equipamentos(
        df_equipamentos
    )

    st.markdown("**Ranking de equipamentos mais usados**")

    _mostrar_grid(
        df_ranking_equipamentos,
        height=260
    )

    colunas_preferidas = [
        "Arvore",
        "Site",
        "Setorial",
        "Parent",
        "Icone",
        "Modelo Base",
        "Fabricante Base",
        "Software Base",
        "Tipo Base",
        "Código Base",
        "Valor Base",
        "Equipamento",
        "Endereco",
        "Status",
        "Status Cliente",
        "Predio",
        "Assinatura",
        "Sites Atendimento",
        "Setoriais Atendimento",
        "Vínculos Atendimento",
        "Cliente Estrutura"
    ]

    df_equipamentos = df_equipamentos[
        [
            coluna
            for coluna in colunas_preferidas
            if coluna in df_equipamentos.columns
        ]
    ]

    df_arvore = df_equipamentos.sort_values(
        by=[
            "Site",
            "Setorial",
            "Icone",
            "Parent",
            "Equipamento"
        ]
    ).rename(columns={
        "Icone": "Ícone",
        "Modelo Base": "Modelo",
        "Fabricante Base": "Fabricante",
        "Software Base": "Software",
        "Tipo Base": "Tipo",
        "Código Base": "Código",
        "Valor Base": "Valor"
    })

    st.markdown("**Árvore de equipamentos**")

    _mostrar_grid(
        df_arvore,
        height=560
    )


def montar_equipamentos_enriquecidos(equipamentos, sites=None):
    df_equipamentos = pd.DataFrame(equipamentos)

    if df_equipamentos.empty:
        return pd.DataFrame()

    colunas_base = [
        "Arvore",
        "Site",
        "Setorial",
        "Parent",
        "Icone",
        "Equipamento",
        "Endereco",
        "Status",
        "Predio",
        "Assinatura",
        "Cliente Estrutura"
    ]
    df_equipamentos = df_equipamentos[
        [
            coluna
            for coluna in colunas_base
            if coluna in df_equipamentos.columns
        ]
    ]

    df_equipamentos = enrich_equipments_with_catalog(
        df_equipamentos
    )
    df_equipamentos = adicionar_vinculos_atendimento_equipamentos(
        df_equipamentos,
        sites
    )

    for coluna in [
        "Modelo Base",
        "Fabricante Base",
        "Software Base",
        "Tipo Base",
        "Código Base",
        "Valor Base"
    ]:
        if coluna not in df_equipamentos.columns:
            df_equipamentos[coluna] = ""

    return df_equipamentos


def filtrar_equipamentos_cancelados(df_equipamentos):
    if df_equipamentos.empty or "Status Cliente" not in df_equipamentos.columns:
        return df_equipamentos

    return df_equipamentos[
        df_equipamentos["Status Cliente"] == "Cancelado"
    ].copy()


def normalizar_selecao_filtro(valores, opcoes_validas):
    opcoes_validas = set(
        str(valor)
        for valor in opcoes_validas
    )

    return [
        valor
        for valor in valores or []
        if str(valor) in opcoes_validas
    ]


def aplicar_filtros_equipamentos(df_equipamentos, filtros):
    if df_equipamentos.empty:
        return df_equipamentos

    df_filtrado = df_equipamentos.copy()

    for coluna, valores in (filtros or {}).items():
        valores = [
            str(valor)
            for valor in valores or []
            if str(valor).strip()
        ]

        if not valores or coluna not in df_filtrado.columns:
            continue

        df_filtrado = df_filtrado[
            df_filtrado[coluna].astype(str).isin(valores)
        ]

    return df_filtrado


def opcoes_filtro_equipamentos(df_equipamentos, coluna, filtros_atuais):
    filtros_sem_coluna = {
        chave: valor
        for chave, valor in (filtros_atuais or {}).items()
        if chave != coluna
    }
    df_base = aplicar_filtros_equipamentos(
        df_equipamentos,
        filtros_sem_coluna
    )

    if df_base.empty or coluna not in df_base.columns:
        return []

    return sorted(
        {
            str(valor).strip()
            for valor in df_base[coluna].dropna().unique()
            if str(valor).strip()
        }
    )


def mostrar_busca_equipamentos(sites, equipamentos):
    st.header("Buscar equipamentos")

    df_equipamentos = montar_equipamentos_enriquecidos(
        equipamentos,
        sites
    )

    if df_equipamentos.empty:
        st.warning("Nenhum equipamento encontrado na topologia SNMPc.")
        return

    df_equipamentos = marcar_status_cliente_equipamentos(
        df_equipamentos,
        assinaturas_ativas_sites(sites)
    )

    df_filtrado = df_equipamentos.copy()

    somente_cancelados = st.checkbox(
        "Mostrar somente equipamentos de clientes cancelados",
        value=False,
        key="buscar_equipamentos_somente_cancelados"
    )

    if somente_cancelados:
        df_filtrado = filtrar_equipamentos_cancelados(
            df_filtrado
        )

    filtros_chaves = {
        "Icone": "buscar_equipamentos_icones",
        "Fabricante Base": "buscar_equipamentos_fabricantes",
        "Modelo Base": "buscar_equipamentos_modelos",
        "Tipo Base": "buscar_equipamentos_tipos"
    }
    filtros_atuais = {
        coluna: st.session_state.get(chave, [])
        for coluna, chave in filtros_chaves.items()
    }
    opcoes_por_coluna = {
        coluna: opcoes_filtro_equipamentos(
            df_filtrado,
            coluna,
            filtros_atuais
        )
        for coluna in filtros_chaves
    }

    for coluna, chave in filtros_chaves.items():
        selecao_normalizada = normalizar_selecao_filtro(
            st.session_state.get(chave, []),
            opcoes_por_coluna[coluna]
        )

        if selecao_normalizada != st.session_state.get(chave, []):
            st.session_state[chave] = selecao_normalizada

    col1, col2 = st.columns(2)
    with col1:
        icones_selecionados = st.multiselect(
            "Ícone",
            opcoes_por_coluna["Icone"],
            key="buscar_equipamentos_icones"
        )
    with col2:
        fabricantes_selecionados = st.multiselect(
            "Fabricante",
            opcoes_por_coluna["Fabricante Base"],
            key="buscar_equipamentos_fabricantes"
        )

    col1, col2 = st.columns(2)
    with col1:
        modelos_selecionados = st.multiselect(
            "Modelo",
            opcoes_por_coluna["Modelo Base"],
            key="buscar_equipamentos_modelos"
        )
    with col2:
        tipos_selecionados = st.multiselect(
            "Tipo",
            opcoes_por_coluna["Tipo Base"],
            key="buscar_equipamentos_tipos"
        )

    col_limpar, _col_espaco = st.columns([1, 4])
    with col_limpar:
        if st.button(
            "Limpar filtros",
            key="buscar_equipamentos_limpar"
        ):
            for chave in list(filtros_chaves.values()) + [
                "buscar_equipamentos_somente_cancelados"
            ]:
                st.session_state.pop(chave, None)
            st.rerun()

    df_filtrado = aplicar_filtros_equipamentos(
        df_filtrado,
        {
            "Icone": icones_selecionados,
            "Fabricante Base": fabricantes_selecionados,
            "Modelo Base": modelos_selecionados,
            "Tipo Base": tipos_selecionados
        }
    )

    if df_filtrado.empty:
        st.info("Nenhum equipamento encontrado para os filtros informados.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Equipamentos",
        len(df_filtrado)
    )
    col2.metric(
        "Ícones",
        df_filtrado["Icone"].nunique()
    )
    col3.metric(
        "Sites",
        df_filtrado["Site"].nunique()
        if "Site" in df_filtrado.columns
        else 0
    )

    colunas_resultado = [
        "Icone",
        "Modelo Base",
        "Fabricante Base",
        "Software Base",
        "Tipo Base",
        "Código Base",
        "Valor Base",
        "Equipamento",
        "Site",
        "Setorial",
        "Parent",
        "Status",
        "Status Cliente",
        "Assinatura",
        "Endereco",
        "Predio",
        "Cliente Estrutura",
        "Arvore"
    ]
    df_resultado = df_filtrado[
        [
            coluna
            for coluna in colunas_resultado
            if coluna in df_filtrado.columns
        ]
    ].rename(columns={
        "Icone": "Ícone",
        "Modelo Base": "Modelo",
        "Fabricante Base": "Fabricante",
        "Software Base": "Software",
        "Tipo Base": "Tipo",
        "Código Base": "Código",
        "Valor Base": "Valor"
    })

    _mostrar_grid(
        df_resultado.sort_values(
            by=[
                coluna
                for coluna in [
                    "Ícone",
                    "Modelo",
                    "Site",
                    "Equipamento"
                ]
                if coluna in df_resultado.columns
            ]
        ),
        height=620,
        key="grid_buscar_equipamentos"
    )


def mostrar_base_equipamentos(equipamentos):
    st.header("Editar Equipamentos")

    df_base = ensure_catalog_from_equipments(
        equipamentos
    )

    icones_snmpc = {
        str(equipamento.get("Icone") or "").strip()
        for equipamento in equipamentos
        if str(equipamento.get("Icone") or "").strip()
    }

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Ícones no SNMPc",
        len(icones_snmpc)
    )
    col2.metric(
        "Itens na base",
        len(df_base)
    )
    col3.metric(
        "Sem modelo",
        int(
            df_base["Modelo"].astype(str).str.strip().eq("").sum()
        )
    )

    with st.expander("Importação em massa por Excel"):
        st.download_button(
            "Baixar modelo Excel",
            data=equipment_catalog_template_excel(),
            file_name="base_equipamentos_modelo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="base_equipamentos_modelo"
        )

        arquivo_importacao = st.file_uploader(
            "Importar equipamentos",
            type=[
                "xlsx",
                "xls"
            ],
            key="base_equipamentos_importacao"
        )

        importar = st.button(
            "Importar Excel",
            type="primary",
            disabled=arquivo_importacao is None,
            key="base_equipamentos_importar"
        )

        if importar and arquivo_importacao is not None:
            try:
                df_importado = import_equipment_catalog_excel(
                    arquivo_importacao,
                    df_base
                )
                save_equipment_catalog(
                    df_importado
                )
                st.success(
                    f"Importação concluída. {len(df_importado)} itens na base."
                )
                st.rerun()

            except Exception as erro:
                st.error(f"Falha ao importar a base: {erro}")

    busca = st.text_input(
        "Buscar equipamentos cadastrados",
        key="base_equipamentos_busca"
    )

    df_editor = df_base.copy()

    if busca:
        filtro = pd.Series(
            False,
            index=df_editor.index
        )

        for coluna in df_editor.columns:
            filtro = filtro | df_editor[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_editor = df_editor[filtro]

    df_editado = st.data_editor(
        df_editor,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Ícone": st.column_config.TextColumn(
                "Ícone",
                required=True
            ),
            "Modelo": st.column_config.TextColumn(
                "Modelo"
            ),
            "Fabricante": st.column_config.TextColumn(
                "Fabricante"
            ),
            "Software": st.column_config.TextColumn(
                "Software"
            ),
            "Tipo": st.column_config.TextColumn(
                "Tipo"
            ),
            "Código": st.column_config.TextColumn(
                "Código"
            ),
            "Valor": st.column_config.NumberColumn(
                "Valor",
                min_value=0.0,
                step=0.01,
                format="R$ %.2f"
            )
        },
        key="base_equipamentos_editor"
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        salvar = st.button(
            "Salvar base",
            type="primary",
            key="base_equipamentos_salvar"
        )

    with col2:
        atualizar = st.button(
            "Atualizar ícones do SNMPc",
            key="base_equipamentos_atualizar_icones"
        )

    if salvar:
        df_atual = df_base.copy()

        if busca:
            icones_editados = set(
                df_editado["Ícone"].astype(str).str.strip()
            )
            df_atual = df_atual[
                ~df_atual["Ícone"].astype(str).str.strip().isin(icones_editados)
            ]
            df_atual = pd.concat(
                [
                    df_atual,
                    df_editado
                ],
                ignore_index=True
            )
        else:
            df_atual = df_editado

        save_equipment_catalog(
            df_atual[EQUIPMENT_CATALOG_COLUMNS]
        )
        st.success("Equipamentos salvos.")
        st.rerun()

    if atualizar:
        save_equipment_catalog(
            ensure_catalog_from_equipments(
                equipamentos
            )
        )
        st.success("Ícones do SNMPc atualizados na base.")
        st.rerun()


def montar_equipamentos_retirada(equipamentos, assinatura):
    assinatura = str(assinatura or "").strip()

    if not assinatura:
        return pd.DataFrame()

    df_equipamentos = pd.DataFrame(equipamentos)

    if df_equipamentos.empty or "Assinatura" not in df_equipamentos.columns:
        return pd.DataFrame()

    df_retirada = df_equipamentos[
        df_equipamentos["Assinatura"].astype(str).str.strip() == assinatura
    ].copy()

    if df_retirada.empty:
        return pd.DataFrame()

    colunas_base = [
        "Arvore",
        "Site",
        "Setorial",
        "Parent",
        "Icone",
        "Equipamento",
        "Endereco",
        "Status",
        "Predio",
        "Assinatura",
        "Cliente Estrutura"
    ]
    df_retirada = df_retirada[
        [
            coluna
            for coluna in colunas_base
            if coluna in df_retirada.columns
        ]
    ]
    df_retirada = enrich_equipments_with_catalog(
        df_retirada
    )

    colunas_retirada = [
        "Icone",
        "Modelo Base",
        "Fabricante Base",
        "Software Base",
        "Código Base",
        "Tipo Base",
        "Valor Base",
        "Equipamento",
        "Site",
        "Setorial",
        "Parent",
        "Status",
        "Endereco",
        "Predio",
        "Assinatura",
        "Cliente Estrutura",
        "Arvore"
    ]

    return df_retirada[
        [
            coluna
            for coluna in colunas_retirada
            if coluna in df_retirada.columns
        ]
    ].rename(columns={
        "Icone": "Ícone",
        "Modelo Base": "Modelo",
        "Fabricante Base": "Fabricante",
        "Software Base": "Software",
        "Código Base": "Código",
        "Tipo Base": "Tipo",
        "Valor Base": "Valor"
    })


def mostrar_retirada_equipamentos(equipamentos):
    st.header("Retirada")

    assinatura = st.text_input(
        "Assinatura",
        key="retirada_assinatura"
    )

    if not assinatura:
        st.info("Informe uma assinatura para listar os equipamentos relacionados no SNMPc.")
        return

    df_retirada = montar_equipamentos_retirada(
        equipamentos,
        assinatura
    )

    if df_retirada.empty:
        st.warning(
            "Nenhum equipamento relacionado a esta assinatura foi encontrado no SNMPc."
        )
        return

    valor_total = (
        df_retirada["Valor"].fillna(0).astype(float).sum()
        if "Valor" in df_retirada.columns
        else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Equipamentos",
        len(df_retirada)
    )
    col2.metric(
        "Tipos por ícone",
        df_retirada["Ícone"].nunique()
    )
    col3.metric(
        "Valor total",
        f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    _mostrar_grid(
        df_retirada.sort_values(
            by=[
                "Site",
                "Setorial",
                "Ícone",
                "Equipamento"
            ]
        ),
        height=560,
        key="grid_retirada_equipamentos"
    )


def mostrar_equipamentos(sites, equipamentos):
    mostrar_consulta_equipamentos(
        sites,
        equipamentos
    )


def resumir_lista(valores):
    valores_limpos = [
        str(valor).strip()
        for valor in valores
        if str(valor).strip()
    ]

    unicos = sorted(set(valores_limpos))

    return ", ".join(unicos)


def enriquecer_enlaces_com_base(df_enlaces):
    if df_enlaces.empty:
        return df_enlaces

    df_enriquecido = df_enlaces.copy()
    df_catalogo = load_equipment_catalog().rename(columns={
        "Ícone": "Icone Enlace",
        "Modelo": "Nome Equipamento",
        "Fabricante": "Fabricante Equipamento",
        "Software": "Software Equipamento",
        "Tipo": "Tipo Equipamento",
        "Código": "Código Equipamento",
        "Valor": "Valor Equipamento"
    })

    if not df_catalogo.empty:
        df_enriquecido = df_enriquecido.merge(
            df_catalogo[
                [
                    "Icone Enlace",
                    "Nome Equipamento",
                    "Fabricante Equipamento",
                    "Software Equipamento",
                    "Tipo Equipamento",
                    "Código Equipamento",
                    "Valor Equipamento"
                ]
            ],
            on="Icone Enlace",
            how="left"
        )

    for coluna in [
        "Nome Equipamento",
        "Fabricante Equipamento",
        "Software Equipamento",
        "Tipo Equipamento",
        "Código Equipamento",
        "Valor Equipamento"
    ]:
        if coluna not in df_enriquecido.columns:
            df_enriquecido[coluna] = ""

    return df_enriquecido


@st.cache_data(show_spinner=False)
def montar_enlaces_cliente(df_equipamentos):
    if df_equipamentos.empty:
        return pd.DataFrame()

    dados = []

    grupos = df_equipamentos.groupby(
        [
            "Site",
            "Setorial",
            "Icone"
        ],
        dropna=False
    )

    for (site, setorial, icone), grupo in grupos:
        equipamentos_infra = grupo[
            grupo["Status Cliente"] == "Infraestrutura"
        ]
        equipamentos_cliente = grupo[
            grupo["Status Cliente"].isin([
                "Ativo",
                "Cancelado"
            ])
        ]

        if equipamentos_infra.empty or equipamentos_cliente.empty:
            continue

        for assinatura, grupo_cliente in equipamentos_cliente.groupby(
            "Assinatura",
            dropna=False
        ):
            dados.append({
                "Tipo Enlace": "Site x Cliente",
                "Site Pai": site,
                "Site Filho": "",
                "Setorial": setorial,
                "Assinatura": assinatura,
                "Cliente Estrutura": resumir_lista(
                    grupo_cliente["Cliente Estrutura"]
                ),
                "Status Cliente": resumir_lista(
                    grupo_cliente["Status Cliente"]
                ),
                "Icone Enlace": icone,
                "Equipamentos Infra": len(equipamentos_infra),
                "Icones Infra": resumir_lista(
                    equipamentos_infra["Icone"]
                ),
                "Equipamentos Cliente": len(grupo_cliente),
                "Icones Cliente": resumir_lista(
                    grupo_cliente["Icone"]
                )
            })

    return pd.DataFrame(dados)


def filtrar_enlaces_clientes_cancelados(df_enlaces):
    if df_enlaces.empty:
        return df_enlaces

    if "Tipo Enlace" not in df_enlaces.columns or "Status Cliente" not in df_enlaces.columns:
        return df_enlaces.iloc[0:0].copy()

    return df_enlaces[
        (df_enlaces["Tipo Enlace"] == "Site x Cliente")
        & (df_enlaces["Status Cliente"] == "Cancelado")
    ].copy()


def montar_enlaces_sites(sites_consulta):
    dados = []

    for site in sites_consulta:
        for setorial, sites_filhos in getattr(
            site,
            "sites_por_setorial",
            {}
        ).items():
            equipamentos_pai = pd.DataFrame([
                equipamento
                for equipamento in getattr(site, "equipamentos", [])
                if equipamento.get("Setorial") == setorial
                and not equipamento.get("Assinatura")
            ])

            for site_filho in sites_filhos:
                equipamentos_filho = pd.DataFrame([
                    equipamento
                    for equipamento in getattr(site_filho, "equipamentos", [])
                    if not equipamento.get("Assinatura")
                ])

                if equipamentos_pai.empty or equipamentos_filho.empty:
                    continue

                icones_pai = set(
                    equipamentos_pai["Icone"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                icones_filho = set(
                    equipamentos_filho["Icone"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )

                for icone in sorted(icones_pai & icones_filho):
                    equipamentos_pai_icone = equipamentos_pai[
                        equipamentos_pai["Icone"] == icone
                    ]
                    equipamentos_filho_icone = equipamentos_filho[
                        equipamentos_filho["Icone"] == icone
                    ]

                    dados.append({
                        "Tipo Enlace": "Site Pai x Filho",
                        "Site Pai": site.nome,
                        "Site Filho": site_filho.nome,
                        "Setorial": setorial,
                        "Assinatura": "",
                        "Cliente Estrutura": "",
                        "Status Cliente": "Infraestrutura",
                        "Icone Enlace": icone,
                        "Equipamentos Infra": len(equipamentos_pai_icone),
                        "Icones Infra": resumir_lista(
                            equipamentos_pai_icone["Icone"]
                        ),
                        "Equipamentos Cliente": len(equipamentos_filho_icone),
                        "Icones Cliente": resumir_lista(
                            equipamentos_filho_icone["Icone"]
                        )
                    })

    return pd.DataFrame(dados)


def montar_enlaces_snmpc_sites(enlaces_sites, sites_consulta):
    nomes_consulta = {
        site.nome
        for site in sites_consulta
    }
    dados = []

    for enlace in enlaces_sites or []:
        site_origem = str(enlace.get("Site Origem") or "").strip()
        site_destino = str(enlace.get("Site Destino") or "").strip()

        if site_origem not in nomes_consulta and site_destino not in nomes_consulta:
            continue

        dados.append({
            "Tipo Enlace": enlace.get("Tipo Enlace") or "Site x Site",
            "Origem Dados": f"SNMPc {enlace.get('Origem Dados') or 'Network'}",
            "Site Pai": site_origem,
            "Site Filho": site_destino,
            "Setorial": "SNMPc",
            "Assinatura": "",
            "Cliente Estrutura": "",
            "Status Cliente": "Infraestrutura",
            "Icone Enlace": enlace.get("Icone") or "",
            "Nome Link": enlace.get("Nome Link") or "",
            "Tipo Origem": enlace.get("Tipo Origem") or "",
            "Tipo Destino": enlace.get("Tipo Destino") or "",
            "Origem Endpoint": enlace.get("Origem Endpoint") or "",
            "Destino Endpoint": enlace.get("Destino Endpoint") or "",
            "ID Link": enlace.get("ID Link") or "",
            "Parent SNMPc": enlace.get("Parent SNMPc") or "",
            "Status": enlace.get("Status") or "",
            "Equipamentos Infra": "",
            "Icones Infra": "",
            "Equipamentos Cliente": "",
            "Icones Cliente": ""
        })

    return pd.DataFrame(dados)


def mostrar_enlaces(sites, equipamentos, enlaces_sites=None):
    st.header("Localizador de enlaces")
    enlaces_sites = enlaces_sites or []

    assinaturas_ativas = assinaturas_ativas_sites(sites)

    rotulos = _rotulos_sites_por_nome(
        sites
    )
    opcoes_site = [
        "Todos os sites"
    ]
    opcoes_site.extend(
        sorted(sites.keys())
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        site_escolhido = st.selectbox(
            "Site para localizar enlaces",
            opcoes_site,
            index=None,
            placeholder="Digite para pesquisar e selecione um site",
            format_func=lambda nome: (
                "Todos os sites"
                if nome == "Todos os sites"
                else rotulos.get(nome, nome)
            )
        )

    with col2:
        incluir_filhos = st.checkbox(
            "Incluir sites filhos",
            value=True,
            key="enlaces_incluir_filhos"
        )

    if site_escolhido is None:
        st.info("Pesquise e selecione um site ou escolha Todos os sites.")
        return

    if site_escolhido == "Todos os sites":
        df_equipamentos = pd.DataFrame(equipamentos)
        sites_consulta = list(sites.values())

        if not df_equipamentos.empty:
            df_equipamentos = df_equipamentos[[
                "Arvore",
                "Site",
                "Setorial",
                "Parent",
                "Icone",
                "Equipamento",
                "Endereco",
                "Status",
                "Predio",
                "Assinatura",
                "Cliente Estrutura"
            ]]
    else:
        site_base = sites[site_escolhido]
        sites_consulta = (
            sites_descendentes(site_base)
            if incluir_filhos
            else [site_base]
        )
        df_equipamentos = montar_equipamentos_site(
            site_base,
            incluir_filhos=incluir_filhos
        )

    if df_equipamentos.empty:
        st.warning(
            "Nenhum equipamento encontrado para localizar enlaces."
        )
        return

    df_equipamentos = marcar_status_cliente_equipamentos(
        df_equipamentos,
        assinaturas_ativas
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        busca_assinatura = st.text_input(
            "Buscar assinatura no enlace"
        )

    with col2:
        busca_icone = st.text_input(
            "Buscar ícone no enlace",
            key="enlaces_busca_icone"
        )

    with col3:
        busca_nome = st.text_input(
            "Buscar nome do equipamento",
            key="enlaces_busca_nome"
        )

    with col4:
        busca_tipo = st.text_input(
            "Buscar tipo do equipamento",
            key="enlaces_busca_tipo"
        )

    somente_cancelados = st.checkbox(
        "Somente enlaces de clientes cancelados",
        value=False
    )

    if somente_cancelados:
        df_equipamentos = df_equipamentos[
            (df_equipamentos["Status Cliente"] == "Cancelado")
            | (df_equipamentos["Status Cliente"] == "Infraestrutura")
        ]

    if busca_assinatura:
        df_equipamentos = df_equipamentos[
            (df_equipamentos["Assinatura"].astype(str).str.contains(
                busca_assinatura,
                case=False,
                regex=False,
                na=False
            ))
            | (df_equipamentos["Status Cliente"] == "Infraestrutura")
        ]

    with st.spinner("Carregando enlaces..."):
        df_enlaces = pd.concat(
            [
                montar_enlaces_cliente(df_equipamentos),
                montar_enlaces_sites(sites_consulta),
                montar_enlaces_snmpc_sites(enlaces_sites, sites_consulta)
            ],
            ignore_index=True
        )
        df_enlaces = enriquecer_enlaces_com_base(
            df_enlaces
        )

    if df_enlaces.empty:
        st.info(
            "Nenhum enlace candidato encontrado para os filtros atuais."
        )
        return

    if busca_assinatura:
        df_enlaces = df_enlaces[
            df_enlaces["Assinatura"].astype(str).str.contains(
                busca_assinatura,
                case=False,
                regex=False,
                na=False
            )
        ]

    if somente_cancelados:
        df_enlaces = filtrar_enlaces_clientes_cancelados(
            df_enlaces
        )

    tipos_enlace = sorted(
        df_enlaces["Tipo Enlace"].dropna().unique()
    )
    tipos_enlace_selecionados = st.multiselect(
        "Tipo de enlace",
        tipos_enlace,
        default=tipos_enlace
    )

    df_enlaces = df_enlaces[
        df_enlaces["Tipo Enlace"].isin(tipos_enlace_selecionados)
    ]

    if busca_icone:
        df_enlaces = df_enlaces[
            df_enlaces["Icone Enlace"].astype(str).str.contains(
                busca_icone,
                case=False,
                regex=False,
                na=False
            )
        ]

    if busca_nome:
        df_enlaces = df_enlaces[
            df_enlaces["Nome Equipamento"].astype(str).str.contains(
                busca_nome,
                case=False,
                regex=False,
                na=False
            )
        ]

    if busca_tipo:
        df_enlaces = df_enlaces[
            df_enlaces["Tipo Equipamento"].astype(str).str.contains(
                busca_tipo,
                case=False,
                regex=False,
                na=False
            )
        ]

    if df_enlaces.empty:
        st.info(
            "Nenhum enlace encontrado apos aplicar os filtros."
        )
        return

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Enlaces",
        len(df_enlaces)
    )
    col2.metric(
        "Site x Cliente",
        int(
            (df_enlaces["Tipo Enlace"] == "Site x Cliente").sum()
        )
    )
    col3.metric(
        "Site Pai x Filho",
        int(
            (df_enlaces["Tipo Enlace"] == "Site Pai x Filho").sum()
        )
    )
    col4.metric(
        "SNMPc entre sites",
        int(
            df_enlaces["Origem Dados"].astype(str).str.startswith("SNMPc").sum()
            if "Origem Dados" in df_enlaces.columns
            else 0
        )
    )

    _mostrar_grid(
        df_enlaces.sort_values(
            by=[
                "Tipo Enlace",
                "Site Pai",
                "Setorial",
                "Assinatura"
            ]
        ),
        height=620
    )


def mostrar_ferramentas(
    sites,
    equipamentos,
    enlaces_sites=None
):
    ferramentas = [
        (
            "enlaces",
            "Enlaces",
            lambda: mostrar_enlaces(
                sites,
                equipamentos,
                enlaces_sites
            )
        ),
        (
            "equipamentos_por_site",
            "Equipamentos por Site",
            lambda: mostrar_equipamentos(
                sites,
                equipamentos
            )
        ),
        (
            "buscar_equipamentos",
            "Buscar equipamentos",
            lambda: mostrar_busca_equipamentos(
                sites,
                equipamentos
            )
        ),
        (
            "editar_base_equipamentos",
            "Editar Equipamentos",
            lambda: mostrar_base_equipamentos(
                equipamentos
            )
        )
    ]

    ferramentas_permitidas = [
        ferramenta
        for ferramenta in ferramentas
        if has_permission(
            _usuario_logado(),
            ferramenta[0]
        )
    ]

    if not ferramentas_permitidas:
        st.warning(
            "Seu usuário não possui permissões para os equipamentos desta área."
        )
        return

    funcao = mostrar_subnavegacao(
        ferramentas_permitidas,
        key="ferramentas_subaba"
    )

    if funcao:
        funcao()
