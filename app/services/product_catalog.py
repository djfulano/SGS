from io import BytesIO
import re
import unicodedata

import pandas as pd

from app.config import PRODUCT_CATALOG_FILE
from app.storage import read_json
from app.storage import write_json_atomic


PRODUCT_CATALOG_COLUMNS = [
    "Nome",
    "Tipo",
    "Grupo",
    "Família",
    "Velocidade",
    "Variação"
]

PRODUCT_TYPES = [
    "Telecom",
    "SVA"
]
TELECOM_GROUPS = [
    "Internet",
    "VPN"
]
INTERNET_FAMILIES = [
    "NeoSoft",
    "NeoTotal"
]
VPN_FAMILIES = [
    "VPN",
    "CARRIER"
]
SVA_FAMILIES = [
    "NeoWifi",
    "NeoFirewall",
    "NeoBalance",
    "NeoCaptive"
]
PRODUCT_FAMILIES = INTERNET_FAMILIES + VPN_FAMILIES + SVA_FAMILIES

COLUMN_ALIASES = {
    "NOME": "Nome",
    "PRODUTO": "Nome",
    "NOME PRODUTO": "Nome",
    "TIPO": "Tipo",
    "CLASSIFICACAO": "Tipo",
    "CLASSIFICACAO 1": "Tipo",
    "GRUPO": "Grupo",
    "SUBTIPO": "Grupo",
    "CATEGORIA": "Grupo",
    "FAMILIA": "Família",
    "LINHA": "Família",
    "VELOCIDADE": "Velocidade",
    "BANDA": "Velocidade",
    "VARIACAO": "Variação",
    "VARIACAO PRODUTO": "Variação",
    "CARACTERISTICA": "Variação",
    "CARACTERISTICAS": "Variação"
}


def normalize_column_key(value):
    text = str(value or "").strip()
    text = unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ascii",
        "ignore"
    ).decode("ascii")

    return re.sub(
        r"[^A-Z0-9]+",
        " ",
        text.upper()
    ).strip()


def normalize_product_text(value):
    if pd.isna(value):
        return ""

    return str(value or "").strip()


def normalize_catalog_columns(df):
    rename = {}

    for column in df.columns:
        key = normalize_column_key(column)

        if key in COLUMN_ALIASES:
            rename[column] = COLUMN_ALIASES[key]

    return df.rename(columns=rename)


def infer_product_fields(name):
    text = normalize_product_text(name)
    text_lower = text.lower()

    result = {
        "Tipo": "",
        "Grupo": "",
        "Família": "",
        "Velocidade": "",
        "Variação": ""
    }

    family_rules = [
        ("NeoSoft", "Telecom", "Internet"),
        ("NeoTotal", "Telecom", "Internet"),
        ("CARRIER", "Telecom", "VPN"),
        ("VPN", "Telecom", "VPN"),
        ("NeoWifi", "SVA", ""),
        ("NeoFirewall", "SVA", ""),
        ("NeoBalance", "SVA", ""),
        ("NeoCaptive", "SVA", "")
    ]

    for family, product_type, group in family_rules:
        if family.lower() in text_lower:
            result["Tipo"] = product_type
            result["Grupo"] = group
            result["Família"] = family
            break

    speed_match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*(GIGA|GB|MB|M|KB|K)",
        text,
        flags=re.IGNORECASE
    )

    if speed_match:
        result["Velocidade"] = " ".join(speed_match.groups()).upper()

    if result["Família"]:
        variation = re.sub(
            re.escape(result["Família"]),
            "",
            text,
            flags=re.IGNORECASE
        ).strip(" -_/|")
        result["Variação"] = variation

    return result


def normalize_catalog_dataframe(df):
    if df is None:
        df = pd.DataFrame(columns=PRODUCT_CATALOG_COLUMNS)

    df = normalize_catalog_columns(df.copy())

    for column in PRODUCT_CATALOG_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[PRODUCT_CATALOG_COLUMNS].fillna("")

    for column in PRODUCT_CATALOG_COLUMNS:
        df[column] = df[column].apply(normalize_product_text)

    for index, row in df.iterrows():
        inferred = infer_product_fields(row.get("Nome"))

        for column, value in inferred.items():
            if not normalize_product_text(row.get(column)):
                df.at[index, column] = value

    df = df[df["Nome"] != ""]
    df = df.drop_duplicates(
        subset=["Nome"],
        keep="last"
    )

    return df.sort_values(
        by=["Tipo", "Grupo", "Família", "Nome"]
    ).reset_index(drop=True)


def load_product_catalog(path=None):
    path = path or PRODUCT_CATALOG_FILE
    records = read_json(
        path,
        []
    )

    return normalize_catalog_dataframe(
        pd.DataFrame(records)
    )


def save_product_catalog(df, path=None):
    path = path or PRODUCT_CATALOG_FILE
    df_save = normalize_catalog_dataframe(df)
    write_json_atomic(
        path,
        df_save.to_dict("records")
    )

    return df_save


def products_from_clients(df_clientes):
    if df_clientes is None or df_clientes.empty or "Produto" not in df_clientes.columns:
        return pd.DataFrame(columns=PRODUCT_CATALOG_COLUMNS)

    products = (
        df_clientes["Produto"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda column: column != ""]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    return normalize_catalog_dataframe(
        pd.DataFrame({
            "Nome": products
        })
    )


def ensure_catalog_from_clients(df_clientes, path=None):
    df_catalog = load_product_catalog(path)
    df_products = products_from_clients(df_clientes)

    if df_products.empty:
        return df_catalog

    df_merged = df_products[["Nome"]].merge(
        df_catalog,
        on="Nome",
        how="left"
    )

    for column in PRODUCT_CATALOG_COLUMNS:
        if column not in df_merged.columns:
            df_merged[column] = ""

    extras = df_catalog[
        ~df_catalog["Nome"].isin(df_products["Nome"])
    ]

    if not extras.empty:
        df_merged = pd.concat(
            [
                df_merged,
                extras
            ],
            ignore_index=True
        )

    return normalize_catalog_dataframe(df_merged)


def merge_catalog_update(df_current, df_update):
    df_current = normalize_catalog_dataframe(df_current)
    df_update = normalize_catalog_dataframe(df_update)

    if df_update.empty:
        return df_current

    update_names = set(
        df_update["Nome"]
    )
    df_current = df_current[
        ~df_current["Nome"].isin(update_names)
    ]

    return normalize_catalog_dataframe(
        pd.concat(
            [
                df_current,
                df_update
            ],
            ignore_index=True
        )
    )


def import_product_catalog_excel(uploaded_file, df_current=None):
    df_import = pd.read_excel(
        uploaded_file,
        dtype=object
    )
    df_import = normalize_catalog_columns(df_import)

    if "Nome" not in df_import.columns:
        raise ValueError(
            "A planilha deve conter a coluna Nome ou Produto."
        )

    df_current = (
        load_product_catalog()
        if df_current is None
        else df_current
    )

    return merge_catalog_update(
        df_current,
        df_import
    )


def product_catalog_template_excel():
    output = BytesIO()
    df_template = pd.DataFrame(
        columns=PRODUCT_CATALOG_COLUMNS
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_template.to_excel(
            writer,
            index=False,
            sheet_name="Produtos"
        )

    output.seek(0)

    return output.getvalue()


def enrich_products_with_catalog(df):
    if df is None or df.empty or "Produto" not in df.columns:
        return df

    df_catalog = load_product_catalog().rename(columns={
        "Nome": "Produto",
        "Tipo": "Tipo Produto",
        "Grupo": "Grupo Produto",
        "Família": "Família Produto",
        "Velocidade": "Velocidade Produto",
        "Variação": "Variação Produto"
    })

    if df_catalog.empty:
        return df

    return df.merge(
        df_catalog,
        on="Produto",
        how="left"
    )
