import os
from pathlib import Path

from app.config import IMPORTS_DIR
from app.importers.txt_importer import importar_estrutura


def caminho_estrutura_txt():

    caminho_configurado = os.getenv(
        "SNMPC_FILE"
    ) or os.getenv(
        "SNMPC_STRUCTURE_TXT_FILE"
    )

    if caminho_configurado:

        caminho = Path(caminho_configurado)

        if caminho.exists():

            return caminho_configurado

    for caminho in [
        IMPORTS_DIR / "SNMPc.txt",
        IMPORTS_DIR / "SNMPc",
        IMPORTS_DIR / "snmpc.txt"
    ]:

        if Path(caminho).exists():

            return str(caminho)

    return caminho_configurado or str(IMPORTS_DIR / "SNMPc.txt")


def versao_estrutura_txt():

    caminho = Path(
        caminho_estrutura_txt()
    )

    if not caminho.exists():

        return "snmpc:ausente"

    stat = caminho.stat()

    return f"{caminho.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def importar_estrutura_atual(retornar_enlaces=False):

    return importar_estrutura(
        caminho_estrutura_txt(),
        retornar_enlaces=retornar_enlaces
    )
