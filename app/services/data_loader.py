from pathlib import Path

from app.config import CLIENTES_FILE
from app.importers.excel_importer import importar_clientes
from app.importers.structure_importer import importar_estrutura_atual
from app.importers.structure_importer import caminho_estrutura_txt
from app.importers.structure_importer import versao_estrutura_txt
from app.importers.topos_importer import carregar_topos
from app.importers.topos_importer import caminho_sites_excel
from app.importers.topos_importer import chave_site
from app.importers.topos_importer import indices_topos
from app.importers.topos_importer import localizar_topo_site
from app.services.database_service import sincronizar_banco


def arquivos_dados_obrigatorios():
    return [
        {
            "chave": "snmpc",
            "nome": "SNMPc TXT",
            "caminho": Path(caminho_estrutura_txt())
        },
        {
            "chave": "sites",
            "nome": "Sites Excel",
            "caminho": Path(caminho_sites_excel())
        },
        {
            "chave": "clientes",
            "nome": "Clientes Excel",
            "caminho": Path(CLIENTES_FILE)
        }
    ]


def status_inicializacao_dados():
    status = []

    for item in arquivos_dados_obrigatorios():
        caminho = item["caminho"]
        existe = caminho.exists()
        status.append({
            **item,
            "caminho": str(caminho),
            "existe": existe,
            "status": "OK" if existe else "Ausente"
        })

    return status


def sistema_precisa_inicializacao():
    return any(
        not item["existe"]
        for item in status_inicializacao_dados()
    )


def versao_topos():
    caminho = caminho_sites_excel()

    if not caminho.exists():
        return "sites:ausente"

    stat = caminho.stat()

    return f"{caminho.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def versao_clientes():
    caminho = Path(CLIENTES_FILE)

    if not caminho.exists():
        return "clientes:ausente"

    stat = caminho.stat()

    return f"{caminho.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def versao_cache_dados():
    return f"{versao_estrutura_txt()}|{versao_topos()}|{versao_clientes()}"


def aplicar_cadastro_topos(sites, df_topos):
    por_snmpc, por_codigo = indices_topos(df_topos)

    for site in sites.values():
        topo = localizar_topo_site(
            site.nome,
            por_snmpc,
            por_codigo
        )

        site.cadastro_topos = topo or {}

        if topo:
            tipo_cadastro = topo.get("Tipo Cadastro") or ""

            if tipo_cadastro:
                site.tipo = tipo_cadastro

            site.codigo_topos = topo.get("Codigo") or ""
            site.microsiga = topo.get("Microsiga") or ""
            site.codigo_condominio = topo.get("Codigo Condominio") or ""
            site.abreviacao = topo.get("Abreviacao") or ""
            site.locacao = float(topo.get("Locacao") or 0)
            site.energia = float(topo.get("Energia") or 0)
            site.outros_custos = float(topo.get("Outros Custos") or 0)
            site.custo = (
                site.locacao
                + site.energia
                + site.outros_custos
            )
            site.cnpj_cpf = topo.get("CNPJ CPF") or ""
            site.tipo_pagamento = topo.get("Tipo Pagamento") or ""
            site.pix = topo.get("Pix") or ""
            site.banco = topo.get("Banco") or ""
            site.codigo_banco = topo.get("Codigo Banco") or ""
            site.agencia = topo.get("Agencia") or ""
            site.conta_corrente = topo.get("Conta Corrente") or ""
            site.multa = topo.get("Multa") or ""
            site.juros = topo.get("Juros") or ""
            site.status_cadastro = topo.get("Status Cadastro") or ""
            site.nome_cadastro = topo.get("Nome Cadastro") or ""
            site.relacionamento = topo.get("Relacionamento") or ""
            site.favorecido = topo.get("Favorecido") or ""
            site.contrato = topo.get("Contrato") or ""
            site.categoria = topo.get("Categoria") or ""
            site.perfil = topo.get("Perfil") or ""
            site.endereco = topo.get("Endereco") or ""
            site.numero = topo.get("Numero") or ""
            site.bairro = topo.get("Bairro") or ""
            site.cidade = topo.get("Cidade") or ""
            site.uf = topo.get("UF") or ""
            site.cep = topo.get("CEP") or ""
            site.latitude = float(topo.get("Latitude") or 0)
            site.longitude = float(topo.get("Longitude") or 0)
            site.altura = float(topo.get("Altura") or 0)
            site.restricao = topo.get("Restricao") or ""
            site.site_critico = str(
                topo.get("Site Critico") or ""
            ).strip().casefold() in {"sim", "s", "true", "1"}
            site.tipo_criticidade = topo.get("Tipo Criticidade") or ""
            site.dia_vencimento = int(topo.get("Dia Vencimento") or 0)
            site.detalhe = topo.get("Detalhe") or ""
            site.observacao = topo.get("Observacao") or ""

        else:
            site.codigo_topos = ""
            site.microsiga = ""
            site.codigo_condominio = ""
            site.abreviacao = ""
            site.custo = 0.0
            site.locacao = 0.0
            site.energia = 0.0
            site.outros_custos = 0.0
            site.cnpj_cpf = ""
            site.tipo_pagamento = ""
            site.pix = ""
            site.banco = ""
            site.codigo_banco = ""
            site.agencia = ""
            site.conta_corrente = ""
            site.multa = ""
            site.juros = ""
            site.status_cadastro = ""
            site.nome_cadastro = ""
            site.relacionamento = ""
            site.favorecido = ""
            site.contrato = ""
            site.categoria = ""
            site.perfil = ""
            site.endereco = ""
            site.numero = ""
            site.bairro = ""
            site.cidade = ""
            site.uf = ""
            site.cep = ""
            site.latitude = 0.0
            site.longitude = 0.0
            site.altura = 0.0
            site.restricao = ""
            site.site_critico = False
            site.tipo_criticidade = ""
            site.dia_vencimento = 0
            site.detalhe = ""
            site.observacao = ""

    return sites


def consolidar_sites_duplicados_cadastro(
    sites,
    assinaturas=None,
    equipamentos=None,
    enlaces_sites=None
):
    """Consolida contêineres SNMPc que apontam para o mesmo site cadastrado."""
    assinaturas = assinaturas or {}
    equipamentos = equipamentos or []
    enlaces_sites = enlaces_sites if enlaces_sites is not None else []
    grupos = {}

    for site in sites.values():
        codigo = str(site.codigo_topos or "").strip()

        if codigo:
            grupos.setdefault(codigo, []).append(site)

    substituicoes = {}

    for grupo in grupos.values():
        if len(grupo) < 2:
            continue

        nomes_oficiais = {
            chave_site(site.cadastro_topos.get("SNMPc"))
            for site in grupo
            if site.cadastro_topos
            and chave_site(site.cadastro_topos.get("SNMPc"))
        }
        candidatos = [
            site
            for site in grupo
            if chave_site(site.nome) in nomes_oficiais
        ]

        if len(candidatos) != 1:
            continue

        canonico = candidatos[0]

        for alias in grupo:
            if alias is not canonico:
                substituicoes[alias] = canonico

    if not substituicoes:
        return sites

    for alias, canonico in substituicoes.items():
        pai_alias = alias.pai

        if pai_alias and alias in pai_alias.filhos:
            pai_alias.filhos.remove(alias)

        if canonico.pai is alias:
            canonico.pai = None

        if canonico in alias.filhos:
            alias.filhos.remove(canonico)

        if (
            pai_alias
            and pai_alias is not canonico
            and substituicoes.get(pai_alias, pai_alias) is not canonico
            and canonico.pai is None
        ):
            pai_alias.adicionar_filho(canonico)

        for filho in list(alias.filhos):
            filho_real = substituicoes.get(filho, filho)

            if filho_real is not canonico:
                canonico.adicionar_filho(filho_real)

        for assinatura in alias.assinaturas:
            if assinatura not in canonico.assinaturas:
                canonico.assinaturas.append(assinatura)

        for vinculo in alias.clientes_estrutura:
            canonico.adicionar_cliente_estrutura(
                vinculo.get("nome") or "",
                vinculo.get("assinatura") or "",
                predio=vinculo.get("predio"),
                setorial=vinculo.get("setorial"),
                tipo_vinculo=vinculo.get("tipo_vinculo") or "Principal"
            )

        for equipamento in alias.equipamentos:
            if equipamento not in canonico.equipamentos:
                canonico.equipamentos.append(equipamento)

        for setorial, filhos in alias.sites_por_setorial.items():
            for filho in filhos:
                filho_real = substituicoes.get(filho, filho)

                if filho_real is not canonico:
                    canonico.adicionar_site_setorial(setorial, filho_real)

    for dados_assinatura in assinaturas.values():
        site_principal = dados_assinatura.get("site")

        if site_principal in substituicoes:
            dados_assinatura["site"] = substituicoes[site_principal]

        vinculos_unicos = []
        chaves_vinculos = set()

        for vinculo in dados_assinatura.get("vinculos") or []:
            site_vinculo = substituicoes.get(
                vinculo.get("site"),
                vinculo.get("site")
            )
            vinculo["site"] = site_vinculo
            chave = (
                site_vinculo.nome if site_vinculo else "",
                str(vinculo.get("setorial") or "Direto")
            )

            if chave not in chaves_vinculos:
                chaves_vinculos.add(chave)
                vinculos_unicos.append(vinculo)

        dados_assinatura["vinculos"] = vinculos_unicos

    nomes_alias = {
        alias.nome: canonico
        for alias, canonico in substituicoes.items()
    }

    for site in sites.values():
        for setorial, filhos in list(site.sites_por_setorial.items()):
            filhos_atualizados = []

            for filho in filhos:
                filho_real = substituicoes.get(filho, filho)

                if filho_real is site or filho_real in filhos_atualizados:
                    continue

                filhos_atualizados.append(filho_real)

            site.sites_por_setorial[setorial] = filhos_atualizados

    for equipamento in equipamentos:
        nome_alias = str(equipamento.get("Site") or "")
        canonico = nomes_alias.get(nome_alias)

        if not canonico:
            continue

        equipamento["Site"] = canonico.nome
        arvore = str(equipamento.get("Arvore") or "")

        if arvore == nome_alias or arvore.startswith(f"{nome_alias} >"):
            equipamento["Arvore"] = canonico.nome + arvore[len(nome_alias):]

    enlaces_consolidados = []
    chaves_enlaces = set()

    for enlace in enlaces_sites:
        origem = nomes_alias.get(str(enlace.get("Site Origem") or ""))
        destino = nomes_alias.get(str(enlace.get("Site Destino") or ""))

        if origem:
            enlace["Site Origem"] = origem.nome
            enlace["Tipo Origem"] = origem.tipo

        if destino:
            enlace["Site Destino"] = destino.nome
            enlace["Tipo Destino"] = destino.tipo

        if enlace.get("Site Origem") == enlace.get("Site Destino"):
            continue

        chave = (
            tuple(sorted([
                str(enlace.get("Site Origem") or ""),
                str(enlace.get("Site Destino") or "")
            ])),
            str(enlace.get("ID Link") or ""),
            str(enlace.get("Nome Link") or "")
        )

        if chave not in chaves_enlaces:
            chaves_enlaces.add(chave)
            enlaces_consolidados.append(enlace)

    enlaces_sites[:] = enlaces_consolidados

    for site in sites.values():
        site.enlaces_sites = []

    sites_finais = {
        nome: site
        for nome, site in sites.items()
        if site not in substituicoes
    }

    for enlace in enlaces_sites:
        for campo in ["Site Origem", "Site Destino"]:
            site = sites_finais.get(enlace.get(campo))

            if site and enlace not in site.enlaces_sites:
                site.enlaces_sites.append(enlace)

    return sites_finais


def carregar_dados_dashboard():
    sites, assinaturas, equipamentos, enlaces_sites = importar_estrutura_atual(
        retornar_enlaces=True
    )
    df_topos = carregar_topos()
    aplicar_cadastro_topos(
        sites,
        df_topos
    )
    sites = consolidar_sites_duplicados_cadastro(
        sites,
        assinaturas,
        equipamentos,
        enlaces_sites
    )

    clientes_sem_site, clientes_cancelados, clientes_snmpc_cancelados = importar_clientes(
        CLIENTES_FILE,
        assinaturas,
        retornar_cancelados=True
    )

    sincronizar_banco(sites)

    return {
        "sites": sites,
        "clientes_sem_site": clientes_sem_site,
        "clientes_cancelados": clientes_cancelados,
        "clientes_snmpc_cancelados": clientes_snmpc_cancelados,
        "equipamentos": equipamentos,
        "enlaces_sites": enlaces_sites,
        "totais": {
            "sites": len(sites),
            "sites_cadastro": len(df_topos),
            "assinaturas": len(assinaturas),
            "equipamentos": len(equipamentos),
            "enlaces_sites": len(enlaces_sites),
            "clientes_sem_site": len(clientes_sem_site),
            "clientes_cancelados": len(clientes_cancelados),
            "clientes_snmpc_cancelados": len(clientes_snmpc_cancelados)
        }
    }
