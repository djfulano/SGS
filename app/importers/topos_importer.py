import re
import unicodedata
from pathlib import Path

import pandas as pd

from app.config import IMPORTS_DIR

SITES_FILE = IMPORTS_DIR / "Sites.xlsx"
TOPOS_FILE = SITES_FILE


def caminho_sites_excel():

    for caminho in [
        IMPORTS_DIR / "Sites.xlsx",
        IMPORTS_DIR / "Sites.xls",
        IMPORTS_DIR / "sites.xlsx",
        IMPORTS_DIR / "sites.xls",
        IMPORTS_DIR / "topos.xlsx"
    ]:

        if caminho.exists():

            return caminho

    return SITES_FILE


def normalizar_texto(valor):

    if pd.isna(valor):

        return ""

    texto = str(valor).strip()
    texto = unicodedata.normalize(
        "NFKD",
        texto
    ).encode(
        "ascii",
        "ignore"
    ).decode(
        "ascii"
    )

    return texto


def chave_coluna(coluna):

    texto = normalizar_texto(coluna).upper()

    return re.sub(
        r"[^A-Z0-9]+",
        "",
        texto
    )


def valor_texto(valor):

    if pd.isna(valor):

        return ""

    return str(valor).strip()


def valor_codigo(valor):

    if pd.isna(valor):

        return ""

    if isinstance(valor, float) and valor.is_integer():

        return str(int(valor))

    texto = str(valor).strip()

    if texto.endswith(".0"):

        return texto[:-2]

    return texto


def valor_numero(valor):

    if pd.isna(valor):

        return 0.0

    if isinstance(valor, str):

        valor = (
            valor
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

    try:

        return float(valor)

    except (TypeError, ValueError):

        return 0.0


def valor_coordenada(valor, limite=180):

    if pd.isna(valor):

        return 0.0

    if isinstance(valor, str):

        texto = (
            valor
            .replace("R$", "")
            .strip()
        )

        if "," in texto and "." in texto:

            texto = texto.replace(".", "").replace(",", ".")

        elif "," in texto:

            texto = texto.replace(",", ".")

        valor = texto

    try:

        coordenada = float(valor)

        while abs(coordenada) > limite:

            coordenada = coordenada / 10

        return coordenada

    except (TypeError, ValueError):

        return 0.0


def separar_endereco_numero(endereco, numero=""):
    endereco = valor_texto(endereco)
    numero = valor_codigo(numero)

    if numero:
        return endereco, numero

    match = re.match(
        r"^(?P<endereco>.+?),\s*(?P<numero>[^,]+)$",
        endereco
    )

    if not match:
        return endereco, numero

    return (
        match.group("endereco").strip(),
        match.group("numero").strip()
    )


def obter_coluna(colunas, *nomes):

    for nome in nomes:

        chave = chave_coluna(nome)

        if chave in colunas:

            return colunas[chave]

    return None


def obter_coluna_tipo_site(df):

    tipos_validos = {
        "POP",
        "BH",
        "REP",
        "DC"
    }

    for coluna in df.columns:

        if chave_coluna(coluna) != "TIPO":

            continue

        valores = {
            valor_texto(valor).upper()
            for valor in df[coluna].dropna().unique()
        }

        if valores & tipos_validos:

            return coluna

    return obter_coluna(
        {
            chave_coluna(coluna): coluna
            for coluna in df.columns
        },
        "TIPO"
    )


def carregar_topos(caminho=None):

    caminho = Path(caminho) if caminho else caminho_sites_excel()

    if not caminho.exists():

        return pd.DataFrame()

    df = pd.read_excel(caminho)

    colunas = {
        chave_coluna(coluna): coluna
        for coluna in df.columns
    }

    coluna_codigo = obter_coluna(
        colunas,
        "CODIGO AQUILES",
        "CODIGO"
    )
    coluna_microsiga = obter_coluna(
        colunas,
        "CODIGO MICROSIGA",
        "MICROSIGA"
    )
    coluna_codigo_condominio = obter_coluna(
        colunas,
        "CODIGO CONDOMINIO",
        "CONDOMINIO"
    )
    coluna_abreviacao = obter_coluna(
        colunas,
        "ABREVIACAO",
        "ABREVIAÇÃO"
    )
    coluna_snmpc = obter_coluna(
        colunas,
        "SNMPC",
        "SMNPC"
    )
    coluna_tipo = obter_coluna_tipo_site(df)
    coluna_nome = obter_coluna(
        colunas,
        "NOME"
    )
    coluna_custo = obter_coluna(
        colunas,
        "CUSTO"
    )
    coluna_status = obter_coluna(
        colunas,
        "STATUS"
    )
    coluna_relacionamento = obter_coluna(
        colunas,
        "RELACIONAMENTO"
    )
    coluna_favorecido = obter_coluna(
        colunas,
        "FAVORECIDO"
    )
    coluna_endereco = obter_coluna(
        colunas,
        "ENDERECO"
    )
    coluna_numero = obter_coluna(
        colunas,
        "NUMERO",
        "NÚMERO"
    )
    coluna_bairro = obter_coluna(
        colunas,
        "BAIRRO"
    )
    coluna_cidade = obter_coluna(
        colunas,
        "CIDADE"
    )
    coluna_uf = obter_coluna(
        colunas,
        "UF"
    )
    coluna_cep = obter_coluna(
        colunas,
        "CEP"
    )
    coluna_ativacao = obter_coluna(
        colunas,
        "ATIVACAO"
    )
    coluna_latitude = obter_coluna(
        colunas,
        "LATITUDE"
    )
    coluna_longitude = obter_coluna(
        colunas,
        "LONGITUDE"
    )
    coluna_contrato = obter_coluna(
        colunas,
        "CONTRATO"
    )
    coluna_qtdo = obter_coluna(
        colunas,
        "QTDO"
    )
    coluna_categoria = obter_coluna(
        colunas,
        "CATEGORIA"
    )
    coluna_perfil = obter_coluna(
        colunas,
        "PERFIL"
    )
    coluna_altura = obter_coluna(
        colunas,
        "ALTURA"
    )
    coluna_restricao = obter_coluna(
        colunas,
        "RESTRICAO"
    )
    coluna_detalhe = obter_coluna(
        colunas,
        "DETALHE"
    )
    coluna_observacao = obter_coluna(
        colunas,
        "OBSERVACAO"
    )
    coluna_contato_principal = obter_coluna(
        colunas,
        "CONTATO PRINCIPAL"
    )
    coluna_telefone_contato = obter_coluna(
        colunas,
        "TELEFONE CONTATO",
        "TELEFONE"
    )
    coluna_email_contato = obter_coluna(
        colunas,
        "EMAIL CONTATO",
        "E-MAIL CONTATO",
        "EMAIL"
    )
    coluna_outros_contatos = obter_coluna(
        colunas,
        "OUTROS CONTATOS",
        "CONTATOS"
    )

    registros = []

    for _, linha in df.iterrows():

        codigo = valor_codigo(
            linha.get(coluna_codigo)
            if coluna_codigo
            else ""
        )
        snmpc = valor_texto(
            linha.get(coluna_snmpc)
            if coluna_snmpc
            else ""
        )

        if not codigo and not snmpc:

            continue

        endereco, numero = separar_endereco_numero(
            linha.get(coluna_endereco)
            if coluna_endereco
            else "",
            linha.get(coluna_numero)
            if coluna_numero
            else ""
        )

        registros.append({
            "Codigo": codigo,
            "Microsiga": valor_codigo(
                linha.get(coluna_microsiga)
                if coluna_microsiga
                else ""
            ),
            "Codigo Condominio": valor_codigo(
                linha.get(coluna_codigo_condominio)
                if coluna_codigo_condominio
                else ""
            ),
            "Abreviacao": valor_texto(
                linha.get(coluna_abreviacao)
                if coluna_abreviacao
                else ""
            ),
            "SNMPc": snmpc,
            "Tipo Cadastro": valor_texto(
                linha.get(coluna_tipo)
                if coluna_tipo
                else ""
            ).upper(),
            "Nome Cadastro": valor_texto(
                linha.get(coluna_nome)
                if coluna_nome
                else ""
            ),
            "Custo": valor_numero(
                linha.get(coluna_custo)
                if coluna_custo
                else 0
            ),
            "Status Cadastro": valor_texto(
                linha.get(coluna_status)
                if coluna_status
                else ""
            ),
            "Relacionamento": valor_texto(
                linha.get(coluna_relacionamento)
                if coluna_relacionamento
                else ""
            ),
            "Favorecido": valor_texto(
                linha.get(coluna_favorecido)
                if coluna_favorecido
                else ""
            ),
            "Contrato": valor_texto(
                linha.get(coluna_contrato)
                if coluna_contrato
                else ""
            ),
            "Qtdo": valor_numero(
                linha.get(coluna_qtdo)
                if coluna_qtdo
                else 0
            ),
            "Categoria": valor_texto(
                linha.get(coluna_categoria)
                if coluna_categoria
                else ""
            ),
            "Perfil": valor_texto(
                linha.get(coluna_perfil)
                if coluna_perfil
                else ""
            ),
            "Endereco": endereco,
            "Numero": numero,
            "Bairro": valor_texto(
                linha.get(coluna_bairro)
                if coluna_bairro
                else ""
            ),
            "Cidade": valor_texto(
                linha.get(coluna_cidade)
                if coluna_cidade
                else ""
            ),
            "UF": valor_texto(
                linha.get(coluna_uf)
                if coluna_uf
                else ""
            ),
            "CEP": valor_codigo(
                linha.get(coluna_cep)
                if coluna_cep
                else ""
            ),
            "Ativacao": valor_texto(
                linha.get(coluna_ativacao)
                if coluna_ativacao
                else ""
            ),
            "Latitude": valor_coordenada(
                linha.get(coluna_latitude)
                if coluna_latitude
                else 0,
                limite=90
            ),
            "Longitude": valor_coordenada(
                linha.get(coluna_longitude)
                if coluna_longitude
                else 0,
                limite=180
            ),
            "Altura": valor_numero(
                linha.get(coluna_altura)
                if coluna_altura
                else 0
            ),
            "Restricao": valor_texto(
                linha.get(coluna_restricao)
                if coluna_restricao
                else ""
            ),
            "Detalhe": valor_texto(
                linha.get(coluna_detalhe)
                if coluna_detalhe
                else ""
            ),
            "Observacao": valor_texto(
                linha.get(coluna_observacao)
                if coluna_observacao
                else ""
            ),
            "Contato Principal": valor_texto(
                linha.get(coluna_contato_principal)
                if coluna_contato_principal
                else ""
            ),
            "Telefone Contato": valor_texto(
                linha.get(coluna_telefone_contato)
                if coluna_telefone_contato
                else ""
            ),
            "Email Contato": valor_texto(
                linha.get(coluna_email_contato)
                if coluna_email_contato
                else ""
            ),
            "Outros Contatos": valor_texto(
                linha.get(coluna_outros_contatos)
                if coluna_outros_contatos
                else ""
            )
        })

    return pd.DataFrame(registros)


def chave_site(nome):

    chave = normalizar_texto(nome).upper()
    chave = re.sub(
        r"\s+_(IP|MAC)$",
        r"_\1",
        chave
    )

    return re.sub(
        r"_\s*(IP|MAC)$",
        r"_\1",
        chave
    )


def indices_topos(df_topos):

    por_snmpc = {}
    por_codigo = {}

    if df_topos.empty:

        return por_snmpc, por_codigo

    for registro in df_topos.to_dict("records"):

        snmpc = chave_site(
            registro.get("SNMPc")
        )
        codigo = str(
            registro.get("Codigo") or ""
        ).strip()

        if snmpc:

            por_snmpc[snmpc] = registro

        if codigo:

            por_codigo[codigo] = registro

    return por_snmpc, por_codigo


def localizar_topo_site(site_nome, por_snmpc, por_codigo):

    topo = por_snmpc.get(
        chave_site(site_nome)
    )

    if topo:

        return topo

    codigos = re.findall(
        r"\d+",
        str(site_nome)
    )

    for codigo in codigos:

        topo = por_codigo.get(codigo)

        if topo:

            return topo

    return None
