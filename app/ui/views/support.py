import pandas as pd
import streamlit as st

from app.auth import has_permission
from app.ui.navigation import mostrar_subnavegacao
from app.ui.views.tools import mostrar_predios
from app.ui.views.tools import mostrar_retirada_equipamentos


_usuario_logado = None
_mostrar_grid = None


def configurar_suporte(usuario_logado, mostrar_grid=None):
    global _usuario_logado
    global _mostrar_grid

    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid


def texto(valor, padrao="Não localizado"):
    valor = "" if valor is None else str(valor).strip()

    return valor or padrao


def cliente_por_assinatura(sites, assinatura):
    assinatura = str(assinatura or "").strip()

    for site in (sites or {}).values():
        for cliente in getattr(site, "clientes", []):
            if str(getattr(cliente, "num_assinatura", "")).strip() == assinatura:
                return site, cliente

    return None, None


def estrutura_cliente_por_assinatura(sites, assinatura):
    assinatura = str(assinatura or "").strip()

    for site in (sites or {}).values():
        for cliente_estrutura in getattr(site, "clientes_estrutura", []):
            if str(cliente_estrutura.get("assinatura") or "").strip() == assinatura:
                return site, cliente_estrutura

    return None, {}


def equipamentos_por_assinatura(equipamentos, assinatura):
    assinatura = str(assinatura or "").strip()

    return [
        equipamento
        for equipamento in equipamentos or []
        if str(equipamento.get("Assinatura") or "").strip() == assinatura
    ]


def resumo_equipamentos_agendamento(equipamentos_assinatura):
    dados = []

    for equipamento in equipamentos_assinatura:
        dados.append({
            "Site": equipamento.get("Site") or "",
            "Setorial": equipamento.get("Setorial") or "",
            "Ícone": equipamento.get("Icone") or "",
            "Equipamento": equipamento.get("Equipamento") or "",
            "IP/Endereço": equipamento.get("Endereco") or "",
            "Equipamento Base": equipamento.get("Parent") or "",
            "Status": equipamento.get("Status") or "",
            "Prédio": equipamento.get("Predio") or ""
        })

    return pd.DataFrame(dados)


def montar_dados_agendamento(sites, equipamentos, assinatura):
    assinatura = str(assinatura or "").strip()

    if not assinatura:
        return {}, pd.DataFrame()

    site_cliente, cliente = cliente_por_assinatura(
        sites,
        assinatura
    )
    site_estrutura, cliente_estrutura = estrutura_cliente_por_assinatura(
        sites,
        assinatura
    )
    equipamentos_assinatura = equipamentos_por_assinatura(
        equipamentos,
        assinatura
    )
    primeiro_equipamento = (
        equipamentos_assinatura[0]
        if equipamentos_assinatura
        else {}
    )
    site_referencia = site_cliente or site_estrutura
    df_equipamentos = resumo_equipamentos_agendamento(
        equipamentos_assinatura
    )

    endereco = (
        getattr(cliente, "endereco_completo", "")
        if cliente
        else ""
    ) or cliente_estrutura.get("endereco", "")
    cidade = (
        getattr(cliente, "cidade", "")
        if cliente
        else ""
    )
    bairro = (
        getattr(cliente, "bairro", "")
        if cliente
        else ""
    )
    produto = (
        getattr(cliente, "produto", "")
        if cliente
        else ""
    )
    predio = (
        cliente_estrutura.get("predio")
        or primeiro_equipamento.get("Predio")
        or ""
    )
    setorial = (
        getattr(cliente, "setorial", "")
        if cliente
        else ""
    ) or cliente_estrutura.get("setorial") or primeiro_equipamento.get("Setorial")

    equipamento_cliente = ", ".join(
        sorted({
            texto(
                equipamento.get("Equipamento"),
                ""
            )
            for equipamento in equipamentos_assinatura
            if texto(
                equipamento.get("Equipamento"),
                ""
            )
        })
    )
    equipamento_base = ", ".join(
        sorted({
            texto(
                equipamento.get("Parent"),
                ""
            )
            for equipamento in equipamentos_assinatura
            if texto(
                equipamento.get("Parent"),
                ""
            )
        })
    )
    caminho_pop = ", ".join(
        sorted({
            texto(
                equipamento.get("Arvore"),
                ""
            )
            for equipamento in equipamentos_assinatura
            if texto(
                equipamento.get("Arvore"),
                ""
            )
        })
    )

    return {
        "Nº da Assinatura": texto(assinatura),
        "Nº do Código do Prédio": texto(predio),
        "Endereço": texto(endereco),
        "Cidade": texto(cidade),
        "Bairro": texto(bairro),
        "Equipamento Base": texto(equipamento_base),
        "Equipamento Cliente": texto(equipamento_cliente),
        "Caminho até o POP": texto(caminho_pop),
        "Setorial": texto(setorial),
        "Produto contratado": texto(produto),
        "Site": texto(getattr(site_referencia, "nome", "")),
        "Sites de atendimento": texto(
            ", ".join(
                getattr(vinculo.get("site"), "nome", "")
                for vinculo in getattr(cliente, "vinculos_atendimento", [])
                if vinculo.get("site") is not None
            ) if cliente else ""
        ),
    }, df_equipamentos


def mostrar_agendamento(sites, equipamentos):
    st.header("Agendamento")

    assinatura = st.text_input(
        "Assinatura",
        key="suporte_agendamento_assinatura"
    )

    if not assinatura:
        st.info("Informe uma assinatura para montar os dados do agendamento.")
        return

    dados, df_equipamentos = montar_dados_agendamento(
        sites,
        equipamentos,
        assinatura
    )

    if not dados:
        st.warning("Nenhuma informação encontrada para esta assinatura.")
        return

    st.markdown("**Dados do agendamento para visita técnica**")

    linhas = [
        ["Nº da Assinatura", dados["Nº da Assinatura"]],
        ["Nº do Código do Prédio", dados["Nº do Código do Prédio"]],
        ["Endereço", dados["Endereço"]],
        ["Cidade", dados["Cidade"]],
        ["Bairro", dados["Bairro"]],
        ["Equipamento Base", dados["Equipamento Base"]],
        ["Equipamento Cliente", dados["Equipamento Cliente"]],
        ["Caminho até o POP", dados["Caminho até o POP"]],
        ["Setorial", dados["Setorial"]],
        ["Sites de atendimento", dados["Sites de atendimento"]],
        ["Produto contratado", dados["Produto contratado"]],
    ]

    st.dataframe(
        pd.DataFrame(
            linhas,
            columns=[
                "Campo",
                "Informação"
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=420
    )

    texto_copia = "\n".join(
        f"{campo}: {valor}"
        for campo, valor in linhas
    )
    st.code(
        texto_copia,
        language=None
    )

    st.markdown("**Lista de equipamentos e IPs**")

    if df_equipamentos.empty:
        st.info("Nenhum equipamento relacionado à assinatura foi encontrado.")
        return

    if _mostrar_grid:
        _mostrar_grid(
            df_equipamentos,
            height=360,
            key="grid_suporte_agendamento_equipamentos"
        )
    else:
        st.dataframe(
            df_equipamentos,
            use_container_width=True,
            hide_index=True
        )


def mostrar_suporte(sites, equipamentos):
    usuario = _usuario_logado()
    subabas = [
        (
            "suporte_agendamento",
            "Agendamento",
            lambda: mostrar_agendamento(
                sites,
                equipamentos
            )
        ),
        (
            "retirada",
            "Retirada",
            lambda: mostrar_retirada_equipamentos(
                equipamentos
            )
        ),
        (
            "predios",
            "Prédios",
            lambda: mostrar_predios(
                sites
            )
        )
    ]
    subabas_permitidas = [
        subaba
        for subaba in subabas
        if (
            has_permission(
                usuario,
                "suporte"
            )
            or has_permission(
                usuario,
                subaba[0]
            )
        )
    ]

    if not subabas_permitidas:
        st.warning(
            "Seu usuário não possui permissões para as subabas de Suporte."
        )
        return

    funcao = mostrar_subnavegacao(
        subabas_permitidas,
        key="suporte_subaba"
    )

    if funcao:
        funcao()
