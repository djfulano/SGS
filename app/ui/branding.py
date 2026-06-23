import base64
from pathlib import Path

from app.config import CONFIG_DIR


MANUAL_USO_FILE = Path("docs/USO.md")
FAQ_FILE = Path("docs/FAQ.md")
BRANDING_DIR = CONFIG_DIR / "branding"
BRANDING_LOGO_FILES = [
    BRANDING_DIR / "Neovia-Logo-Branco.png",
    BRANDING_DIR / "Neovia-Logo-Branco.jpg",
    BRANDING_DIR / "Neovia-Logo-Branco.jpeg",
    BRANDING_DIR / "Neovia-Logo-Branco.svg"
]
NEOVIA_LOGO_FALLBACK_FILE = Path("app/static/neovia-logo-branco.svg")


def logo_branding_file():

    for caminho in BRANDING_LOGO_FILES:

        if caminho.exists():

            return caminho

    return None


def favicon_sgs():

    return (
        logo_branding_file()
        or (
            NEOVIA_LOGO_FALLBACK_FILE
            if NEOVIA_LOGO_FALLBACK_FILE.exists()
            else "SGS"
        )
    )


def mime_logo(caminho):

    extensao = caminho.suffix.lower()

    if extensao == ".svg":

        return "image/svg+xml"

    if extensao in {
        ".jpg",
        ".jpeg"
    }:

        return "image/jpeg"

    return "image/png"


def logo_neovia_html():

    caminho = logo_branding_file()

    if caminho:

        conteudo = base64.b64encode(
            caminho.read_bytes()
        ).decode("ascii")

        return (
            f'<img src="data:{mime_logo(caminho)};base64,{conteudo}" '
            'alt="Neovia Solutions" />'
        )

    if not NEOVIA_LOGO_FALLBACK_FILE.exists():

        return '<span class="sgt-logo-fallback">SGS</span>'

    return NEOVIA_LOGO_FALLBACK_FILE.read_text(
        encoding="utf-8"
    )


def bloco_identidade_sgs(classe="sgt-topbar"):

    return f"""
    <div class="{classe}">
        <div class="sgt-brand-mark">{logo_neovia_html()}</div>
        <div>
            <div class="sgt-title">SGS</div>
            <div class="sgt-subtitle">Sistema de gerenciamento de Sites</div>
        </div>
    </div>
    """
