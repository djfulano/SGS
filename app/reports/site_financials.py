import pandas as pd

from app.importers.topos_importer import carregar_topos
from app.importers.topos_importer import indices_topos
from app.importers.topos_importer import localizar_topo_site
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import sites_descendentes


def montar_detalhes_topos(sites):

    df_topos = carregar_topos()
    por_snmpc, por_codigo = indices_topos(df_topos)
    codigos_usados = set()
    snmpc_usados = set()
    dados = []

    for site in sites.values():

        topo = localizar_topo_site(
            site.nome,
            por_snmpc,
            por_codigo
        ) or {}

        if topo.get("Codigo"):

            codigos_usados.add(
                str(topo.get("Codigo"))
            )

        if topo.get("SNMPc"):

            snmpc_usados.add(
                str(topo.get("SNMPc")).upper()
            )

        receita_direta = receita_site(site)
        receita_indireta = receita_indireta_site(site)
        receita_com_filhos = receita_direta + receita_indireta
        receita_total = receita_direta
        custo = float(topo.get("Custo") or 0)
        resultado = receita_total - custo
        margem = (
            resultado / receita_total
            if receita_total
            else 0
        )
        clientes_indiretos = clientes_indiretos_site(site)

        dados.append({
            "Site SNMPc": site.nome,
            "No SNMPc": "Sim",
            "Codigo": topo.get("Codigo") or getattr(site, "codigo_topos", ""),
            "Microsiga": topo.get("Microsiga") or getattr(site, "microsiga", ""),
            "Codigo Condominio": topo.get("Codigo Condominio") or getattr(site, "codigo_condominio", ""),
            "Abreviacao": topo.get("Abreviacao") or getattr(site, "abreviacao", ""),
            "SNMPc": topo.get("SNMPc") or "",
            "Tipo": topo.get("Tipo Cadastro") or site.tipo,
            "Nome Cadastro": topo.get("Nome Cadastro") or getattr(site, "nome_cadastro", ""),
            "Status Cadastro": topo.get("Status Cadastro") or getattr(site, "status_cadastro", ""),
            "Relacionamento": topo.get("Relacionamento") or getattr(site, "relacionamento", ""),
            "Favorecido": topo.get("Favorecido") or getattr(site, "favorecido", ""),
            "Custo": custo,
            "Receita Direta": receita_direta,
            "Receita Indireta": receita_indireta,
            "Receita Com Filhos": receita_com_filhos,
            "Receita Total": receita_total,
            "Resultado": resultado,
            "Margem %": margem,
            "Clientes Diretos": len(site.clientes),
            "Clientes Indiretos": clientes_indiretos,
            "Clientes Total": len(site.clientes) + clientes_indiretos,
            "Contrato": topo.get("Contrato") or "",
            "Qtdo": topo.get("Qtdo") or 0,
            "Categoria": topo.get("Categoria") or "",
            "Perfil": topo.get("Perfil") or "",
            "Endereco": topo.get("Endereco") or "",
            "Numero": topo.get("Numero") or "",
            "Bairro": topo.get("Bairro") or "",
            "Cidade": topo.get("Cidade") or "",
            "UF": topo.get("UF") or "",
            "CEP": topo.get("CEP") or "",
            "Ativacao": topo.get("Ativacao") or "",
            "Latitude": topo.get("Latitude") or "",
            "Longitude": topo.get("Longitude") or "",
            "Altura": topo.get("Altura") or 0,
            "Restricao": topo.get("Restricao") or "",
            "Detalhe": topo.get("Detalhe") or "",
            "Observacao": topo.get("Observacao") or ""
        })

    if not df_topos.empty:

        for topo in df_topos.to_dict("records"):

            codigo = str(topo.get("Codigo") or "")
            snmpc = str(topo.get("SNMPc") or "").upper()

            if codigo in codigos_usados or snmpc in snmpc_usados:

                continue

            custo = float(topo.get("Custo") or 0)

            dados.append({
                "Site SNMPc": "",
                "No SNMPc": "Nao",
                "Codigo": topo.get("Codigo") or "",
                "Microsiga": topo.get("Microsiga") or "",
                "Codigo Condominio": topo.get("Codigo Condominio") or "",
                "Abreviacao": topo.get("Abreviacao") or "",
                "SNMPc": topo.get("SNMPc") or "",
                "Tipo": topo.get("Tipo Cadastro") or "",
                "Nome Cadastro": topo.get("Nome Cadastro") or "",
                "Status Cadastro": topo.get("Status Cadastro") or "",
                "Relacionamento": topo.get("Relacionamento") or "",
                "Favorecido": topo.get("Favorecido") or "",
                "Custo": custo,
                "Receita Direta": 0.0,
                "Receita Indireta": 0.0,
                "Receita Com Filhos": 0.0,
                "Receita Total": 0.0,
                "Resultado": -custo,
                "Margem %": 0.0,
                "Clientes Diretos": 0,
                "Clientes Indiretos": 0,
                "Clientes Total": 0,
                "Contrato": topo.get("Contrato") or "",
                "Qtdo": topo.get("Qtdo") or 0,
                "Categoria": topo.get("Categoria") or "",
                "Perfil": topo.get("Perfil") or "",
                "Endereco": topo.get("Endereco") or "",
                "Numero": topo.get("Numero") or "",
                "Bairro": topo.get("Bairro") or "",
                "Cidade": topo.get("Cidade") or "",
                "UF": topo.get("UF") or "",
                "CEP": topo.get("CEP") or "",
                "Ativacao": topo.get("Ativacao") or "",
                "Latitude": topo.get("Latitude") or "",
                "Longitude": topo.get("Longitude") or "",
                "Altura": topo.get("Altura") or 0,
                "Restricao": topo.get("Restricao") or "",
                "Detalhe": topo.get("Detalhe") or "",
                "Observacao": topo.get("Observacao") or ""
            })

    return pd.DataFrame(dados)


def montar_relatorio_custos_receita(
    sites,
    df_detalhes,
    sites_selecionados,
    incluir_filhos,
    apenas_ativos=True
):

    if df_detalhes.empty:

        return pd.DataFrame(), pd.DataFrame()

    if apenas_ativos:

        df_detalhes = df_detalhes[
            df_detalhes["Status Cadastro"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("ativo")
        ].copy()

    registros_resumo = []
    nomes_escopo = set()

    for nome_site in sites_selecionados:

        site = sites.get(nome_site)

        if not site:

            continue

        sites_escopo = (
            sites_descendentes(site)
            if incluir_filhos
            else [site]
        )
        nomes_site_escopo = {
            site_escopo.nome
            for site_escopo in sites_escopo
        }
        nomes_escopo.update(nomes_site_escopo)

        df_site = df_detalhes[
            df_detalhes["Site SNMPc"].isin(nomes_site_escopo)
        ]

        receita = df_site["Receita Total"].fillna(0).astype(float).sum()
        custo = df_site["Custo"].fillna(0).astype(float).sum()
        resultado = receita - custo

        registros_resumo.append({
            "Site escolhido": nome_site,
            "Sites no escopo": len(df_site),
            "Clientes": df_site["Clientes Total"].fillna(0).astype(float).sum(),
            "Receita": receita,
            "Custo": custo,
            "Resultado": resultado,
            "Margem %": (
                resultado / receita
                if receita
                else 0
            )
        })

    df_detalhe = df_detalhes[
        df_detalhes["Site SNMPc"].isin(nomes_escopo)
    ].copy()

    if not df_detalhe.empty:

        df_detalhe["Margem %"] = df_detalhe.apply(
            lambda linha: (
                float(linha.get("Resultado") or 0)
                / float(linha.get("Receita Total") or 0)
                if float(linha.get("Receita Total") or 0)
                else 0
            ),
            axis=1
        )

    return (
        pd.DataFrame(registros_resumo),
        df_detalhe
    )
