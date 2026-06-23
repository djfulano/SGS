import html
import io
from datetime import datetime
from zipfile import ZIP_DEFLATED
from zipfile import ZipFile


PASTAS_EXPORTACAO = {
    "sites": "Sites",
    "clientes": "Clientes",
    "links_clientes": "Vínculos site x cliente",
    "links_sites": "Vínculos entre sites",
    "nao_plotados": "Itens não plotados"
}


def escapar_xml(valor):
    return html.escape(
        str(valor or ""),
        quote=True
    )


def cdata(valor):
    return str(valor or "").replace("]]>", "]]&gt;")


def valor_texto(registro, coluna):
    valor = registro.get(coluna, "")

    if valor is None:
        return ""

    return str(valor)


def coordenada_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def coordenadas_ponto(registro):
    latitude = coordenada_float(registro.get("Latitude"))
    longitude = coordenada_float(registro.get("Longitude"))

    if latitude is None or longitude is None:
        return ""

    return f"{longitude:.8f},{latitude:.8f},0"


def coordenadas_linha(registro):
    origem = registro.get("Origem")
    destino = registro.get("Destino")

    if not isinstance(origem, (list, tuple)) or not isinstance(destino, (list, tuple)):
        return ""

    if len(origem) < 2 or len(destino) < 2:
        return ""

    origem_lon = coordenada_float(origem[0])
    origem_lat = coordenada_float(origem[1])
    destino_lon = coordenada_float(destino[0])
    destino_lat = coordenada_float(destino[1])

    if None in {
        origem_lon,
        origem_lat,
        destino_lon,
        destino_lat
    }:
        return ""

    return (
        f"{origem_lon:.8f},{origem_lat:.8f},0 "
        f"{destino_lon:.8f},{destino_lat:.8f},0"
    )


def cor_kml(cor, fallback=(120, 120, 120, 220)):
    if not isinstance(cor, (list, tuple)):
        cor = fallback

    valores = list(cor) + list(fallback)

    try:
        vermelho = max(0, min(255, int(valores[0])))
        verde = max(0, min(255, int(valores[1])))
        azul = max(0, min(255, int(valores[2])))
        alpha = max(0, min(255, int(valores[3])))
    except (TypeError, ValueError):
        vermelho, verde, azul, alpha = fallback

    return f"{alpha:02x}{azul:02x}{verde:02x}{vermelho:02x}"


def dataframe_registros(df):
    if df is None or getattr(df, "empty", True):
        return []

    return df.to_dict("records")


def descricao_html(registro, campos):
    linhas = []

    for coluna in campos:
        valor = valor_texto(
            registro,
            coluna
        )

        if not valor:
            continue

        linhas.append(
            "<tr>"
            f"<th>{html.escape(coluna)}</th>"
            f"<td>{html.escape(valor)}</td>"
            "</tr>"
        )

    if not linhas:
        return ""

    return (
        "<![CDATA[<table>"
        + "".join(linhas)
        + "</table>]]>"
    )


def placemark_ponto(nome, registro, campos, cor, escala=1.1):
    coordenadas = coordenadas_ponto(registro)
    descricao = descricao_html(
        registro,
        campos
    )
    geometria = (
        "<Point>"
        f"<coordinates>{coordenadas}</coordinates>"
        "</Point>"
        if coordenadas
        else ""
    )

    return (
        "<Placemark>"
        f"<name>{escapar_xml(nome)}</name>"
        f"<description>{descricao}</description>"
        "<Style>"
        "<IconStyle>"
        f"<color>{cor_kml(cor)}</color>"
        f"<scale>{escapar_xml(escala)}</scale>"
        "<Icon>"
        "<href>http://maps.google.com/mapfiles/kml/paddle/wht-blank.png</href>"
        "</Icon>"
        "</IconStyle>"
        "</Style>"
        f"{geometria}"
        "</Placemark>"
    )


def placemark_linha(nome, registro, campos, cor, largura):
    coordenadas = coordenadas_linha(registro)

    if not coordenadas:
        return ""

    descricao = descricao_html(
        registro,
        campos
    )

    return (
        "<Placemark>"
        f"<name>{escapar_xml(nome)}</name>"
        f"<description>{descricao}</description>"
        "<Style>"
        "<LineStyle>"
        f"<color>{cor_kml(cor)}</color>"
        f"<width>{int(largura)}</width>"
        "</LineStyle>"
        "</Style>"
        "<LineString>"
        "<tessellate>1</tessellate>"
        f"<coordinates>{coordenadas}</coordinates>"
        "</LineString>"
        "</Placemark>"
    )


def pasta_kml(nome, placemarks):
    placemarks = [
        placemark
        for placemark in placemarks
        if placemark
    ]

    if not placemarks:
        return ""

    return (
        "<Folder>"
        f"<name>{escapar_xml(nome)}</name>"
        + "".join(placemarks)
        + "</Folder>"
    )


def campos_por_tipo(campos_detalhe):
    campos_detalhe = set(campos_detalhe or [])
    campos = {
        "sites": [
            "Site"
        ],
        "clientes": [
            "Cliente"
        ],
        "links": [
            "Distância Km"
        ],
        "nao_plotados": [
            "Tipo Item",
            "Motivo"
        ]
    }

    if "Endereço" in campos_detalhe:
        campos["sites"].extend(["Endereco", "Cidade", "UF", "CEP"])
        campos["clientes"].extend(["Endereco", "Cidade", "UF"])
        campos["nao_plotados"].append("Endereco")

    if "Coordenadas" in campos_detalhe:
        for chave in campos:
            campos[chave].extend(["Latitude", "Longitude"])

    if "Setorial" in campos_detalhe:
        campos["sites"].append("Setorial")
        campos["clientes"].append("Setorial")
        campos["links"].append("Setorial")

    if "Distância" in campos_detalhe:
        campos["clientes"].append("Distância Site Km")
        campos["nao_plotados"].extend(["Distância Km", "Limite Km"])

    if "Produto" in campos_detalhe:
        campos["clientes"].append("Produto")
        campos["links"].append("Produto")

    if "Equipamento" in campos_detalhe:
        campos["clientes"].append("Equipamento")

    if "Receita" in campos_detalhe:
        campos["clientes"].append("Receita")
        campos["links"].append("Receita")

    if "Motivo" in campos_detalhe:
        campos["nao_plotados"].extend(["Vínculo", "Site", "Cliente", "Assinatura"])

    return campos


def montar_kml_mapa(
    df_sites,
    df_clientes,
    df_links_clientes,
    df_links_sites,
    df_nao_plotados,
    *,
    itens=None,
    campos_detalhe=None,
    nome_documento="SGS Mapa"
):
    itens = set(itens or PASTAS_EXPORTACAO.keys())
    campos = campos_por_tipo(campos_detalhe)
    pastas = []

    if "sites" in itens:
        pastas.append(pasta_kml(
            PASTAS_EXPORTACAO["sites"],
            [
                placemark_ponto(
                    valor_texto(registro, "Site") or "Site",
                    registro,
                    campos["sites"],
                    registro.get("Cor") or [20, 150, 70, 220],
                    escala=1.2
                )
                for registro in dataframe_registros(df_sites)
            ]
        ))

    if "clientes" in itens:
        pastas.append(pasta_kml(
            PASTAS_EXPORTACAO["clientes"],
            [
                placemark_ponto(
                    valor_texto(registro, "Cliente") or "Cliente",
                    registro,
                    campos["clientes"],
                    [130, 130, 130, 220],
                    escala=0.9
                )
                for registro in dataframe_registros(df_clientes)
            ]
        ))

    if "links_clientes" in itens:
        pastas.append(pasta_kml(
            PASTAS_EXPORTACAO["links_clientes"],
            [
                placemark_linha(
                    (
                        f"{valor_texto(registro, 'Site')} -> "
                        f"{valor_texto(registro, 'Cliente')}"
                    ),
                    registro,
                    campos["links"],
                    registro.get("Cor") or [20, 150, 70, 160],
                    3
                )
                for registro in dataframe_registros(df_links_clientes)
            ]
        ))

    if "links_sites" in itens:
        pastas.append(pasta_kml(
            PASTAS_EXPORTACAO["links_sites"],
            [
                placemark_linha(
                    (
                        f"{valor_texto(registro, 'Site Pai')} -> "
                        f"{valor_texto(registro, 'Site Filho')}"
                    ),
                    registro,
                    campos["links"],
                    registro.get("Cor") or [210, 30, 30, 170],
                    5
                )
                for registro in dataframe_registros(df_links_sites)
            ]
        ))

    if "nao_plotados" in itens:
        pastas.append(pasta_kml(
            PASTAS_EXPORTACAO["nao_plotados"],
            [
                placemark_ponto(
                    (
                        valor_texto(registro, "Cliente")
                        or valor_texto(registro, "Site")
                        or valor_texto(registro, "Tipo Item")
                        or "Item não plotado"
                    ),
                    registro,
                    campos["nao_plotados"],
                    [245, 180, 40, 220],
                    escala=0.9
                )
                for registro in dataframe_registros(df_nao_plotados)
            ]
        ))

    conteudo = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document>"
        f"<name>{escapar_xml(nome_documento)}</name>"
        f"<description><![CDATA[Gerado pelo SGS em {cdata(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}]]></description>"
        + "".join(pastas)
        + "</Document>"
        + "</kml>"
    )

    return conteudo.encode("utf-8")


def montar_kmz_mapa(*args, **kwargs):
    kml = montar_kml_mapa(
        *args,
        **kwargs
    )
    buffer = io.BytesIO()

    with ZipFile(
        buffer,
        "w",
        ZIP_DEFLATED
    ) as arquivo_zip:
        arquivo_zip.writestr(
            "doc.kml",
            kml
        )

    return buffer.getvalue()
