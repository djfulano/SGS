from io import BytesIO
import re
import unicodedata

import pandas as pd

from app.config import EQUIPMENT_CATALOG_FILE
from app.storage import read_json
from app.storage import write_json_atomic


EQUIPMENT_CATALOG_COLUMNS = [
    "Ícone",
    "Modelo",
    "Fabricante",
    "Software",
    "Tipo",
    "Código",
    "Valor"
]

COLUMN_ALIASES = {
    "ICONE": "Ícone",
    "ICONES": "Ícone",
    "ICONE SNMPC": "Ícone",
    "ICONE DO SNMPC": "Ícone",
    "NOME": "Modelo",
    "MODELO": "Modelo",
    "FABRICANTE": "Fabricante",
    "SOFTWARE": "Software",
    "TIPO": "Tipo",
    "CODIGO": "Código",
    "CODIGO EQUIPAMENTO": "Código",
    "VALOR": "Valor",
    "CUSTO": "Valor"
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


def normalize_catalog_columns(df):
    rename = {}

    for column in df.columns:
        key = normalize_column_key(column)

        if key in COLUMN_ALIASES:
            rename[column] = COLUMN_ALIASES[key]

    df = df.rename(columns=rename)

    if not df.columns.duplicated().any():
        return df

    normalized = pd.DataFrame(index=df.index)

    for column in dict.fromkeys(df.columns):
        subset = df.loc[:, df.columns == column]

        if subset.shape[1] == 1:
            normalized[column] = subset.iloc[:, 0]
            continue

        normalized[column] = (
            subset
            .replace("", pd.NA)
            .ffill(axis=1)
            .iloc[:, -1]
            .fillna("")
        )

    return normalized


def normalize_icon(value):
    if pd.isna(value):
        return ""

    return str(value or "").strip()


def normalize_money(value):
    if pd.isna(value) or value == "":
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    text = (
        str(value)
        .replace("R$", "")
        .replace(" ", "")
        .strip()
    )

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_catalog_dataframe(df):
    if df is None:
        df = pd.DataFrame(columns=EQUIPMENT_CATALOG_COLUMNS)

    df = df.copy()
    df = normalize_catalog_columns(df)

    for column in EQUIPMENT_CATALOG_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[EQUIPMENT_CATALOG_COLUMNS].fillna("")
    df["Ícone"] = df["Ícone"].apply(normalize_icon)
    df["Modelo"] = df["Modelo"].astype(str).str.strip()
    df["Fabricante"] = df["Fabricante"].astype(str).str.strip()
    df["Software"] = df["Software"].astype(str).str.strip()
    df["Tipo"] = df["Tipo"].astype(str).str.strip()
    df["Código"] = df["Código"].astype(str).str.strip()
    df["Valor"] = df["Valor"].apply(normalize_money)
    df = df[df["Ícone"] != ""]
    df = df.drop_duplicates(
        subset=["Ícone"],
        keep="last"
    )

    return df.sort_values(
        by=["Ícone"]
    ).reset_index(drop=True)


def load_equipment_catalog(path=None):
    path = path or EQUIPMENT_CATALOG_FILE
    records = read_json(
        path,
        []
    )

    return normalize_catalog_dataframe(
        pd.DataFrame(records)
    )


def save_equipment_catalog(df, path=None):
    path = path or EQUIPMENT_CATALOG_FILE
    df_save = normalize_catalog_dataframe(df)
    write_json_atomic(
        path,
        df_save.to_dict("records")
    )

    return df_save


def merge_catalog_update(df_current, df_update):
    df_current = normalize_catalog_dataframe(df_current)
    df_update = normalize_catalog_dataframe(df_update)

    if df_update.empty:
        return df_current

    update_icons = set(
        df_update["Ícone"]
    )
    df_current = df_current[
        ~df_current["Ícone"].isin(update_icons)
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


def import_equipment_catalog_excel(uploaded_file, df_current=None):
    df_import = pd.read_excel(
        uploaded_file,
        dtype=object
    )
    df_import = normalize_catalog_columns(df_import)

    if "Ícone" not in df_import.columns:
        raise ValueError(
            "A planilha deve conter a coluna Ícone."
        )

    df_current = (
        load_equipment_catalog()
        if df_current is None
        else df_current
    )

    return merge_catalog_update(
        df_current,
        df_import
    )


def equipment_catalog_template_excel():
    output = BytesIO()
    df_template = pd.DataFrame(
        columns=EQUIPMENT_CATALOG_COLUMNS
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_template.to_excel(
            writer,
            index=False,
            sheet_name="Equipamentos"
        )

    output.seek(0)

    return output.getvalue()


def icons_from_equipments(equipamentos):
    icons = sorted({
        normalize_icon(
            equipamento.get("Icone")
        )
        for equipamento in equipamentos
        if normalize_icon(
            equipamento.get("Icone")
        )
    })

    return pd.DataFrame({
        "Ícone": icons
    })


def ensure_catalog_from_equipments(equipamentos, path=None):
    df_catalog = load_equipment_catalog(path)
    df_icons = icons_from_equipments(equipamentos)

    if df_icons.empty:
        return df_catalog

    df_merged = df_icons.merge(
        df_catalog,
        on="Ícone",
        how="left"
    )

    for column in EQUIPMENT_CATALOG_COLUMNS:
        if column not in df_merged.columns:
            df_merged[column] = ""

    df_merged["Valor"] = df_merged["Valor"].fillna(0)

    extras = df_catalog[
        ~df_catalog["Ícone"].isin(df_icons["Ícone"])
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


def enrich_equipments_with_catalog(df_equipamentos):
    if df_equipamentos.empty:
        return df_equipamentos

    df_catalog = load_equipment_catalog()

    if df_catalog.empty:
        return df_equipamentos

    df_catalog = df_catalog.rename(columns={
        "Ícone": "Icone",
        "Modelo": "Modelo Base",
        "Fabricante": "Fabricante Base",
        "Software": "Software Base",
        "Tipo": "Tipo Base",
        "Código": "Código Base",
        "Valor": "Valor Base"
    })

    return df_equipamentos.merge(
        df_catalog,
        on="Icone",
        how="left"
    )
