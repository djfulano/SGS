import csv
import re
import unicodedata

from app.logs import registrar_log_sistema
from app.models.site import Site


SITES_IGNORADOS = {
    "MAPA GERAL"
}

TIPOS_ENLACE_SITE = {
    "POP",
    "DC"
}

PREFIXOS_ENLACE_IGNORADOS = {
    "AC",
    "AGS20",
    "ASG20",
    "ALFO",
    "ALFOP2",
    "BB",
    "CERA",
    "CN",
    "FO",
    "GI",
    "IP",
    "IP10",
    "L2",
    "L2LAN",
    "ML",
    "NEO",
    "NEOVIA",
    "OSPF",
    "POP",
    "TN",
    "TXT",
    "UFINET"
}

TIPOS_ESTRUTURA = {
    "Subnet"
}


def eh_setorial(nome):

    return bool(
        re.search(
            r'(^|[_\-\s])S\d+($|[_\-\s])',
            str(nome).upper()
        )
    )


def extrair_setorial_nome(nome):

    match = re.search(
        r'([A-Z0-9]+_S\d+)',
        str(nome).upper()
    )

    if match:

        return match.group(1)

    return None


def normalizar_nome_snmpc(nome):

    nome = str(nome).strip()
    nome = re.sub(
        r'\s+_(IP|MAC)$',
        r'_\1',
        nome,
        flags=re.IGNORECASE
    )

    return re.sub(
        r'_\s*(IP|MAC)$',
        r'_\1',
        nome,
        flags=re.IGNORECASE
    )


def detectar_tipo(linha):

    nome = normalizar_nome_snmpc(
        linha.get("Name", "")
    ).upper()

    if eh_setorial(nome):

        return None

    if re.search(r'(^|[_\-\s])DC($|[_\-\s])', nome):
        return "DC"

    if not re.search(r'_\d+_(IP|MAC)$', nome):

        return None

    if re.search(r'(^|[_\-\s])POP($|[_\-\s])', nome):
        return "POP"

    elif re.search(r'(^|[_\-\s])BH($|[_\-\s])', nome):
        return "BH"

    elif re.search(r'(^|[_\-\s])REP\d*($|[_\-\s])', nome):
        return "REP"

    return None


def extrair_assinatura(texto):

    texto = str(texto).strip()

    match = re.search(r'(\d{8})$', texto)

    if match:
        return match.group(1)

    return None


def remover_acentos(texto):

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFKD",
            str(texto)
        )
        if not unicodedata.combining(caractere)
    )


def extrair_predio(texto):

    texto_normalizado = remover_acentos(texto).upper()

    padroes = [
        r'(?:COD\.?\s*)?PREDIO\s*[:=\-]?\s*(\d{4,8})',
        r'CODIGO\s*(?:DO|DE)?\s*PREDIO\s*[:=\-]?\s*(\d{4,8})'
    ]

    for padrao in padroes:

        match = re.search(
            padrao,
            texto_normalizado
        )

        if match:

            return match.group(1)

    return None


def extrair_parent_id(parent):

    parent = str(parent).strip()

    if not parent or parent == "(NULL)":

        return None

    if parent.isdigit():

        return parent

    match = re.search(r'\((\d+)\)$', parent)

    if match:

        return match.group(1)

    return parent


def caminho_ancestrais(item_id, itens):

    caminho = []

    visitados = set()

    parent_id = itens.get(item_id, {}).get("parent_id")

    while parent_id and parent_id in itens:

        if parent_id in visitados:

            break

        visitados.add(parent_id)

        caminho.append(parent_id)

        parent_id = itens[parent_id]["parent_id"]

    return caminho


def prefixo(nome):

    nome = str(nome).strip().upper()

    if not nome:

        return None

    return re.split(r'[_\-\s]', nome)[0]


def montar_indice_sites(sites):

    indice = {}

    for site in sites.values():

        chave = prefixo(site.nome)

        if not chave:

            continue

        indice.setdefault(
            chave,
            []
        ).append(site)

    return indice


def site_por_prefixo(nome, sites_por_prefixo):

    chave = prefixo(nome)

    if not chave:

        return None

    candidatos = sites_por_prefixo.get(
        chave,
        []
    )

    if not candidatos:

        return None

    prioridade = {
        "POP": 0,
        "DC": 1,
        "BH": 2,
        "REP": 3
    }

    return sorted(
        candidatos,
        key=lambda site: prioridade.get(site.tipo, 99)
    )[0]


def primeiro_site_ancestral(item_id, sites_por_id, itens):

    for ancestral_id in caminho_ancestrais(item_id, itens):

        if ancestral_id in sites_por_id:

            return sites_por_id[ancestral_id]

    return None


def site_mais_proximo(item_id, sites_por_id, itens, sites_por_prefixo):

    if item_id in sites_por_id:

        return sites_por_id[item_id]

    site_ancestral = primeiro_site_ancestral(
        item_id,
        sites_por_id,
        itens
    )

    if site_ancestral:

        return site_ancestral

    item = itens.get(item_id)

    if not item:

        return None

    # Fallback apenas para agrupadores/setoriais sem site ancestral no TXT.
    referencias = [
        itens[ancestral_id]["nome"]
        for ancestral_id in caminho_ancestrais(item_id, itens)
        if ancestral_id in itens
    ]

    if not extrair_assinatura(item["nome"]):

        referencias.insert(
            0,
            item["nome"]
        )

    for referencia in referencias:

        site = site_por_prefixo(
            referencia,
            sites_por_prefixo
        )

        if site:

            return site

    return None


def setorial_mais_proximo(item_id, itens):

    item = itens.get(item_id)

    if item and eh_setorial(item["nome"]):

        return item["nome"]

    for ancestral_id in caminho_ancestrais(item_id, itens):

        ancestral = itens.get(ancestral_id)

        if ancestral and eh_setorial(ancestral["nome"]):

            return ancestral["nome"]

    return None


def assinatura_mais_proxima(item_id, itens):

    item = itens.get(item_id)

    if item:

        assinatura = extrair_assinatura(item["nome"])

        if assinatura:

            return assinatura, item["nome"]

    for ancestral_id in caminho_ancestrais(item_id, itens):

        ancestral = itens.get(ancestral_id)

        if not ancestral:

            continue

        assinatura = extrair_assinatura(ancestral["nome"])

        if assinatura:

            return assinatura, ancestral["nome"]

    return None, None


def extrair_endpoints_network(linha):
    for valor in linha.values():
        texto = str(valor or "").strip()

        if "," not in texto:
            continue

        endpoints = re.findall(
            r'([^(),]+)\((\d+)\)',
            texto
        )

        if len(endpoints) >= 2:
            origem = endpoints[0]
            destino = endpoints[-1]

            return {
                "origem_nome": origem[0].strip(),
                "origem_id": origem[1].strip(),
                "destino_nome": destino[0].strip(),
                "destino_id": destino[1].strip(),
                "bruto": texto
            }

    return None


def tipo_enlace_sites(site_origem, site_destino):
    tipos = {
        str(getattr(site_origem, "tipo", "") or "").upper(),
        str(getattr(site_destino, "tipo", "") or "").upper()
    }

    if tipos == {"POP"}:
        return "POP x POP"

    if tipos == {"DC"}:
        return "DC x DC"

    if tipos == {"POP", "DC"}:
        return "POP x DC"

    return "Site x Site"


def texto_enlace_sites(texto, sites_por_prefixo):
    sites = []
    vistos = set()
    texto = remover_acentos(texto).upper()

    for token in re.split(r'[^A-Z0-9]+', texto):
        token = token.strip()

        if (
            not token
            or len(token) < 3
            or token.isdigit()
            or token in PREFIXOS_ENLACE_IGNORADOS
        ):
            continue

        site = site_por_prefixo(
            token,
            sites_por_prefixo
        )

        if not site:
            continue

        if str(site.tipo).upper() not in TIPOS_ENLACE_SITE:
            continue

        if site.nome in vistos:
            continue

        vistos.add(site.nome)
        sites.append(site)

    return sites


def adicionar_enlace_site(
    enlaces,
    chaves,
    site_origem,
    site_destino,
    dados,
    chave_extra=None
):
    if not site_origem or not site_destino:
        return False

    if site_origem.nome == site_destino.nome:
        return False

    par_sites = tuple(
        sorted([
            site_origem.nome,
            site_destino.nome
        ])
    )
    chave = (
        par_sites,
        str(chave_extra or dados.get("ID Link") or ""),
        str(dados.get("Nome Link") or "")
    )

    if chave in chaves:
        return False

    chaves.add(chave)
    tipo = tipo_enlace_sites(
        site_origem,
        site_destino
    )
    enlace = {
        "Tipo Enlace": tipo,
        "Nome Link": dados.get("Nome Link") or "",
        "Site Origem": site_origem.nome,
        "Site Destino": site_destino.nome,
        "Tipo Origem": site_origem.tipo,
        "Tipo Destino": site_destino.tipo,
        "ID Link": dados.get("ID Link") or "",
        "Parent SNMPc": dados.get("Parent SNMPc") or "",
        "Parent ID": dados.get("Parent ID") or "",
        "Origem Endpoint": dados.get("Origem Endpoint") or site_origem.nome,
        "Origem ID": dados.get("Origem ID") or "",
        "Destino Endpoint": dados.get("Destino Endpoint") or site_destino.nome,
        "Destino ID": dados.get("Destino ID") or "",
        "Endpoints": dados.get("Endpoints") or "",
        "Status": dados.get("Status") or "",
        "Icone": dados.get("Icone") or "",
        "Endereco": dados.get("Endereco") or "",
        "Origem Dados": dados.get("Origem Dados") or "Network"
    }
    site_origem.enlaces_sites.append(enlace)
    site_destino.enlaces_sites.append(enlace)
    enlaces.append(enlace)
    return True


def montar_enlaces_network_sites(networks, sites_por_id, itens, sites_por_prefixo, enlaces=None, chaves=None):
    enlaces = enlaces if enlaces is not None else []
    chaves = chaves if chaves is not None else set()

    for network in networks:
        endpoints = extrair_endpoints_network(
            network["linha"]
        )

        if not endpoints:
            continue

        site_origem = site_mais_proximo(
            endpoints["origem_id"],
            sites_por_id,
            itens,
            sites_por_prefixo
        )
        site_destino = site_mais_proximo(
            endpoints["destino_id"],
            sites_por_id,
            itens,
            sites_por_prefixo
        )

        adicionar_enlace_site(
            enlaces,
            chaves,
            site_origem,
            site_destino,
            {
            "Nome Link": network.get("nome") or "",
            "ID Link": network.get("id") or "",
            "Parent SNMPc": network.get("parent") or "",
            "Parent ID": network.get("parent_id") or "",
            "Origem Endpoint": endpoints["origem_nome"],
            "Origem ID": endpoints["origem_id"],
            "Destino Endpoint": endpoints["destino_nome"],
            "Destino ID": endpoints["destino_id"],
            "Endpoints": endpoints["bruto"],
            "Status": network.get("status") or "",
            "Icone": network.get("icon") or "",
            "Endereco": network.get("address") or "",
            "Origem Dados": "Network"
            }
        )

    return enlaces


def montar_enlaces_dispositivos_sites(dispositivos, sites_por_id, itens, sites_por_prefixo, enlaces=None, chaves=None):
    enlaces = enlaces if enlaces is not None else []
    chaves = chaves if chaves is not None else set()

    for dispositivo in dispositivos:
        parent_id = dispositivo.get("parent_id")
        site_parent = site_mais_proximo(
            parent_id,
            sites_por_id,
            itens,
            sites_por_prefixo
        ) if parent_id else None

        texto_referencia = " ".join(
            str(dispositivo.get(campo) or "")
            for campo in [
                "nome",
                "address",
                "parent",
                "icon",
                "group1",
                "group2"
            ]
        )
        sites_texto = texto_enlace_sites(
            texto_referencia,
            sites_por_prefixo
        )

        candidatos = []
        vistos = set()

        for site in [site_parent, *sites_texto]:
            if not site:
                continue

            if str(site.tipo).upper() not in TIPOS_ENLACE_SITE:
                continue

            if site.nome in vistos:
                continue

            vistos.add(site.nome)
            candidatos.append(site)

        if len(candidatos) < 2:
            continue

        origem = site_parent if site_parent in candidatos else candidatos[0]

        for destino in candidatos:
            if destino.nome == origem.nome:
                continue

            adicionar_enlace_site(
                enlaces,
                chaves,
                origem,
                destino,
                {
                    "Nome Link": dispositivo.get("nome") or "",
                    "ID Link": dispositivo.get("id") or "",
                    "Parent SNMPc": dispositivo.get("parent") or "",
                    "Parent ID": dispositivo.get("parent_id") or "",
                    "Origem Endpoint": origem.nome,
                    "Origem ID": "",
                    "Destino Endpoint": destino.nome,
                    "Destino ID": "",
                    "Endpoints": dispositivo.get("nome") or "",
                    "Status": dispositivo.get("status") or "",
                    "Icone": dispositivo.get("icon") or "",
                    "Endereco": dispositivo.get("address") or "",
                    "Origem Dados": "Device"
                }
            )

    return enlaces


def site_por_setorial(item_id, itens, sites_por_prefixo):

    setorial = setorial_mais_proximo(
        item_id,
        itens
    )

    if not setorial:

        return None

    return site_por_prefixo(
        setorial,
        sites_por_prefixo
    )


def aplicar_links_goto_setoriais(itens, links_goto):

    ids_por_nome = {}

    for item_id, item in itens.items():

        ids_por_nome.setdefault(
            item["nome"].strip().upper(),
            []
        ).append(item_id)

    for link in links_goto:

        nome_destino = link["destino"].strip().upper()
        parent_id = link["parent_id"]

        if not nome_destino or parent_id not in itens:

            continue

        parent = itens[parent_id]

        if not parent.get("tipo"):

            continue

        for item_id in ids_por_nome.get(nome_destino, []):

            item = itens[item_id]

            if not eh_setorial(item["nome"]):

                continue

            if item_id in caminho_ancestrais(parent_id, itens):

                continue

            item["parent_id"] = parent_id


def importar_estrutura_de_linhas(linhas, retornar_enlaces=False):

    itens = {}

    dispositivos = []

    networks = []

    links_goto = []

    mapa_geral_parent_id = None

    for linha in linhas:

        nome = normalizar_nome_snmpc(
            linha.get("Name", "")
        )

        item_id = str(
            linha.get("ID", "")
        ).strip()

        if not nome or not item_id:

            continue

        tipo_item = linha.get("Type", "").strip()

        parent_id = extrair_parent_id(
            linha.get("Parent", "")
        )

        if tipo_item == "Goto":

            destino = (
                linha.get("Address", "").strip()
                or nome
            )

            if destino and parent_id:

                links_goto.append(
                    {
                        "nome": nome,
                        "destino": destino,
                        "parent_id": parent_id
                    }
                )

            continue

        if tipo_item == "Device":

            dispositivos.append({
                "id": item_id,
                "nome": nome,
                "address": linha.get("Address", "").strip(),
                "icon": linha.get("Icon", "").strip(),
                "group1": linha.get("Group1", "").strip(),
                "group2": linha.get("Group2", "").strip(),
                "parent_id": parent_id,
                "parent": linha.get("Parent", "").strip(),
                "status": linha.get("Status", "").strip(),
                "predio": extrair_predio(
                    linha.get("Description", "")
                )
            })

            continue

        if tipo_item == "Network":

            networks.append({
                "id": item_id,
                "nome": nome,
                "address": linha.get("Address", "").strip(),
                "icon": linha.get("Icon", "").strip(),
                "parent_id": parent_id,
                "parent": linha.get("Parent", "").strip(),
                "status": linha.get("Status", "").strip(),
                "linha": linha
            })

            continue

        if tipo_item not in TIPOS_ESTRUTURA:

            continue

        if nome in SITES_IGNORADOS:

            mapa_geral_parent_id = parent_id

            continue

        itens[item_id] = {
            "id": item_id,
            "nome": nome,
            "linha": linha,
            "parent_id": parent_id,
            "tipo": detectar_tipo(linha),
            "predio": extrair_predio(
                linha.get("Description", "")
            )
        }

    if mapa_geral_parent_id:

        for item in itens.values():

            if item["parent_id"] and item["parent_id"] not in itens:

                item["parent_id"] = mapa_geral_parent_id

    aplicar_links_goto_setoriais(
        itens,
        links_goto
    )

    sites_por_id = {}

    for item_id, item in itens.items():

        if not item["tipo"]:

            continue

        sites_por_id[item_id] = Site(
            item["nome"],
            item["tipo"],
            predio=item.get("predio")
        )

    sites_por_nome = {
        site.nome: site
        for site in sites_por_id.values()
    }

    sites_por_prefixo = montar_indice_sites(
        sites_por_nome
    )

    for item_id, site in sites_por_id.items():

        parent_site = primeiro_site_ancestral(
            item_id,
            sites_por_id,
            itens
        )

        setorial = setorial_mais_proximo(
            item_id,
            itens
        )

        if not parent_site:

            parent_site = site_por_setorial(
                item_id,
                itens,
                sites_por_prefixo
            )

        if parent_site and setorial:

            parent_site.adicionar_site_setorial(
                setorial,
                site
            )

        if parent_site:

            parent_site.adicionar_filho(site)

    assinaturas = {}
    vinculos_por_assinatura = {}

    def adicionar_vinculo_assinatura(assinatura, vinculo):
        vinculos = vinculos_por_assinatura.setdefault(
            assinatura,
            []
        )
        chave = (
            vinculo["site"].nome,
            str(vinculo.get("setorial") or "Direto")
        )

        for existente in vinculos:
            chave_existente = (
                existente["site"].nome,
                str(existente.get("setorial") or "Direto")
            )

            if chave_existente == chave:
                return False

        vinculos.append(vinculo)
        return True

    for item_id, item in itens.items():

        assinatura_cliente = extrair_assinatura(
            item["nome"]
        )

        if not assinatura_cliente:

            continue

        site = site_mais_proximo(
            item_id,
            sites_por_id,
            itens,
            sites_por_prefixo
        )

        if not site:

            continue

        setorial = setorial_mais_proximo(
            item_id,
            itens
        )

        adicionar_vinculo_assinatura(assinatura_cliente, {
            "site": site,
            "setorial": setorial,
            "origem": item["nome"],
            "predio": item.get("predio"),
            "origem_tipo": "Subnet"
        })

    for link_goto in links_goto:
        assinatura_cliente = (
            extrair_assinatura(link_goto.get("destino"))
            or extrair_assinatura(link_goto.get("nome"))
        )

        if not assinatura_cliente:
            continue

        parent_id = link_goto.get("parent_id")
        site = site_mais_proximo(
            parent_id,
            sites_por_id,
            itens,
            sites_por_prefixo
        )

        if not site:
            continue

        adicionar_vinculo_assinatura(assinatura_cliente, {
            "site": site,
            "setorial": setorial_mais_proximo(parent_id, itens),
            "origem": link_goto.get("destino") or link_goto.get("nome"),
            "predio": None,
            "origem_tipo": "Goto"
        })

    assinaturas_multiplos_vinculos = {}
    assinaturas_multiplos_nos_reais = {}

    for assinatura_cliente, vinculos in vinculos_por_assinatura.items():
        indice_principal = next(
            (
                indice
                for indice, vinculo in enumerate(vinculos)
                if vinculo.get("origem_tipo") == "Subnet"
            ),
            0
        )
        principal = vinculos[indice_principal]
        vinculos_ordenados = [principal] + [
            vinculo
            for indice, vinculo in enumerate(vinculos)
            if indice != indice_principal
        ]
        vinculos_normalizados = []
        nos_reais = [
            vinculo
            for vinculo in vinculos_ordenados
            if vinculo.get("origem_tipo") == "Subnet"
        ]

        if len(nos_reais) > 1:
            assinaturas_multiplos_nos_reais[assinatura_cliente] = [
                {
                    "site": vinculo["site"].nome,
                    "setorial": vinculo.get("setorial"),
                    "origem": vinculo.get("origem")
                }
                for vinculo in nos_reais
            ]

        for indice, vinculo in enumerate(vinculos_ordenados):
            tipo_vinculo = "Principal" if indice == 0 else "Adicional"
            vinculo_normalizado = {
                **vinculo,
                "predio": vinculo.get("predio") or principal.get("predio"),
                "tipo": tipo_vinculo
            }
            vinculos_normalizados.append(vinculo_normalizado)
            site = vinculo_normalizado["site"]

            if assinatura_cliente not in site.assinaturas:
                site.assinaturas.append(assinatura_cliente)

            site.adicionar_cliente_estrutura(
                vinculo_normalizado.get("origem") or "",
                assinatura_cliente,
                predio=vinculo_normalizado.get("predio"),
                setorial=vinculo_normalizado.get("setorial"),
                tipo_vinculo=tipo_vinculo
            )

        assinaturas[assinatura_cliente] = {
            **principal,
            "tipo": "Principal",
            "vinculos": vinculos_normalizados
        }

        if len(vinculos_normalizados) > 1:
            assinaturas_multiplos_vinculos[assinatura_cliente] = [
                {
                    "site": vinculo["site"].nome,
                    "setorial": vinculo.get("setorial"),
                    "tipo": vinculo.get("tipo")
                }
                for vinculo in vinculos_normalizados
            ]

    if assinaturas_multiplos_vinculos:
        exemplos = []

        for assinatura, vinculos in list(
            assinaturas_multiplos_vinculos.items()
        )[:10]:
            locais = ", ".join(
                (
                    f"{vinculo['site']} / "
                    f"{vinculo.get('setorial') or 'Direto'} "
                    f"({vinculo.get('tipo')})"
                )
                for vinculo in vinculos
            )
            exemplos.append(f"{assinatura}: {locais}")

        registrar_log_sistema(
            "assinaturas_multiplos_vinculos_snmpc",
            status="sucesso",
            detalhes={
                "quantidade": len(assinaturas_multiplos_vinculos),
                "exemplos": exemplos
            }
        )

    if assinaturas_multiplos_nos_reais:
        registrar_log_sistema(
            "assinaturas_multiplos_nos_reais_snmpc",
            status="aviso",
            detalhes={
                "quantidade": len(assinaturas_multiplos_nos_reais),
                "assinaturas": assinaturas_multiplos_nos_reais
            }
        )

    equipamentos = []

    for dispositivo in dispositivos:

        parent_id = dispositivo.get("parent_id")

        if not parent_id:

            continue

        site = site_mais_proximo(
            parent_id,
            sites_por_id,
            itens,
            sites_por_prefixo
        )

        if not site:

            continue

        parent_item = itens.get(parent_id)
        setorial = (
            setorial_mais_proximo(
                parent_id,
                itens
            )
            or extrair_setorial_nome(dispositivo["nome"])
            or "Direto"
        )
        parent_nome = (
            parent_item["nome"]
            if parent_item
            else dispositivo["parent"]
        )
        assinatura, cliente_estrutura = assinatura_mais_proxima(
            parent_id,
            itens
        )

        equipamento = {
            "ID": dispositivo["id"],
            "Arvore": " > ".join(
                parte
                for parte in [
                    site.nome,
                    setorial,
                    dispositivo["icon"],
                    parent_nome,
                    dispositivo["nome"]
                ]
                if parte
            ),
            "Equipamento": dispositivo["nome"],
            "Endereco": dispositivo["address"],
            "Icone": dispositivo["icon"],
            "Grupo1": dispositivo["group1"],
            "Grupo2": dispositivo["group2"],
            "Status": dispositivo["status"],
            "Predio": dispositivo["predio"],
            "Site": site.nome,
            "Setorial": setorial,
            "Parent": parent_nome,
            "Assinatura": assinatura or "",
            "Cliente Estrutura": cliente_estrutura or ""
        }

        site.adicionar_equipamento(equipamento)

        equipamentos.append(equipamento)

    itens_para_enlaces = dict(itens)

    for dispositivo in dispositivos:
        itens_para_enlaces[dispositivo["id"]] = {
            "id": dispositivo["id"],
            "nome": dispositivo["nome"],
            "parent_id": dispositivo.get("parent_id"),
            "tipo": None
        }

    enlaces_sites = montar_enlaces_network_sites(
        networks,
        sites_por_id,
        itens_para_enlaces,
        sites_por_prefixo
    )
    montar_enlaces_dispositivos_sites(
        dispositivos,
        sites_por_id,
        itens_para_enlaces,
        sites_por_prefixo,
        enlaces_sites,
        set(
            (
                tuple(sorted([enlace["Site Origem"], enlace["Site Destino"]])),
                str(enlace.get("ID Link") or ""),
                str(enlace.get("Nome Link") or "")
            )
            for enlace in enlaces_sites
        )
    )

    if retornar_enlaces:
        return sites_por_nome, assinaturas, equipamentos, enlaces_sites

    return sites_por_nome, assinaturas, equipamentos


def importar_estrutura(caminho_arquivo, retornar_enlaces=False):

    with open(caminho_arquivo, "r", encoding="latin1") as arquivo:

        leitor = csv.DictReader(
            arquivo,
            delimiter=","
        )

        return importar_estrutura_de_linhas(
            leitor,
            retornar_enlaces=retornar_enlaces
        )
