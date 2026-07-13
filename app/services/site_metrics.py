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
