import re

import pandas as pd

from app.services.product_catalog import infer_product_fields


def receita_site(site):

    return sum(
        cliente.receita
        for cliente in site.clientes
    )


def clientes_indiretos_site(site):

    return sum(
        clientes_totais_site(filho)
        for filho in site.filhos
    )


def clientes_totais_site(site):

    return len(site.clientes) + clientes_indiretos_site(site)


def receita_indireta_site(site):

    return sum(
        filho.calcular_receita()
        for filho in site.filhos
    )


def receita_total_site(site):

    return receita_site(site) + receita_indireta_site(site)


def custo_site(site):

    try:
        return float(getattr(site, "custo", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def custo_indireto_site(site):

    return sum(
        custo_total_site(filho)
        for filho in site.filhos
    )


def custo_total_site(site):

    return custo_site(site) + custo_indireto_site(site)


def sites_descendentes(site):

    sites = [site]

    for filho in site.filhos:

        sites.extend(
            sites_descendentes(filho)
        )

    return sites


def montar_escopo_sites(sites_selecionados, incluir_filhos):

    usados = {}
    selecionados = {}

    for site in sites_selecionados:

        selecionados[site.nome] = site

        sites_consulta = (
            sites_descendentes(site)
            if incluir_filhos
            else [site]
        )

        for site_consulta in sites_consulta:

            usados[site_consulta.nome] = site_consulta

    return selecionados, usados


def montar_resumo_selecao_sites(selecionados, usados):

    clientes_diretos = sum(
        len(site.clientes)
        for site in selecionados.values()
    )
    receita_direta = sum(
        receita_site(site)
        for site in selecionados.values()
    )
    clientes_total = sum(
        len(site.clientes)
        for site in usados.values()
    )
    receita_total = sum(
        receita_site(site)
        for site in usados.values()
    )
    custo_direto = sum(
        custo_site(site)
        for site in selecionados.values()
    )
    custo_total = sum(
        custo_site(site)
        for site in usados.values()
    )

    return {
        "clientes_total": clientes_total,
        "receita_total": receita_total,
        "clientes_diretos": clientes_diretos,
        "receita_direta": receita_direta,
        "clientes_indiretos": clientes_total - clientes_diretos,
        "receita_indireta": receita_total - receita_direta,
        "custo_direto": custo_direto,
        "custo_indireto": custo_total - custo_direto,
        "custo_total": custo_total
    }


def normalizar_velocidade_mbps(valor):
    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None

    texto = str(valor or "").strip()

    if not texto:
        return None

    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*"
        r"(GBPS|GIGA|GB|G|MBPS|MB|M|KBPS|KB|K)\b",
        texto,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    numero = float(match.group(1).replace(",", "."))
    unidade = match.group(2).upper()

    if unidade in {"GBPS", "GIGA", "GB", "G"}:
        return numero * 1000

    if unidade in {"KBPS", "KB", "K"}:
        return numero / 1000

    return numero


def _linha_catalogo_produto(catalogo, produto):
    if catalogo is None or catalogo.empty or "Nome" not in catalogo.columns:
        return {}

    produto_normalizado = str(produto or "").strip().casefold()

    if not produto_normalizado:
        return {}

    nomes = catalogo["Nome"].astype(str).str.strip().str.casefold()
    linhas = catalogo.loc[nomes == produto_normalizado]

    if linhas.empty:
        return {}

    return linhas.iloc[-1].to_dict()


def velocidade_telecom_produto_mbps(produto, catalogo=None):
    produto = str(produto or "").strip()

    if not produto:
        return None

    linha_catalogo = _linha_catalogo_produto(catalogo, produto)
    inferido = infer_product_fields(produto)
    tipo = str(
        linha_catalogo.get("Tipo") or inferido.get("Tipo") or ""
    ).strip().casefold()

    if tipo != "telecom":
        return None

    for valor in [
        linha_catalogo.get("Velocidade"),
        inferido.get("Velocidade"),
        produto
    ]:
        velocidade = normalizar_velocidade_mbps(valor)

        if velocidade:
            return velocidade

    return None


def formatar_banda_mbps(valor):
    if not valor or valor <= 0:
        return "0 Mbps"

    if valor >= 1000:
        texto = f"{valor / 1000:g}".replace(".", ",")
        return f"{texto} Gbps"

    texto = f"{valor:g}".replace(".", ",")
    return f"{texto} Mbps"


def montar_metricas_banda_telecom_site(site, catalogo=None):
    velocidades = []

    for site_atual in sites_descendentes(site):
        for cliente in site_atual.clientes:
            velocidade = velocidade_telecom_produto_mbps(
                getattr(cliente, "produto", ""),
                catalogo
            )

            if velocidade:
                velocidades.append(velocidade)

    return {
        "maior_mbps": max(velocidades) if velocidades else None,
        "soma_mbps": sum(velocidades),
        "acima_100_mbps": sum(
            1 for velocidade in velocidades if velocidade >= 100
        )
    }


def montar_metricas_banda_telecom_sites(sites_usados, catalogo=None):
    velocidades = []

    for site in sites_usados:
        for cliente in site.clientes:
            velocidade = velocidade_telecom_produto_mbps(
                getattr(cliente, "produto", ""),
                catalogo
            )

            if velocidade:
                velocidades.append(velocidade)

    return {
        "maior_mbps": max(velocidades) if velocidades else None,
        "soma_mbps": sum(velocidades),
        "acima_100_mbps": sum(
            1 for velocidade in velocidades if velocidade >= 100
        )
    }
