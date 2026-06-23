import pandas as pd
import streamlit as st

from app.ui.navigation import mostrar_subnavegacao
from app.services.product_catalog import PRODUCT_CATALOG_COLUMNS
from app.services.product_catalog import PRODUCT_FAMILIES
from app.services.product_catalog import PRODUCT_TYPES
from app.services.product_catalog import TELECOM_GROUPS
from app.services.product_catalog import ensure_catalog_from_clients
from app.services.product_catalog import import_product_catalog_excel
from app.services.product_catalog import load_product_catalog
from app.services.product_catalog import product_catalog_template_excel
from app.services.product_catalog import save_product_catalog
from app.services.products import montar_clientes_produtos_base
from app.services.products import montar_produtos_equipamentos
from app.services.products import montar_sva_clientes


_mostrar_grid = None
_formatar_moeda = None
_pode_ver = None


def configurar_produtos(
    mostrar_grid,
    formatar_moeda,
    pode_ver=None
):
    global _mostrar_grid
    global _formatar_moeda
    global _pode_ver

    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda
    _pode_ver = pode_ver or (lambda _chave: True)


def mostrar_produtos_equipamentos_consulta(sites, equipamentos):
    st.header("Produtos x equipamentos")

    df_produtos = montar_produtos_equipamentos(
        sites,
        equipamentos
    )

    if df_produtos.empty:
        st.warning(
            "Nenhum equipamento associado a produtos ativos foi encontrado."
        )
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        busca_produto = st.text_input(
            "Buscar produto",
            placeholder="Ex.: NeoSoft 100 Mbps"
        )

    with col2:
        busca_equipamento = st.text_input(
            "Buscar equipamento ou ícone",
            placeholder="Ex.: cn510"
        )

    with col3:
        busca_assinatura = st.text_input(
            "Buscar assinatura do produto"
        )

    df_filtrado = df_produtos.copy()

    if busca_produto:
        df_filtrado = df_filtrado[
            df_filtrado["Produto"].astype(str).str.contains(
                busca_produto,
                case=False,
                regex=False,
                na=False
            )
        ]

    if busca_equipamento:
        filtro_equipamento = (
            df_filtrado["Equipamento"].astype(str).str.contains(
                busca_equipamento,
                case=False,
                regex=False,
                na=False
            )
            | df_filtrado["Icone"].astype(str).str.contains(
                busca_equipamento,
                case=False,
                regex=False,
                na=False
            )
        )
        df_filtrado = df_filtrado[filtro_equipamento]

    if busca_assinatura:
        df_filtrado = df_filtrado[
            df_filtrado["Assinatura"].astype(str).str.contains(
                busca_assinatura,
                case=False,
                regex=False,
                na=False
            )
        ]

    if df_filtrado.empty:
        st.info(
            "Nenhum produto encontrado para os filtros informados."
        )
        return

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Registros",
        len(df_filtrado)
    )
    col2.metric(
        "Clientes",
        df_filtrado["Assinatura"].nunique()
    )
    col3.metric(
        "Tipos de equipamento",
        df_filtrado["Icone"].nunique()
    )

    st.markdown("**Ranking de equipamentos nos produtos filtrados**")

    df_ranking = (
        df_filtrado
        .groupby("Icone", dropna=False)
        .size()
        .reset_index(name="Quantidade")
        .sort_values(
            by="Quantidade",
            ascending=False
        )
    )

    _mostrar_grid(
        df_ranking,
        height=240
    )

    colunas = [
        "Produto",
        "Tipo Produto",
        "Grupo Produto",
        "Família Produto",
        "Velocidade Produto",
        "Variação Produto",
        "Cliente",
        "Assinatura",
        "Receita",
        "Equipamento",
        "Icone",
        "Endereco Equipamento",
        "Status",
        "Site Cliente",
        "Setorial Cliente",
        "Site Equipamento",
        "Setorial Equipamento",
        "Parent",
        "Predio Cliente",
        "Predio Equipamento"
    ]

    df_filtrado = df_filtrado[
        [
            coluna
            for coluna in colunas
            if coluna in df_filtrado.columns
        ]
    ]

    st.markdown("**Clientes e equipamentos associados**")

    _mostrar_grid(
        df_filtrado.sort_values(
            by=[
                "Produto",
                "Cliente",
                "Icone",
                "Equipamento"
            ]
        ),
        height=560
    )


def mostrar_base_produtos(sites):
    st.header("Editar Produtos")

    df_clientes = montar_clientes_produtos_base(sites)
    df_base = ensure_catalog_from_clients(
        df_clientes
    )
    df_catalogo_salvo = load_product_catalog()
    nomes_base = set(
        df_base["Nome"].astype(str).str.strip()
    )
    nomes_salvos = set(
        df_catalogo_salvo["Nome"].astype(str).str.strip()
    )

    if nomes_base - nomes_salvos:
        df_base = save_product_catalog(
            df_base
        )

    produtos_ativos = (
        df_clientes["Produto"].dropna().astype(str).str.strip()
        .loc[lambda coluna: coluna != ""]
        .nunique()
        if not df_clientes.empty and "Produto" in df_clientes.columns
        else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Produtos ativos",
        produtos_ativos
    )
    col2.metric(
        "Itens na base",
        len(df_base)
    )
    col3.metric(
        "Sem classificação",
        int(
            df_base["Tipo"].astype(str).str.strip().eq("").sum()
        )
    )

    with st.expander("Importação em massa por Excel"):
        st.download_button(
            "Baixar modelo Excel",
            data=product_catalog_template_excel(),
            file_name="base_produtos_modelo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="base_produtos_modelo"
        )

        arquivo_importacao = st.file_uploader(
            "Importar produtos",
            type=[
                "xlsx",
                "xls"
            ],
            key="base_produtos_importacao"
        )

        importar = st.button(
            "Importar Excel",
            type="primary",
            disabled=arquivo_importacao is None,
            key="base_produtos_importar"
        )

        if importar and arquivo_importacao is not None:
            try:
                df_importado = import_product_catalog_excel(
                    arquivo_importacao,
                    df_base
                )
                save_product_catalog(
                    df_importado
                )
                st.success(
                    f"Importação concluída. {len(df_importado)} itens na base."
                )
                st.rerun()

            except Exception as erro:
                st.error(f"Falha ao importar a base: {erro}")

    busca = st.text_input(
        "Buscar produtos",
        key="base_produtos_busca"
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
            "Nome": st.column_config.TextColumn(
                "Nome",
                required=True
            ),
            "Tipo": st.column_config.SelectboxColumn(
                "Tipo",
                options=[""] + PRODUCT_TYPES
            ),
            "Grupo": st.column_config.SelectboxColumn(
                "Grupo",
                options=[""] + TELECOM_GROUPS
            ),
            "Família": st.column_config.SelectboxColumn(
                "Família",
                options=[""] + PRODUCT_FAMILIES
            ),
            "Velocidade": st.column_config.TextColumn(
                "Velocidade"
            ),
            "Variação": st.column_config.TextColumn(
                "Variação"
            )
        },
        key="base_produtos_editor"
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        salvar = st.button(
            "Salvar base",
            type="primary",
            key="base_produtos_salvar"
        )

    with col2:
        atualizar = st.button(
            "Atualizar produtos ativos",
            key="base_produtos_atualizar_produtos"
        )

    if salvar:
        df_atual = df_base.copy()

        if busca:
            nomes_editados = set(
                df_editado["Nome"].astype(str).str.strip()
            )
            df_atual = df_atual[
                ~df_atual["Nome"].astype(str).str.strip().isin(nomes_editados)
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

        save_product_catalog(
            df_atual[PRODUCT_CATALOG_COLUMNS]
        )
        st.success("Produtos salvos.")
        st.rerun()

    if atualizar:
        save_product_catalog(
            ensure_catalog_from_clients(
                df_clientes
            )
        )
        st.success("Produtos ativos atualizados na base.")
        st.rerun()


def mostrar_produtos_equipamentos(sites, equipamentos):
    itens = []

    if _pode_ver("produtos"):
        itens.extend([
            (
                "produtos_equipamentos",
                "Produtos x equipamentos",
                lambda: mostrar_produtos_equipamentos_consulta(
                    sites,
                    equipamentos
                )
            ),
        ])

    if _pode_ver("editar_produtos"):
        itens.append(
            (
                "editar_produtos",
                "Editar Produtos",
                lambda: mostrar_base_produtos(
                    sites
                )
            )
        )

    if _pode_ver("sva"):
        itens.append(
            (
                "sva",
                "SVA",
                lambda: mostrar_sva(
                    sites,
                    equipamentos
                )
            )
        )

    funcao = mostrar_subnavegacao(
        itens,
        key="produtos_subaba"
    )

    if funcao:
        funcao()


def mostrar_sva(sites, equipamentos):
    st.header("SVA")

    df_sva = montar_sva_clientes(
        sites,
        equipamentos
    )

    if df_sva.empty:
        st.info(
            "Nenhum cliente com assinatura localizada no ícone de equipamentos."
        )
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        busca_assinatura = st.text_input(
            "Assinatura",
            key="sva_busca_assinatura"
        )

    with col2:
        produtos = sorted(
            produto
            for produto in df_sva["Produto"].dropna().unique()
            if str(produto).strip()
        )
        produtos_selecionados = st.multiselect(
            "Produto",
            produtos,
            default=produtos,
            key="sva_produtos"
        )

    with col3:
        status_opcoes = sorted(
            df_sva["Status Vinculo"].dropna().unique()
        )
        status_selecionados = st.multiselect(
            "Status de vínculo",
            status_opcoes,
            default=status_opcoes,
            key="sva_status"
        )

    df_filtrado = df_sva[
        df_sva["Status Vinculo"].isin(status_selecionados)
    ]

    if produtos_selecionados:
        df_filtrado = df_filtrado[
            df_filtrado["Produto"].isin(produtos_selecionados)
        ]

    if busca_assinatura:
        df_filtrado = df_filtrado[
            df_filtrado["Assinatura"].astype(str).str.contains(
                busca_assinatura,
                case=False,
                regex=False,
                na=False
            )
        ]

    if df_filtrado.empty:
        st.info(
            "Nenhum registro encontrado para os filtros atuais."
        )
        return

    clientes_unicos = df_filtrado["Assinatura"].nunique()
    equipamentos_unicos = int(
        df_filtrado["Equipamento"].astype(str).str.strip().ne("").sum()
    )
    sem_site = df_filtrado[
        df_filtrado["Status Vinculo"].isin([
            "Sem site direto",
            "Nao aparece no SNMPc"
        ])
    ]["Assinatura"].nunique()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Clientes",
        clientes_unicos
    )
    col2.metric(
        "Equipamentos",
        equipamentos_unicos
    )
    col3.metric(
        "Sem site direto",
        sem_site
    )
    col4.metric(
        "Receita",
        _formatar_moeda(
            df_filtrado.drop_duplicates(
                subset=["Assinatura"]
            )["Receita"].sum()
        )
    )

    _mostrar_grid(
        df_filtrado.sort_values(
            by=[
                "Status Vinculo",
                "Produto",
                "Cliente",
                "Site Equipamento"
            ]
        ),
        height=560,
        key="grid_sva"
    )
