import base64

import streamlit as st

from app.config import CONFIG_DIR


BACKGROUND_DIRS = [
    CONFIG_DIR / "IMG",
    CONFIG_DIR / "img"
]
BACKGROUND_NAMES = [
    "fundo",
    "fundo.png",
    "fundo.jpg",
    "fundo.jpeg",
    "fundo.webp",
    "fundo.svg"
]


def mime_imagem_fundo(caminho):

    extensao = caminho.suffix.lower()

    if extensao == ".svg":

        return "image/svg+xml"

    if extensao in {
        ".jpg",
        ".jpeg"
    }:

        return "image/jpeg"

    if extensao == ".webp":

        return "image/webp"

    return "image/png"


def arquivo_imagem_fundo():

    for pasta in BACKGROUND_DIRS:

        for nome in BACKGROUND_NAMES:

            caminho = pasta / nome

            if caminho.exists() and caminho.is_file():

                return caminho

    return None


def css_imagem_fundo():

    caminho = arquivo_imagem_fundo()

    if not caminho:

        return ""

    conteudo = base64.b64encode(
        caminho.read_bytes()
    ).decode("ascii")
    mime = mime_imagem_fundo(
        caminho
    )

    return f"""
            .stApp {{
                background:
                    linear-gradient(
                        180deg,
                        rgba(245, 247, 251, 0.90) 0,
                        rgba(245, 247, 251, 0.82) 320px,
                        rgba(245, 247, 251, 0.88) 100%
                    ),
                    url("data:{mime};base64,{conteudo}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
                color: var(--sgt-text);
            }}

            @media (prefers-color-scheme: dark) {{
                .stApp {{
                    background:
                        linear-gradient(
                            180deg,
                            rgba(15, 20, 27, 0.92) 0,
                            rgba(15, 20, 27, 0.84) 320px,
                            rgba(15, 20, 27, 0.90) 100%
                        ),
                        url("data:{mime};base64,{conteudo}");
                    background-size: cover;
                    background-position: center;
                    background-attachment: fixed;
                }}
            }}
    """


def aplicar_tema_visual():

    st.markdown(
        """
        <style>
            :root {
                --sgt-bg: #f5f7fb;
                --sgt-surface: #ffffff;
                --sgt-surface-muted: #f8fafc;
                --sgt-border: #d9e1ec;
                --sgt-text: #172033;
                --sgt-muted: #617089;
                --sgt-accent: #0f766e;
                --sgt-accent-soft: #dff7f2;
                --sgt-warning: #b45309;
                --sgt-danger: #b91c1c;
                --sgt-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --sgt-bg: #0f141b;
                    --sgt-surface: #171d26;
                    --sgt-surface-muted: #111821;
                    --sgt-border: #2c3746;
                    --sgt-text: #eef3f8;
                    --sgt-muted: #a8b3c2;
                    --sgt-accent: #2dd4bf;
                    --sgt-accent-soft: rgba(45, 212, 191, 0.14);
                    --sgt-warning: #f59e0b;
                    --sgt-danger: #f87171;
                    --sgt-shadow: 0 14px 32px rgba(0, 0, 0, 0.28);
                }
            }

            .stApp {
                background:
                    linear-gradient(180deg, var(--sgt-surface-muted) 0, var(--sgt-bg) 280px);
                color: var(--sgt-text);
            }

            __SGS_BACKGROUND_CSS__

            .block-container {
                max-width: 1480px;
                padding-top: 1.1rem;
                padding-bottom: 2rem;
            }

            header[data-testid="stHeader"] {
                background: transparent;
            }

            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {
                display: none;
            }

            #MainMenu, footer[data-testid="stDecoration"], div[data-testid="stToolbar"] {
                visibility: hidden;
                height: 0;
            }

            .sgt-topbar {
                display: flex;
                align-items: center;
                gap: 14px;
                min-height: 92px;
                padding: 14px 18px;
                border: 0;
                border-radius: 0;
                background: transparent;
                box-shadow: none;
                margin-bottom: 12px;
            }

            .sgt-brand-mark {
                width: 78px;
                height: 78px;
                border-radius: 0;
                display: grid;
                place-items: center;
                background: transparent;
                border: 0;
                overflow: visible;
                flex: 0 0 auto;
            }

            .sgt-brand-mark svg,
            .sgt-brand-mark img {
                width: 66px;
                height: 66px;
                display: block;
                object-fit: contain;
            }

            .sgt-logo-fallback {
                color: #ffffff;
                font-weight: 800;
                font-size: 18px;
            }

            .sgt-login-hero {
                max-width: 520px;
                margin: 28px auto 18px;
                padding: 24px;
                border: 0;
                border-radius: 0;
                background: transparent;
                box-shadow: none;
                text-align: center;
            }

            .sgt-login-hero .sgt-brand-mark {
                width: 128px;
                height: 128px;
                margin: 0 auto 14px;
            }

            .sgt-login-hero .sgt-brand-mark svg,
            .sgt-login-hero .sgt-brand-mark img {
                width: 110px;
                height: 110px;
                object-fit: contain;
            }

            .sgt-login-hero .sgt-title {
                font-size: 30px;
            }

            .sgt-title {
                margin: 0;
                color: var(--sgt-text);
                font-size: 26px;
                line-height: 1.1;
                font-weight: 750;
            }

            .sgt-subtitle {
                margin-top: 4px;
                color: var(--sgt-muted);
                font-size: 13px;
            }

            .sgt-header-actions-marker {
                display: none;
            }

            div[data-testid="stHorizontalBlock"]:has(.sgt-header-actions-marker)
            div[data-testid="stPopover"] button {
                min-width: 42px;
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 8px;
                border: 1px solid var(--sgt-border);
                background: var(--sgt-surface);
                color: var(--sgt-muted);
                font-size: 14px;
                white-space: nowrap;
                cursor: pointer;
            }

            div[data-testid="stHorizontalBlock"]:has(.sgt-header-actions-marker)
            div[data-testid="stPopover"] button:hover {
                border-color: var(--sgt-accent);
                color: var(--sgt-text);
                background: var(--sgt-accent-soft);
            }

            h1, h2, h3 {
                color: var(--sgt-text);
                letter-spacing: 0;
            }

            h1 {
                font-size: 1.75rem;
                margin-bottom: 0.65rem;
            }

            h2 {
                font-size: 1.35rem;
            }

            div[data-testid="stTabs"] {
                margin-top: 0.35rem;
            }

            div[data-testid="stTabs"] div[role="tablist"] {
                gap: 6px;
                border-bottom: 1px solid var(--sgt-border);
            }

            div[data-testid="stTabs"] button[role="tab"] {
                min-height: 42px;
                padding: 8px 12px;
                border-radius: 8px 8px 0 0;
                color: var(--sgt-muted);
                font-weight: 650;
            }

            div[data-testid="stTabs"] button[aria-selected="true"] {
                color: var(--sgt-accent);
                background: var(--sgt-accent-soft);
                border-bottom: 2px solid var(--sgt-accent);
            }

            div[data-testid="stSegmentedControl"] {
                margin: 6px 0 14px;
            }

            div[data-testid="stSegmentedControl"] div[role="radiogroup"] {
                gap: 6px;
                flex-wrap: wrap;
            }

            div[data-testid="stSegmentedControl"] label {
                border-radius: 8px;
                font-weight: 650;
            }

            div[data-testid="stMetric"] {
                min-height: 98px;
                padding: 14px 15px;
                border: 1px solid var(--sgt-border);
                border-radius: 8px;
                background: var(--sgt-surface);
                box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
                overflow: visible;
            }

            div[data-testid="stMetricLabel"] p {
                color: var(--sgt-muted);
                font-size: 0.82rem;
                font-weight: 650;
                line-height: 1.2;
                white-space: normal;
            }

            div[data-testid="stMetricValue"] {
                color: var(--sgt-text);
                font-weight: 760;
                font-size: clamp(1rem, 1.35vw, 1.55rem);
                line-height: 1.14;
                white-space: normal;
                overflow-wrap: anywhere;
                word-break: normal;
                max-width: 100%;
            }

            div[data-testid="stMetricValue"] > div {
                width: 100%;
                min-width: 0;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .stButton > button,
            .stDownloadButton > button,
            button[data-testid="baseButton-secondary"],
            button[data-testid="baseButton-primary"] {
                border-radius: 8px;
                border: 1px solid var(--sgt-border);
                min-height: 38px;
                font-weight: 650;
            }

            button[data-testid="baseButton-primary"] {
                background: var(--sgt-accent);
                border-color: var(--sgt-accent);
            }

            div[data-baseweb="input"] > div,
            div[data-baseweb="select"] > div,
            div[data-baseweb="textarea"] textarea,
            div[data-baseweb="base-input"] {
                border-radius: 8px;
                border-color: var(--sgt-border);
            }

            div[data-testid="stExpander"] {
                border: 1px solid var(--sgt-border);
                border-radius: 8px;
                background: var(--sgt-surface);
            }

            div[data-testid="stAlert"] {
                border-radius: 8px;
                border: 1px solid var(--sgt-border);
            }

            .ag-theme-streamlit,
            .ag-theme-alpine {
                --ag-border-radius: 8px;
                --ag-font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }

            .sgt-footer {
                text-align: center;
                color: var(--sgt-muted);
                font-size: 12px;
                margin: 32px 0 12px;
            }

            @media (max-width: 760px) {
                .block-container {
                    padding-left: 0.75rem;
                    padding-right: 0.75rem;
                    padding-top: 0.75rem;
                }

                .sgt-topbar {
                    padding: 10px 12px;
                    min-height: 72px;
                    gap: 10px;
                }

                .sgt-brand-mark {
                    width: 56px;
                    height: 56px;
                }

                .sgt-brand-mark svg,
                .sgt-brand-mark img {
                    width: 46px;
                    height: 46px;
                    object-fit: contain;
                }

                .sgt-title {
                    font-size: 20px;
                }

                .sgt-subtitle {
                    font-size: 12px;
                    line-height: 1.2;
                }

                div[data-testid="stHorizontalBlock"]:has(.sgt-header-actions-marker) {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    width: 100% !important;
                    max-width: 100% !important;
                    justify-content: flex-end !important;
                    gap: 6px !important;
                    align-items: center !important;
                    overflow: hidden !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.sgt-header-actions-marker)
                div[data-testid="stPopover"] button {
                    width: 42px;
                    min-width: 36px;
                    min-height: 28px;
                    padding: 4px 4px;
                }

                h1 {
                    font-size: 1.35rem;
                }

                h2 {
                    font-size: 1.15rem;
                }

                h3 {
                    font-size: 1rem;
                }

                div[data-testid="stTabs"] div[role="tablist"] {
                    overflow-x: auto;
                    overflow-y: hidden;
                    flex-wrap: nowrap;
                    scrollbar-width: thin;
                }

                div[data-testid="stTabs"] button[role="tab"] {
                    min-width: max-content;
                    min-height: 38px;
                    padding: 7px 10px;
                    font-size: 0.86rem;
                }

                div[data-testid="stMetric"] {
                    min-height: 82px;
                    padding: 10px 11px;
                }

                div[data-testid="stMetricLabel"] p {
                    font-size: 0.76rem;
                }

                div[data-testid="stMetricValue"] {
                    font-size: clamp(0.88rem, 5.2vw, 1.22rem);
                }

                div[data-testid="stDataFrame"],
                div.ag-theme-streamlit,
                div.ag-theme-balham,
                div.ag-theme-alpine {
                    font-size: 12px;
                }

                .stButton > button,
                .stDownloadButton > button,
                button[data-testid="baseButton-secondary"],
                button[data-testid="baseButton-primary"] {
                    min-height: 36px;
                    padding-left: 10px;
                    padding-right: 10px;
                }
            }
        </style>
        """.replace(
            "__SGS_BACKGROUND_CSS__",
            css_imagem_fundo()
        ),
        unsafe_allow_html=True
    )
