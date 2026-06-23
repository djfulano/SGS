import re
import unicodedata

import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.importers.topos_importer import carregar_topos
from app.importers.topos_importer import chave_site as chave_cadastro_site
from app.importers.topos_importer import indices_topos
from app.importers.topos_importer import localizar_topo_site
from app.ui.navigation import mostrar_subnavegacao
from app.reports.site_financials import (
    montar_relatorio_custos_receita as montar_relatorio_custos_receita_relatorio
)
from app.services.contract_service import compare_sites_and_document_folders
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import sites_descendentes


_usuario_logado = None
_mostrar_grid = None
_formatar_moeda = None
_detalhes_topos_cacheados = None


def configurar_analises(
    usuario_logado,
    mostrar_grid=None,
    formatar_moeda=None,
    detalhes_topos_cacheados=None
):
    global _usuario_logado
    global _mostrar_grid
    global _formatar_moeda
    global _detalhes_topos_cacheados

    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda
    _detalhes_topos_cacheados = detalhes_topos_cacheados


def montar_clientes_snmpc_cancelados(clientes_snmpc_cancelados, equipamentos):
    equipamentos_por_assinatura = {}

    for equipamento in equipamentos:
        assinatura = str(
            equipamento.get("Assinatura") or ""
        ).strip()

        if not assinatura:
            continue

        equipamentos_por_assinatura.setdefault(
            assinatura,
            []
        ).append(equipamento)

    registros = []

    for cliente in clientes_snmpc_cancelados:
        assinatura = str(
            cliente.get("Assinatura") or ""
        ).strip()
        equipamentos_assinatura = equipamentos_por_assinatura.get(
            assinatura,
            []
        )
        base = {
            "Assinatura": assinatura,
            "Cliente SNMPc": cliente.get("Cliente") or "",
            "Site": cliente.get("Site") or "",
            "Setorial": cliente.get("Setorial") or "Direto",
            "Predio SNMPc": cliente.get("Predio") or "",
            "Qtd Equipamentos": len(equipamentos_assinatura)
        }

        if not equipamentos_assinatura:
            registros.append({
                **base,
                "Arvore": "",
                "Parent": "",
                "Equipamento": "",
                "Endereco": "",
                "Icone": "",
                "Grupo1": "",
                "Grupo2": "",
                "Status Equipamento": "",
                "Predio Equipamento": ""
            })
            continue

        for equipamento in equipamentos_assinatura:
            registros.append({
                **base,
                "Arvore": equipamento.get("Arvore") or "",
                "Parent": equipamento.get("Parent") or "",
                "Equipamento": equipamento.get("Equipamento") or "",
                "Endereco": equipamento.get("Endereco") or "",
                "Icone": equipamento.get("Icone") or "",
                "Grupo1": equipamento.get("Grupo1") or "",
                "Grupo2": equipamento.get("Grupo2") or "",
                "Status Equipamento": equipamento.get("Status") or "",
                "Predio Equipamento": equipamento.get("Predio") or ""
            })

    colunas = [
        "Assinatura",
        "Cliente SNMPc",
        "Site",
        "Setorial",
        "Predio SNMPc",
        "Qtd Equipamentos",
        "Arvore",
        "Parent",
        "Equipamento",
        "Endereco",
        "Icone",
        "Grupo1",
        "Grupo2",
        "Status Equipamento",
        "Predio Equipamento"
    ]

    return pd.DataFrame(
        registros,
        columns=colunas
    )


def mostrar_clientes_snmpc_cancelados(clientes_snmpc_cancelados, equipamentos):
    st.header("Clientes no SNMPc cancelado")
    st.caption(
        "Lista assinaturas que existem na topologia SNMPc, mas não existem na base de clientes atual."
    )

    if not clientes_snmpc_cancelados:
        st.success(
            "Nenhum cliente encontrado no SNMPc fora da base de clientes."
        )
        return

    df_snmpc_cancelados = montar_clientes_snmpc_cancelados(
        clientes_snmpc_cancelados,
        equipamentos
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Assinaturas no SNMPc",
        df_snmpc_cancelados["Assinatura"].nunique()
    )
    col2.metric(
        "Linhas de detalhe",
        len(df_snmpc_cancelados)
    )
    col3.metric(
        "Sites envolvidos",
        df_snmpc_cancelados["Site"].nunique()
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        busca = st.text_input(
            "Buscar cliente no SNMPc cancelado"
        )

    with col2:
        sites_opcoes = sorted(
            valor
            for valor in df_snmpc_cancelados["Site"].dropna().unique()
            if str(valor).strip()
        )
        sites_selecionados = st.multiselect(
            "Filtrar por site",
            sites_opcoes,
            default=sites_opcoes
        )

    if sites_selecionados:
        df_snmpc_cancelados = df_snmpc_cancelados[
            df_snmpc_cancelados["Site"].isin(sites_selecionados)
        ]

    if busca:
        filtro = pd.Series(
            False,
            index=df_snmpc_cancelados.index
        )

        for coluna in df_snmpc_cancelados.columns:
            filtro = filtro | df_snmpc_cancelados[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_snmpc_cancelados = df_snmpc_cancelados[filtro]

    _mostrar_grid(
        df_snmpc_cancelados.sort_values(
            by=[
                "Site",
                "Setorial",
                "Cliente SNMPc",
                "Equipamento"
            ]
        ),
        height=620,
        key="grid_clientes_snmpc_cancelados"
    )


def montar_sites_sem_clientes_base(sites):
    df_detalhes = _detalhes_topos_cacheados(sites)

    if df_detalhes.empty:
        return df_detalhes

    df_sem_clientes = df_detalhes[
        df_detalhes["Clientes Total"].fillna(0).astype(float) == 0
    ].copy()

    if "Favorecido" not in df_sem_clientes.columns:
        df_sem_clientes["Favorecido"] = ""

    colunas = [
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
        "Contrato",
        "Categoria",
        "Perfil",
        "Custo",
        "Receita Direta",
        "Receita Indireta",
        "Receita Com Filhos",
        "Receita Total",
        "Resultado",
        "Margem %",
        "Clientes Diretos",
        "Clientes Indiretos",
        "Clientes Total",
        "Endereco",
        "Numero",
        "Bairro",
        "Cidade",
        "UF",
        "CEP",
        "Ativacao",
        "Latitude",
        "Longitude",
        "Altura",
        "Restricao",
        "Detalhe",
        "Observacao"
    ]

    return df_sem_clientes[
        [
            coluna
            for coluna in colunas
            if coluna in df_sem_clientes.columns
        ]
    ]


def mostrar_sites_sem_clientes_base(sites):
    st.header("Sites sem clientes na base de clientes")
    st.caption(
        "Lista sites sem clientes vinculados a partir da base de clientes atual, incluindo detalhes cadastrais e valores do site."
    )

    df_sem_clientes = montar_sites_sem_clientes_base(sites)

    if df_sem_clientes.empty:
        st.success(
            "Nenhum site sem clientes foi encontrado."
        )
        return

    col_busca, col_tipo, col_status = st.columns([2, 1, 1])

    with col_busca:
        busca = st.text_input(
            "Buscar site sem clientes"
        )

    with col_tipo:
        tipos = sorted(
            valor
            for valor in df_sem_clientes["Tipo"].dropna().unique()
            if str(valor).strip()
        )
        tipos_selecionados = st.multiselect(
            "Filtrar por tipo",
            tipos,
            default=tipos
        )

    with col_status:
        status = sorted(
            valor
            for valor in df_sem_clientes["Status Cadastro"].dropna().unique()
            if str(valor).strip()
        )
        status_selecionados = st.multiselect(
            "Filtrar por status",
            status,
            default=status
        )

    if tipos_selecionados:
        df_sem_clientes = df_sem_clientes[
            df_sem_clientes["Tipo"].isin(tipos_selecionados)
        ]

    if status_selecionados:
        df_sem_clientes = df_sem_clientes[
            df_sem_clientes["Status Cadastro"].isin(status_selecionados)
        ]

    if busca:
        filtro = pd.Series(
            False,
            index=df_sem_clientes.index
        )

        for coluna in df_sem_clientes.columns:
            filtro = filtro | df_sem_clientes[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_sem_clientes = df_sem_clientes[filtro]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Sites sem clientes",
        len(df_sem_clientes)
    )
    col2.metric(
        "Custo total",
        _formatar_moeda(
            df_sem_clientes["Custo"].fillna(0).astype(float).sum()
        )
    )
    col3.metric(
        "Receita total",
        _formatar_moeda(
            df_sem_clientes["Receita Total"].fillna(0).astype(float).sum()
        )
    )
    col4.metric(
        "Resultado",
        _formatar_moeda(
            df_sem_clientes["Resultado"].fillna(0).astype(float).sum()
        )
    )

    _mostrar_grid(
        df_sem_clientes.sort_values(
            by=[
                "Status Cadastro",
                "Tipo",
                "Site SNMPc",
                "Nome Cadastro"
            ]
        ),
        height=620,
        key="grid_sites_sem_clientes_base_v2"
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
    df_detalhes = _detalhes_topos_cacheados(
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


def montar_relatorio_custos_receita(
    sites,
    sites_selecionados,
    incluir_filhos,
    apenas_ativos=True
):
    df_detalhes = _detalhes_topos_cacheados(sites)

    return montar_relatorio_custos_receita_relatorio(
        sites,
        df_detalhes,
        sites_selecionados,
        incluir_filhos,
        apenas_ativos=apenas_ativos
    )


def montar_clientes_custos_receita(sites, nomes_sites, incluir_filhos=False):
    registros = []
    nomes_sites = set(nomes_sites or [])

    for nome_site in sorted(nomes_sites):
        site = sites.get(nome_site)

        if not site:
            continue

        sites_consulta = (
            sites_descendentes(site)
            if incluir_filhos
            else [site]
        )

        for site_consulta in sites_consulta:
            vinculo = (
                "Direto"
                if site_consulta is site
                else "Indireto"
            )

            for cliente in site_consulta.clientes:
                registros.append({
                    "Vínculo": vinculo,
                    "Site": site_consulta.nome,
                    "Tipo Site": site_consulta.tipo,
                    "Cliente": cliente.nome,
                    "Assinatura": cliente.num_assinatura,
                    "Produto": getattr(cliente, "produto", ""),
                    "Receita": cliente.receita,
                    "Setorial": getattr(cliente, "setorial", "") or "Direto",
                    "Endereco": getattr(cliente, "endereco_completo", ""),
                    "Bairro": getattr(cliente, "bairro", ""),
                    "Cidade": getattr(cliente, "cidade", "")
                })

    return pd.DataFrame(
        registros,
        columns=[
            "Vínculo",
            "Site",
            "Tipo Site",
            "Cliente",
            "Assinatura",
            "Produto",
            "Receita",
            "Setorial",
            "Endereco",
            "Bairro",
            "Cidade"
        ]
    )


def _valor_float(valor):
    numero = pd.to_numeric(
        valor,
        errors="coerce"
    )
    return float(numero) if pd.notna(numero) else 0.0


def _totais_site_com_filhos(site, incluir_filhos=True):
    sites_consulta = (
        sites_descendentes(site)
        if incluir_filhos
        else [site]
    )
    filhos = sites_consulta[1:]
    receita_direta = receita_site(site)
    receita_indireta = sum(
        receita_site(site_filho)
        for site_filho in filhos
    )
    clientes_diretos = len(site.clientes)
    clientes_indiretos = sum(
        len(site_filho.clientes)
        for site_filho in filhos
    )
    custo_total = sum(
        _valor_float(
            getattr(site_consulta, "custo", 0)
        )
        for site_consulta in sites_consulta
    )

    return {
        "Clientes Diretos": clientes_diretos,
        "Clientes Indiretos": clientes_indiretos,
        "Clientes Total": clientes_diretos + clientes_indiretos,
        "Receita Direta": receita_direta,
        "Receita Indireta": receita_indireta,
        "Receita Total": receita_direta + receita_indireta,
        "Receita Com Filhos": receita_direta + receita_indireta,
        "Custo": custo_total,
        "Sites Filhos Considerados": len(filhos)
    }


def _aplicar_totais_sites_filhos(df, sites, incluir_filhos=True):
    if not sites or df.empty:
        return df

    df = df.copy()

    for indice, linha in df.iterrows():
        nome_site = str(
            linha.get("Site SNMPc") or ""
        ).strip()
        site = sites.get(nome_site)

        if not site:
            continue

        totais = _totais_site_com_filhos(
            site,
            incluir_filhos=incluir_filhos
        )

        for coluna, valor in totais.items():
            df.at[indice, coluna] = valor

    return df


def classificar_site_deficitario(
    prejuizo_mensal,
    margem,
    prejuizo_alto=500,
    margem_critica=-0.25
):
    if prejuizo_mensal >= prejuizo_alto and margem <= margem_critica:
        return "Crítico"

    if prejuizo_mensal >= prejuizo_alto or margem <= margem_critica:
        return "Atenção"

    return "Monitorar"


def sugerir_acao_site_deficitario(
    prejuizo_mensal,
    margem,
    clientes_total,
    custo_por_cliente,
    ticket_medio,
    prejuizo_alto=500,
    margem_critica=-0.25,
    poucos_clientes=3
):
    if (
        prejuizo_mensal >= prejuizo_alto
        and (
            clientes_total <= poucos_clientes
            or custo_por_cliente > ticket_medio * 2
        )
    ):
        return "Avaliar cancelamento ou migração"

    if margem <= margem_critica:
        return "Renegociar custo do site"

    if ticket_medio > 0:
        return "Aumentar receita/clientes"

    return "Monitorar"


def montar_sites_deficitarios(
    df_detalhes,
    sites=None,
    incluir_filhos=True,
    receita_coluna="Receita Total",
    prejuizo_alto=500,
    margem_critica=-0.25,
    poucos_clientes=3,
    somente_ativos=True,
    somente_no_snmpc=True,
    somente_com_clientes=True,
    resultado_minimo=None,
    resultado_maximo=0,
    prejuizo_minimo=0,
    margem_maxima=0,
    custo_por_cliente_minimo=0,
    max_clientes=None,
    clientes_equilibrio_minimo=0
):
    if df_detalhes is None or df_detalhes.empty:
        return pd.DataFrame()

    df = df_detalhes.copy()

    if receita_coluna not in df.columns:
        receita_coluna = "Receita Total"

    df = _aplicar_totais_sites_filhos(
        df,
        sites,
        incluir_filhos=incluir_filhos
    )

    if somente_ativos:
        df = df[
            df["Status Cadastro"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("ativo")
        ].copy()

    if somente_no_snmpc:
        df = df[
            df["No SNMPc"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("sim")
        ].copy()

    df["Clientes Total"] = pd.to_numeric(
        df.get("Clientes Total", 0),
        errors="coerce"
    ).fillna(0)

    if somente_com_clientes:
        df = df[df["Clientes Total"] > 0].copy()

    df["Receita Considerada"] = pd.to_numeric(
        df.get(receita_coluna, 0),
        errors="coerce"
    ).fillna(0)
    df["Custo"] = pd.to_numeric(
        df.get("Custo", 0),
        errors="coerce"
    ).fillna(0)
    df["Resultado"] = df["Receita Considerada"] - df["Custo"]
    df["Prejuízo Mensal"] = -df["Resultado"]
    df["Prejuízo Mensal"] = df["Prejuízo Mensal"].clip(lower=0)
    df["Prejuízo Anual"] = df["Prejuízo Mensal"] * 12
    df["Margem %"] = df.apply(
        lambda linha: (
            float(linha["Resultado"]) / float(linha["Receita Considerada"])
            if float(linha["Receita Considerada"] or 0)
            else -1.0
        ),
        axis=1
    )
    df["Custo por Cliente"] = df.apply(
        lambda linha: (
            float(linha["Custo"]) / float(linha["Clientes Total"])
            if float(linha["Clientes Total"] or 0)
            else 0
        ),
        axis=1
    )
    df["Ticket Médio"] = df.apply(
        lambda linha: (
            float(linha["Receita Considerada"]) / float(linha["Clientes Total"])
            if float(linha["Clientes Total"] or 0)
            else 0
        ),
        axis=1
    )
    df["Receita para Equilíbrio"] = df["Custo"]
    df["Gap Receita"] = df["Custo"] - df["Receita Considerada"]
    df["Clientes Necessários para Equilíbrio"] = df.apply(
        lambda linha: (
            max(
                0,
                int(-(-float(linha["Gap Receita"]) // float(linha["Ticket Médio"])))
            )
            if float(linha["Ticket Médio"] or 0)
            else 0
        ),
        axis=1
    )
    df = df[
        df["Resultado"] <= resultado_maximo
    ].copy()
    if resultado_minimo is not None:
        df = df[
            df["Resultado"] >= resultado_minimo
        ].copy()
    if prejuizo_minimo >= 0:
        df = df[
            df["Prejuízo Mensal"] >= prejuizo_minimo
        ].copy()
    else:
        df = df[
            df["Resultado"] >= prejuizo_minimo
        ].copy()
    df = df[
        df["Margem %"] <= margem_maxima
    ].copy()
    df = df[
        df["Custo por Cliente"] >= custo_por_cliente_minimo
    ].copy()
    df = df[
        df["Clientes Necessários para Equilíbrio"] >= clientes_equilibrio_minimo
    ].copy()

    if max_clientes is not None:
        df = df[
            df["Clientes Total"] <= max_clientes
        ].copy()

    if df.empty:
        return df

    df["Severidade"] = df.apply(
        lambda linha: classificar_site_deficitario(
            linha["Prejuízo Mensal"],
            linha["Margem %"],
            prejuizo_alto=prejuizo_alto,
            margem_critica=margem_critica
        ),
        axis=1
    )
    df["Ação Sugerida"] = df.apply(
        lambda linha: sugerir_acao_site_deficitario(
            linha["Prejuízo Mensal"],
            linha["Margem %"],
            linha["Clientes Total"],
            linha["Custo por Cliente"],
            linha["Ticket Médio"],
            prejuizo_alto=prejuizo_alto,
            margem_critica=margem_critica,
            poucos_clientes=poucos_clientes
        ),
        axis=1
    )

    return df.sort_values(
        by=[
            "Resultado",
            "Site SNMPc"
        ]
    )


def mostrar_sites_deficitarios(sites):
    st.header("Sites Deficitários e Baixa Margem")
    st.caption(
        "Apoia decisões de renegociação, migração ou cancelamento com base em custo, receita, margem e clientes ativos no site."
    )

    df_detalhes = _detalhes_topos_cacheados(sites)

    if df_detalhes.empty:
        st.info("A planilha imports/Sites.xlsx não possui registros válidos.")
        return

    st.subheader("Critérios para aparecer na lista")
    col1, col2, col3 = st.columns(3)

    with col1:
        somente_ativos = st.checkbox(
            "Somente sites ativos",
            value=True,
            key="sites_deficitarios_somente_ativos"
        )
        somente_no_snmpc = st.checkbox(
            "Somente sites presentes no SNMPc",
            value=True,
            key="sites_deficitarios_somente_no_snmpc"
        )
        somente_com_clientes = st.checkbox(
            "Somente sites com clientes",
            value=True,
            key="sites_deficitarios_somente_com_clientes"
        )
        incluir_filhos = st.checkbox(
            "Incluir sites filhos e clientes dos filhos",
            value=True,
            key="sites_deficitarios_incluir_filhos"
        )

    with col2:
        receita_coluna = st.selectbox(
            "Receita considerada",
            [
                "Receita Total",
                "Receita Com Filhos"
            ],
            index=0,
            key="sites_deficitarios_receita"
        )
        resultado_maximo = st.number_input(
            "Resultado máximo",
            value=0.0,
            step=100.0,
            key="sites_deficitarios_resultado_maximo",
            help=(
                "Use 0 para listar apenas sites sem lucro. Use valor positivo para "
                "incluir sites com lucro baixo, por exemplo 500 ou 1000."
            )
        )
        aplicar_resultado_minimo = st.checkbox(
            "Aplicar resultado mínimo",
            value=False,
            key="sites_deficitarios_aplicar_resultado_minimo",
            help=(
                "Use para analisar uma faixa específica de resultado. Ex.: mínimo -500 "
                "e máximo 1000 mostra sites entre R$ -500 e R$ 1.000."
            )
        )
        resultado_minimo = None
        if aplicar_resultado_minimo:
            resultado_minimo = st.number_input(
                "Resultado mínimo",
                value=-500.0,
                step=100.0,
                key="sites_deficitarios_resultado_minimo"
            )
        prejuizo_minimo = st.number_input(
            "Prejuízo mínimo",
            value=0.0,
            step=50.0,
            key="sites_deficitarios_prejuizo_minimo",
            help=(
                "Com valor 0, não bloqueia sites positivos. Use valor positivo para "
                "exigir prejuízo real. Use valor negativo apenas para abrir uma faixa "
                "inferior por resultado."
            )
        )

    with col3:
        margem_maxima_percentual = st.number_input(
            "Margem máxima (%)",
            min_value=-100.0,
            max_value=100.0,
            value=0.0,
            step=5.0,
            key="sites_deficitarios_margem_maxima",
            help=(
                "Use valor positivo para encontrar sites com lucro, mas margem baixa. "
                "Ex.: 10 mostra sites com margem até 10%."
            )
        )
        custo_por_cliente_minimo = st.number_input(
            "Custo por cliente mínimo",
            min_value=0.0,
            value=0.0,
            step=50.0,
            key="sites_deficitarios_custo_cliente_minimo"
        )
        max_clientes_valor = st.number_input(
            "Máximo de clientes",
            min_value=0,
            value=0,
            step=1,
            key="sites_deficitarios_max_clientes",
            help="Use 0 para não aplicar limite máximo de clientes."
        )
        clientes_equilibrio_minimo = st.number_input(
            "Clientes necessários para equilíbrio mínimo",
            min_value=0,
            value=0,
            step=1,
            key="sites_deficitarios_clientes_equilibrio_minimo"
        )

    st.subheader("Parâmetros de classificação")
    col1, col2, col3 = st.columns(3)

    with col1:
        prejuizo_alto = st.number_input(
            "Prejuízo alto mensal",
            min_value=0.0,
            value=500.0,
            step=50.0,
            key="sites_deficitarios_prejuizo_alto"
        )

    with col2:
        margem_critica_percentual = st.number_input(
            "Margem crítica (%)",
            min_value=-100.0,
            max_value=0.0,
            value=-25.0,
            step=5.0,
            key="sites_deficitarios_margem_critica"
        )

    with col3:
        poucos_clientes = st.number_input(
            "Poucos clientes",
            min_value=1,
            value=3,
            step=1,
            key="sites_deficitarios_poucos_clientes"
        )

    df_deficitarios = montar_sites_deficitarios(
        df_detalhes,
        sites=sites,
        incluir_filhos=incluir_filhos,
        receita_coluna=receita_coluna,
        prejuizo_alto=prejuizo_alto,
        margem_critica=margem_critica_percentual / 100,
        poucos_clientes=poucos_clientes,
        somente_ativos=somente_ativos,
        somente_no_snmpc=somente_no_snmpc,
        somente_com_clientes=somente_com_clientes,
        resultado_minimo=resultado_minimo,
        resultado_maximo=resultado_maximo,
        prejuizo_minimo=prejuizo_minimo,
        margem_maxima=margem_maxima_percentual / 100,
        custo_por_cliente_minimo=custo_por_cliente_minimo,
        max_clientes=(
            int(max_clientes_valor)
            if max_clientes_valor
            else None
        ),
        clientes_equilibrio_minimo=int(clientes_equilibrio_minimo)
    )

    if df_deficitarios.empty:
        st.info(
            "Nenhum site atende aos critérios atuais."
        )
        return

    st.subheader("Filtros de visualização")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        busca = st.text_input(
            "Buscar",
            placeholder="Site, nome, favorecido, categoria, perfil ou cidade",
            key="sites_deficitarios_busca"
        )

    with col2:
        severidades = st.multiselect(
            "Severidade",
            [
                "Crítico",
                "Atenção",
                "Monitorar"
            ],
            default=[
                "Crítico",
                "Atenção",
                "Monitorar"
            ],
            key="sites_deficitarios_severidade"
        )

    with col3:
        acoes_sugeridas = st.multiselect(
            "Ação sugerida",
            sorted(
                df_deficitarios["Ação Sugerida"].dropna().unique()
            ),
            default=sorted(
                df_deficitarios["Ação Sugerida"].dropna().unique()
            ),
            key="sites_deficitarios_acao_sugerida"
        )

    df_filtrado = df_deficitarios.copy()

    if severidades:
        df_filtrado = df_filtrado[
            df_filtrado["Severidade"].isin(severidades)
        ]

    if acoes_sugeridas:
        df_filtrado = df_filtrado[
            df_filtrado["Ação Sugerida"].isin(acoes_sugeridas)
        ]

    if busca:
        filtro = pd.Series(
            False,
            index=df_filtrado.index
        )

        for coluna in [
            "Site SNMPc",
            "Nome Cadastro",
            "Favorecido",
            "Categoria",
            "Perfil",
            "Cidade"
        ]:
            if coluna in df_filtrado.columns:
                filtro = filtro | df_filtrado[coluna].astype(str).str.contains(
                    busca,
                    case=False,
                    regex=False,
                    na=False
                )

        df_filtrado = df_filtrado[filtro]

    if df_filtrado.empty:
        st.info("Nenhum site atende aos critérios atuais.")
        return

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Sites analisados", len(df_filtrado))
    col2.metric(
        "Prejuízo mensal",
        _formatar_moeda(df_filtrado["Prejuízo Mensal"].sum())
    )
    col3.metric(
        "Prejuízo anual",
        _formatar_moeda(df_filtrado["Prejuízo Anual"].sum())
    )
    col4.metric(
        "Clientes impactados",
        int(df_filtrado["Clientes Total"].sum())
    )
    col5.metric(
        "Custo mensal",
        _formatar_moeda(df_filtrado["Custo"].sum())
    )
    col6.metric(
        "Receita mensal",
        _formatar_moeda(df_filtrado["Receita Considerada"].sum())
    )

    st.subheader("Sites com déficit ou baixa margem")
    colunas_sites = [
        "Severidade",
        "Ação Sugerida",
        "Site SNMPc",
        "No SNMPc",
        "Nome Cadastro",
        "Tipo",
        "Status Cadastro",
        "Favorecido",
        "Categoria",
        "Perfil",
        "Cidade",
        "Sites Filhos Considerados",
        "Clientes Total",
        "Receita Considerada",
        "Custo",
        "Resultado",
        "Prejuízo Mensal",
        "Prejuízo Anual",
        "Margem %",
        "Custo por Cliente",
        "Ticket Médio",
        "Receita para Equilíbrio",
        "Gap Receita",
        "Clientes Necessários para Equilíbrio"
    ]
    colunas_sites = [
        coluna
        for coluna in colunas_sites
        if coluna in df_filtrado.columns
    ]

    _mostrar_grid(
        df_filtrado[colunas_sites].sort_values(
            by=[
                "Resultado",
                "Site SNMPc"
            ]
        ),
        height=520,
        key="sites_deficitarios_ranking"
    )

    st.subheader("Clientes impactados")
    df_clientes = montar_clientes_custos_receita(
        sites,
        df_filtrado["Site SNMPc"].tolist(),
        incluir_filhos=incluir_filhos
    )

    if df_clientes.empty:
        st.info("Nenhum cliente localizado nos sites filtrados.")
    else:
        _mostrar_grid(
            df_clientes.sort_values(
                by=[
                    "Vínculo",
                    "Site",
                    "Cliente",
                    "Assinatura"
                ]
            ),
            height=420,
            key="sites_deficitarios_clientes"
        )

    st.subheader("Resumo por ação sugerida")
    df_acoes = (
        df_filtrado
        .groupby("Ação Sugerida", dropna=False)
        .agg({
            "Site SNMPc": "nunique",
            "Clientes Total": "sum",
            "Custo": "sum",
            "Receita Considerada": "sum",
            "Prejuízo Mensal": "sum",
            "Prejuízo Anual": "sum"
        })
        .reset_index()
        .rename(columns={
            "Site SNMPc": "Sites",
            "Clientes Total": "Clientes",
            "Receita Considerada": "Receita"
        })
        .sort_values(
            by="Prejuízo Mensal",
            ascending=False
        )
    )
    _mostrar_grid(
        df_acoes,
        height=260,
        key="sites_deficitarios_resumo_acoes"
    )


def extrair_sites_resumo_selecionados(df_resumo):
    if df_resumo is None or df_resumo.empty:
        return []

    if "Selecionar" not in df_resumo.columns:
        return []

    return [
        str(linha.get("Site escolhido") or "").strip()
        for _indice, linha in df_resumo.iterrows()
        if bool(linha.get("Selecionar"))
        and str(linha.get("Site escolhido") or "").strip()
    ]


def mostrar_custos_receita_sites(sites):
    st.header("Custos x receita")

    if not sites:
        st.info("Nenhum site disponível para consulta.")
        return

    df_detalhes = _detalhes_topos_cacheados(sites)

    if df_detalhes.empty:
        st.info("A planilha imports/Sites.xlsx não possui registros válidos.")
        return

    sites_ativos = set(
        df_detalhes[
            df_detalhes["Status Cadastro"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("ativo")
        ]["Site SNMPc"]
        .fillna("")
        .astype(str)
        .str.strip()
        .loc[lambda coluna: coluna != ""]
        .tolist()
    )

    rotulos = rotulos_sites_por_nome(
        sites
    )

    col1, col2, col3 = st.columns([3, 1, 1])

    with col2:
        apenas_ativos = st.checkbox(
            "Apenas sites ativos",
            value=True,
            key="analises_custos_receita_apenas_ativos"
        )

    opcoes_site = sorted(
        nome
        for nome in sites.keys()
        if (
            not apenas_ativos
            or nome in sites_ativos
        )
    )

    sites_ja_selecionados = st.session_state.get(
        "analises_custos_receita_sites",
        []
    )
    opcoes_site = sorted(
        set(opcoes_site) | {
            nome
            for nome in sites_ja_selecionados
            if (
                not apenas_ativos
                or nome in sites_ativos
            )
        }
    )

    if apenas_ativos and "analises_custos_receita_sites" in st.session_state:
        st.session_state["analises_custos_receita_sites"] = [
            nome
            for nome in st.session_state["analises_custos_receita_sites"]
            if nome in sites_ativos
        ]

    filtro_pendente = st.session_state.pop(
        "analises_custos_receita_sites_pendentes",
        None
    )

    if filtro_pendente is not None:
        st.session_state["analises_custos_receita_sites"] = [
            nome
            for nome in filtro_pendente
            if nome in opcoes_site
        ]

    with col1:
        sites_selecionados = st.multiselect(
            "Sites",
            opcoes_site,
            key="analises_custos_receita_sites",
            format_func=formatador_site(rotulos)
        )

    with col3:
        incluir_filhos = st.checkbox(
            "Incluir sites filhos",
            value=True,
            key="analises_custos_receita_incluir_filhos"
        )

    if not sites_selecionados:
        st.info("Selecione um ou mais sites para gerar o relatório.")
        return

    df_resumo, df_detalhe = montar_relatorio_custos_receita(
        sites,
        sites_selecionados,
        incluir_filhos,
        apenas_ativos=apenas_ativos
    )

    if df_detalhe.empty:
        st.warning("Nenhum dado financeiro encontrado para os sites selecionados.")
        return

    receita_total = df_detalhe["Receita Total"].fillna(0).astype(float).sum()
    custo_total = df_detalhe["Custo"].fillna(0).astype(float).sum()
    resultado_total = receita_total - custo_total
    margem_total = (
        resultado_total / receita_total
        if receita_total
        else 0
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Sites no escopo", len(df_detalhe))
    col2.metric("Receita", _formatar_moeda(receita_total))
    col3.metric("Custo", _formatar_moeda(custo_total))
    col4.metric("Resultado", _formatar_moeda(resultado_total))
    col5.metric("Margem", f"{margem_total:.1%}")

    st.subheader("Resumo por site escolhido")
    df_resumo_ordenado = df_resumo.sort_values(
        by=[
            "Resultado",
            "Site escolhido"
        ],
        ascending=[
            True,
            True
        ]
    ).copy()
    df_resumo_ordenado.insert(
        0,
        "Selecionar",
        False
    )
    df_resumo_editado = st.data_editor(
        df_resumo_ordenado,
        hide_index=True,
        use_container_width=True,
        height=280,
        num_rows="fixed",
        disabled=[
            coluna
            for coluna in df_resumo_ordenado.columns
            if coluna != "Selecionar"
        ],
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar"
            )
        },
        key="analises_custos_receita_resumo"
    )
    sites_novo_filtro = extrair_sites_resumo_selecionados(
        df_resumo_editado
    )

    if st.button(
        "Carregar novo filtro",
        disabled=not bool(sites_novo_filtro),
        key="analises_custos_receita_carregar_novo_filtro"
    ):
        st.session_state["analises_custos_receita_sites_pendentes"] = sites_novo_filtro
        st.rerun()

    st.subheader("Detalhamento do escopo")
    colunas = [
        "Site SNMPc",
        "No SNMPc",
        "Codigo",
        "Microsiga",
        "Nome Cadastro",
        "Tipo",
        "Status Cadastro",
        "Favorecido",
        "Receita Total",
        "Custo",
        "Resultado",
        "Margem %",
        "Clientes Total"
    ]

    _mostrar_grid(
        df_detalhe[colunas].sort_values(
            by=[
                "Resultado",
                "Site SNMPc"
            ],
            ascending=[
                True,
                True
            ]
        ),
        height=520,
        key="analises_custos_receita_detalhe"
    )

    st.subheader("Clientes e sites associados ao filtro")
    df_clientes_associados = montar_clientes_custos_receita(
        sites,
        df_detalhe["Site SNMPc"].tolist()
    )

    if df_clientes_associados.empty:
        st.info("Nenhum cliente associado aos sites filtrados.")
    else:
        _mostrar_grid(
            df_clientes_associados.sort_values(
                by=[
                    "Site",
                    "Cliente",
                    "Assinatura"
                ]
            ),
            height=520,
            key="analises_custos_receita_clientes_associados"
        )


def mostrar_clientes_sem_vinculo(clientes_sem_site):
    st.header("Clientes sem vínculo")

    if not clientes_sem_site:
        st.success(
            "Todos os clientes foram vinculados."
        )
        return

    registros = []

    for cliente in clientes_sem_site:
        if isinstance(cliente, dict):
            registros.append({
                "Cliente": cliente.get("Cliente") or cliente.get("nome") or "",
                "Assinatura": cliente.get("Assinatura") or cliente.get("num_assinatura") or "",
                "Produto": cliente.get("Produto") or cliente.get("produto") or "",
                "Mensalidade": cliente.get("Mensalidade") or cliente.get("receita") or 0
            })
        else:
            nome, assinatura = cliente
            registros.append({
                "Cliente": nome,
                "Assinatura": assinatura,
                "Produto": "",
                "Mensalidade": 0
            })

    df_sem_site = pd.DataFrame(
        registros,
        columns=[
            "Cliente",
            "Assinatura",
            "Produto",
            "Mensalidade"
        ]
    )

    busca = st.text_input(
        "Buscar cliente sem vínculo"
    )

    if busca:
        filtro = pd.Series(
            False,
            index=df_sem_site.index
        )

        for coluna in [
            "Cliente",
            "Assinatura",
            "Produto"
        ]:
            filtro = filtro | df_sem_site[coluna].astype(str).str.contains(
                busca,
                case=False,
                regex=False,
                na=False
            )

        df_sem_site = df_sem_site[filtro]

    st.metric(
        "Clientes sem vínculo",
        len(df_sem_site)
    )

    _mostrar_grid(
        df_sem_site,
        height=520
    )


def mostrar_ranking_sites(df_sites):
    st.header("Ranking de sites")

    quantidade = st.slider(
        "Quantidade no ranking",
        min_value=5,
        max_value=50,
        value=10,
        step=5
    )

    maior_receita = (
        df_sites
        .sort_values(
            by="Receita Total",
            ascending=False
        )
        .head(quantidade)
    )

    menor_receita = (
        df_sites
        .sort_values(
            by="Receita Total",
            ascending=True
        )
        .head(quantidade)
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Maior receita")
        _mostrar_grid(
            maior_receita,
            height=420
        )

    with col2:
        st.subheader("Menor receita")
        _mostrar_grid(
            menor_receita,
            height=420
        )


def chave_estrutura(valor):
    return re.sub(
        r"\s+",
        "",
        chave_cadastro_site(valor)
    )


def texto_normalizado(valor):
    texto = str(valor or "").strip().lower()

    return unicodedata.normalize(
        "NFKD",
        texto
    ).encode(
        "ascii",
        "ignore"
    ).decode("ascii")


def status_site_cancelado(valor):
    return texto_normalizado(valor) in {
        "cancelado",
        "cancelada"
    }


def topo_cancelado(topo):
    return status_site_cancelado(
        topo.get("Status Cadastro")
    )


def referencias_estrutura_equipamentos(equipamentos):
    referencias_nome = set()
    referencias_codigo = set()

    for equipamento in equipamentos:
        for campo in [
            "Parent",
            "Site",
            "Equipamento"
        ]:
            valor = str(
                equipamento.get(campo) or ""
            ).strip()

            if not valor:
                continue

            referencias_nome.add(
                chave_estrutura(valor)
            )

            for codigo in re.findall(
                r"\d+",
                valor
            ):
                referencias_codigo.add(codigo)

    return referencias_nome, referencias_codigo


def montar_conciliacao_sites_topos(sites, equipamentos):
    df_topos = carregar_topos()
    por_snmpc, por_codigo = indices_topos(df_topos)
    codigos_usados = set()
    snmpc_usados = set()
    referencias_nome, referencias_codigo = referencias_estrutura_equipamentos(
        equipamentos
    )
    sites_sem_topos = []

    for site in sites.values():
        topo = localizar_topo_site(
            site.nome,
            por_snmpc,
            por_codigo
        )

        if topo:
            if topo_cancelado(topo):
                continue

            codigo = str(topo.get("Codigo") or "").strip()
            snmpc = str(topo.get("SNMPc") or "").strip().upper()

            if codigo:
                codigos_usados.add(codigo)

            if snmpc:
                snmpc_usados.add(snmpc)
                snmpc_usados.add(
                    chave_estrutura(snmpc)
                )

            continue

        receita_direta = receita_site(site)
        receita_indireta = receita_indireta_site(site)

        sites_sem_topos.append({
            "Site SNMPc": site.nome,
            "Tipo SNMPc": site.tipo,
            "Clientes Diretos": len(site.clientes),
            "Clientes Indiretos": clientes_indiretos_site(site),
            "Clientes Total": len(site.clientes) + clientes_indiretos_site(site),
            "Receita Direta": receita_direta,
            "Receita Indireta": receita_indireta,
            "Receita Total": receita_direta + receita_indireta,
            "Pai": site.pai.nome if site.pai else "",
            "Filhos": len(site.filhos)
        })

    topos_sem_estrutura = []

    if not df_topos.empty:
        for topo in df_topos.to_dict("records"):
            if topo_cancelado(topo):
                continue

            codigo = str(topo.get("Codigo") or "").strip()
            snmpc = str(topo.get("SNMPc") or "").strip().upper()
            snmpc_chave = chave_estrutura(snmpc)

            if (
                codigo in codigos_usados
                or snmpc in snmpc_usados
                or snmpc_chave in snmpc_usados
                or snmpc_chave in referencias_nome
                or codigo in referencias_codigo
            ):
                continue

            topos_sem_estrutura.append({
                "Codigo": topo.get("Codigo") or "",
                "Microsiga": topo.get("Microsiga") or "",
                "Codigo Condominio": topo.get("Codigo Condominio") or "",
                "Abreviacao": topo.get("Abreviacao") or "",
                "SNMPc": topo.get("SNMPc") or "",
                "Tipo": topo.get("Tipo Cadastro") or "",
                "Nome Cadastro": topo.get("Nome Cadastro") or "",
                "Status Cadastro": topo.get("Status Cadastro") or "",
                "Relacionamento": topo.get("Relacionamento") or "",
                "Custo": float(topo.get("Custo") or 0),
                "Contrato": topo.get("Contrato") or "",
                "Qtdo": topo.get("Qtdo") or 0,
                "Categoria": topo.get("Categoria") or "",
                "Perfil": topo.get("Perfil") or "",
                "Endereco": topo.get("Endereco") or "",
                "Numero": topo.get("Numero") or "",
                "Bairro": topo.get("Bairro") or "",
                "Cidade": topo.get("Cidade") or "",
                "UF": topo.get("UF") or "",
                "Detalhe": topo.get("Detalhe") or "",
                "Observacao": topo.get("Observacao") or ""
            })

    return (
        pd.DataFrame(sites_sem_topos),
        pd.DataFrame(topos_sem_estrutura)
    )


def mostrar_conciliacao_sites(sites, equipamentos):
    st.header("Conciliação SNMPc x Sites")

    df_estrutura_sem_topos, df_topos_sem_estrutura = montar_conciliacao_sites_topos(
        sites,
        equipamentos
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "Sites ausentes no SNMPc",
        len(df_topos_sem_estrutura)
    )
    col2.metric(
        "Sites no SNMPc e ausentes na lista de Sites",
        len(df_estrutura_sem_topos)
    )

    def mostrar_estrutura_sem_topos():
        if df_estrutura_sem_topos.empty:
            st.success("Nenhum site no SNMPc ausente na lista de Sites.")
        else:
            _mostrar_grid(
                df_estrutura_sem_topos.sort_values(
                    by=[
                        "Tipo SNMPc",
                        "Site SNMPc"
                    ]
                ),
                height=560,
                key="conciliacao_estrutura_sem_topos"
            )

    def mostrar_topos_sem_estrutura():
        if df_topos_sem_estrutura.empty:
            st.success("Nenhum site ausente no SNMPc.")
        else:
            _mostrar_grid(
                df_topos_sem_estrutura.sort_values(
                    by=[
                        "Tipo",
                        "Status Cadastro",
                        "SNMPc",
                        "Codigo"
                    ]
                ),
                height=560,
                key="conciliacao_topos_sem_estrutura"
            )

    funcao = mostrar_subnavegacao(
        [
            (
                "topos_sem_estrutura",
                "Sites ausentes no SNMPc",
                mostrar_topos_sem_estrutura
            ),
            (
                "estrutura_sem_topos",
                "Sites no SNMPc e ausentes na lista de Sites",
                mostrar_estrutura_sem_topos
            )
        ],
        key="conciliacao_sites_subaba"
    )

    if funcao:
        funcao()


def pode_ver_relatorio_unificado(chave):
    usuario_atual = _usuario_logado()

    return has_permission(
        usuario_atual,
        chave
    )


def mostrar_sites_x_documentos(sites):
    st.header("Sites x Documentos")
    st.caption(
        "Compara os sites da base com as pastas existentes no armazenamento de documentos."
    )
    sites_sem_pasta, pastas_sem_site = compare_sites_and_document_folders(
        sites
    )

    col1, col2 = st.columns(2)
    col1.metric(
        "Sites sem pasta",
        len(sites_sem_pasta)
    )
    col2.metric(
        "Pastas sem site",
        len(pastas_sem_site)
    )

    st.subheader("Sites sem pasta de documentos")

    if sites_sem_pasta:
        _mostrar_grid(
            pd.DataFrame(sites_sem_pasta),
            height=520,
            key="sites_sem_pasta_documentos"
        )
    else:
        st.success("Todos os sites possuem pasta de documentos.")

    st.subheader("Pastas sem site cadastrado")

    if pastas_sem_site:
        _mostrar_grid(
            pd.DataFrame(pastas_sem_site),
            height=520,
            key="pastas_sem_site_documentos"
        )
    else:
        st.success("Todas as pastas de documentos possuem site correspondente.")


def mostrar_analises_conciliacao(
    sites,
    df_sites,
    equipamentos,
    clientes_sem_site,
    clientes_snmpc_cancelados,
    mostrar_sites_sem_clientes_base,
    mostrar_clientes_snmpc_cancelados
):
    relatorios = [
        (
            "conciliacao_sites",
            "Conciliação",
            lambda: mostrar_conciliacao_sites(
                sites,
                equipamentos
            )
        ),
        (
            "ranking",
            "Ranking",
            lambda: mostrar_ranking_sites(df_sites)
        ),
        (
            "custos_receita",
            "Custos x receita",
            lambda: mostrar_custos_receita_sites(sites)
        ),
        (
            "sites_deficitarios",
            "Sites Deficitários",
            lambda: mostrar_sites_deficitarios(sites)
        ),
        (
            "sites_documentos",
            "Sites x Documentos",
            lambda: mostrar_sites_x_documentos(sites)
        ),
        (
            "sem_vinculo",
            "Sem vínculo",
            lambda: mostrar_clientes_sem_vinculo(clientes_sem_site)
        ),
        (
            "sites_sem_clientes",
            "Sites sem clientes",
            lambda: mostrar_sites_sem_clientes_base(sites)
        ),
        (
            "clientes_snmpc_cancelados",
            "Clientes no SNMPc cancelado",
            lambda: mostrar_clientes_snmpc_cancelados(
                clientes_snmpc_cancelados,
                equipamentos
            )
        )
    ]

    relatorios_permitidos = [
        relatorio
        for relatorio in relatorios
        if pode_ver_relatorio_unificado(relatorio[0])
    ]

    if not relatorios_permitidos:
        st.warning(
            "Seu usuário não possui permissões para os relatórios desta área."
        )
        return

    funcao = mostrar_subnavegacao(
        relatorios_permitidos,
        key="analises_conciliacao_subaba"
    )

    if funcao:
        funcao()
