import re
import unicodedata

import pandas as pd

from app.services.equipment_catalog import load_equipment_catalog
from app.services.product_catalog import load_product_catalog
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import custo_indireto_site
from app.services.site_metrics import custo_site
from app.services.site_metrics import montar_metricas_banda_telecom_site
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import sites_descendentes
from app.services.site_registry_service import load_site_registry


def _texto(valor):
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()
    return texto[:-2] if texto.endswith(".0") else texto


def _numero(valor):
    if isinstance(valor, str):
        texto = valor.replace("R$", "").strip()

        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        valor = texto

    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", _texto(valor))
    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold()


def _normalizar_codigo(valor):
    texto = _texto(valor)
    return re.sub(r"\D+", "", texto) or texto.casefold()


def _indices_sites_topologia(sites):
    indices = {
        "aquiles": {},
        "snmpc": {},
        "microsiga": {},
    }

    for site in (sites or {}).values():
        codigo = _normalizar_codigo(getattr(site, "codigo_topos", ""))
        nome = _normalizar(getattr(site, "nome", ""))
        microsiga = _normalizar_codigo(getattr(site, "microsiga", ""))

        if codigo:
            indices["aquiles"].setdefault(codigo, site)
        if nome:
            indices["snmpc"].setdefault(nome, site)
        if microsiga:
            indices["microsiga"].setdefault(microsiga, site)

    return indices


def _localizar_site_topologia(registro, indices):
    codigo = _normalizar_codigo(registro.get("codigo_topos"))
    nome = _normalizar(registro.get("nome"))
    microsiga = _normalizar_codigo(registro.get("microsiga"))

    return (
        indices["aquiles"].get(codigo)
        or indices["snmpc"].get(nome)
        or indices["microsiga"].get(microsiga)
    )


def _chave_opcao_site(registro, indice):
    for prefixo, campo, normalizador in [
        ("aquiles", "codigo_topos", _normalizar_codigo),
        ("snmpc", "nome", _normalizar),
        ("microsiga", "microsiga", _normalizar_codigo),
    ]:
        valor = normalizador(registro.get(campo))

        if valor:
            return f"{prefixo}:{valor}:{indice}"

    return f"cadastro:{indice}"


def montar_opcoes_sites_pre_venda(sites, cadastro=None):
    cadastro = load_site_registry() if cadastro is None else cadastro.copy()
    indices = _indices_sites_topologia(sites)
    opcoes = {}
    sites_vinculados = set()

    if cadastro is not None and not cadastro.empty:
        for indice, linha in enumerate(cadastro.to_dict(orient="records")):
            registro = {
                "nome": _texto(linha.get("SMNPC")),
                "codigo_topos": _texto(linha.get("CÓDIGO AQUILES")),
                "nome_cadastro": _texto(linha.get("NOME")),
                "microsiga": _texto(linha.get("CÓDIGO MICROSIGA")),
                "status_cadastro": _texto(linha.get("Status")),
                "tipo": _texto(linha.get("TIPO")),
                "custo_direto": sum(
                    _numero(linha.get(coluna))
                    for coluna in ["LOCAÇÃO", "ENERGIA", "OUTROS"]
                ),
            }
            site_topologia = _localizar_site_topologia(registro, indices)
            registro["site_topologia"] = site_topologia

            if site_topologia is not None:
                sites_vinculados.add(id(site_topologia))

            opcoes[_chave_opcao_site(registro, indice)] = registro

    for indice, site in enumerate((sites or {}).values()):
        if id(site) in sites_vinculados:
            continue

        registro = {
            "nome": _texto(getattr(site, "nome", "")),
            "codigo_topos": _texto(getattr(site, "codigo_topos", "")),
            "nome_cadastro": _texto(getattr(site, "nome_cadastro", "")),
            "microsiga": _texto(getattr(site, "microsiga", "")),
            "status_cadastro": _texto(
                getattr(site, "status_cadastro", "")
            ),
            "tipo": _texto(getattr(site, "tipo", "")),
            "custo_direto": custo_site(site),
            "site_topologia": site,
        }
        chave = f"topologia:{_normalizar(site.nome)}:{indice}"
        opcoes[chave] = registro

    return opcoes


def _catalogo_equipamentos_por_icone(catalogo):
    if catalogo is None or catalogo.empty:
        return {}

    return {
        _texto(linha.get("Ícone")): linha
        for linha in catalogo.to_dict(orient="records")
        if _texto(linha.get("Ícone"))
    }


def _tipo_radio(tipo):
    return "radio" in _normalizar(tipo)


def _nome_radio(equipamento, cadastro):
    return (
        _texto(cadastro.get("Modelo"))
        or _texto(cadastro.get("Nome"))
        or _texto(equipamento.get("Icone"))
        or "Não localizado"
    )


def listar_radios_infraestrutura_site(site, catalogo=None):
    if site is None:
        return []

    catalogo = load_equipment_catalog() if catalogo is None else catalogo
    por_icone = _catalogo_equipamentos_por_icone(catalogo)
    radios = []

    for equipamento in getattr(site, "equipamentos", []):
        if _texto(equipamento.get("Assinatura")):
            continue

        icone = _texto(equipamento.get("Icone"))
        cadastro = por_icone.get(icone, {})

        if not _tipo_radio(cadastro.get("Tipo")):
            continue

        radios.append({
            "equipamento": equipamento,
            "nome": _nome_radio(equipamento, cadastro),
        })

    return radios


def _setoriais_enlace_pai(site):
    pai = getattr(site, "pai", None)

    if pai is None:
        return set()

    return {
        _texto(setorial)
        for setorial, filhos in getattr(pai, "sites_por_setorial", {}).items()
        if any(
            filho is site
            or _normalizar(getattr(filho, "nome", ""))
            == _normalizar(getattr(site, "nome", ""))
            for filho in filhos
        )
    }


def identificar_radio_principal(site, radios=None, catalogo=None):
    radios = (
        listar_radios_infraestrutura_site(site, catalogo)
        if radios is None
        else radios
    )
    setoriais_pai = _setoriais_enlace_pai(site)

    if not setoriais_pai:
        return "Não localizado"

    for radio in radios:
        setorial = _texto(radio["equipamento"].get("Setorial"))

        if setorial in setoriais_pai:
            return radio["nome"]

    return "Não localizado"


def montar_resumo_pre_venda(
    registro,
    catalogo_produtos=None,
    catalogo_equipamentos=None,
):
    site = registro.get("site_topologia")
    status = _texto(registro.get("status_cadastro")) or "Não informado"

    if site is None:
        return {
            "status": status,
            "clientes_total": 0,
            "receita_total": 0.0,
            "sites_filhos": 0,
            "clientes_diretos": 0,
            "receita_direta": 0.0,
            "clientes_indiretos": 0,
            "receita_indireta": 0.0,
            "custo_direto": _numero(registro.get("custo_direto")),
            "custo_indireto": 0.0,
            "custo_total": _numero(registro.get("custo_direto")),
            "maior_banda_mbps": None,
            "soma_banda_mbps": 0.0,
            "produtos_100_mbps": 0,
            "radio_principal": "Não localizado",
            "radios_instalados": 0,
        }

    catalogo_produtos = (
        load_product_catalog()
        if catalogo_produtos is None
        else catalogo_produtos
    )
    catalogo_equipamentos = (
        load_equipment_catalog()
        if catalogo_equipamentos is None
        else catalogo_equipamentos
    )
    clientes_diretos = len(site.clientes)
    clientes_indiretos = clientes_indiretos_site(site)
    receita_direta = receita_site(site)
    receita_indireta = receita_indireta_site(site)
    custo_direto = custo_site(site)
    custo_indireto = custo_indireto_site(site)
    descendentes = sites_descendentes(site)
    bandas = montar_metricas_banda_telecom_site(site, catalogo_produtos)
    radios = listar_radios_infraestrutura_site(site, catalogo_equipamentos)

    return {
        "status": status,
        "clientes_total": clientes_diretos + clientes_indiretos,
        "receita_total": receita_direta + receita_indireta,
        "sites_filhos": max(0, len(descendentes) - 1),
        "clientes_diretos": clientes_diretos,
        "receita_direta": receita_direta,
        "clientes_indiretos": clientes_indiretos,
        "receita_indireta": receita_indireta,
        "custo_direto": custo_direto,
        "custo_indireto": custo_indireto,
        "custo_total": custo_direto + custo_indireto,
        "maior_banda_mbps": bandas["maior_mbps"],
        "soma_banda_mbps": bandas["soma_mbps"],
        "produtos_100_mbps": bandas["acima_100_mbps"],
        "radio_principal": identificar_radio_principal(
            site,
            radios=radios,
        ),
        "radios_instalados": len(radios),
    }
