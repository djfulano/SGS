import json

import streamlit as st

from app.auth import account_display_label
from app.auth import authenticate
from app.auth import authenticate_session
from app.auth import bootstrap_token_configured
from app.auth import clear_login_failures
from app.auth import create_session
from app.auth import create_user
from app.auth import load_users
from app.auth import login_lock_status
from app.auth import register_login_failure
from app.auth import revoke_session
from app.auth import save_users
from app.auth import update_password
from app.auth import validate_password
from app.auth import verify_bootstrap_token
from app.auth import has_permission
from app.logs import registrar_log_sistema
from app.logs import registrar_log_usuario
from app.logs import carregar_logs_sistema
from app.services.backup_service import executar_backup_automatico_se_necessario
from app.services.import_reminder import status_importacao_mensal
from app.ui.branding import bloco_identidade_sgs
from app.ui.help import mostrar_ajuda_interativa
from app.version import get_app_version


APP_VERSION = get_app_version()
AUTH_COOKIE_NAME = "sgs_auth_token"
AUTH_COOKIE_MAX_AGE = 12 * 60 * 60
AUTH_NOTICE_LEVELS = {"error", "warning", "info", "success"}
AUTH_NOTICE_MESSAGES = {
    "expired": ("warning", "Sua sessão expirou. Entre novamente."),
    "logout": ("info", "Sessão encerrada."),
    "password_changed": (
        "success",
        "Senha atualizada. Entre novamente para continuar.",
    ),
    "session_error": (
        "error",
        "Não foi possível validar sua sessão. Entre novamente.",
    ),
}


def usuario_logado():

    return st.session_state.get("usuario")


def token_cookie():

    try:

        return st.context.cookies.get(AUTH_COOKIE_NAME, "")

    except Exception:

        return ""


def registrar_sessao_autenticada(usuario, token, estado=None):
    estado = st.session_state if estado is None else estado
    estado.pop("limpar_auth_cookie", None)
    estado.pop("motivo_limpar_auth_cookie", None)
    estado.pop("feedback_login", None)
    estado["usuario"] = usuario
    estado["auth_token"] = token


def definir_feedback_login(mensagem, nivel="error", estado=None):
    estado = st.session_state if estado is None else estado
    estado["feedback_login"] = {
        "mensagem": str(mensagem or "").strip(),
        "nivel": nivel if nivel in AUTH_NOTICE_LEVELS else "error",
    }


def agendar_limpeza_cookie_auth(motivo="", estado=None):
    estado = st.session_state if estado is None else estado
    estado.pop("usuario", None)
    estado.pop("auth_token", None)
    estado["limpar_auth_cookie"] = True
    estado["motivo_limpar_auth_cookie"] = str(motivo or "").strip()


def script_limpar_cookie_auth(motivo=""):
    motivo = str(motivo or "").strip()

    return f"""
    <script>
        const cookieName = {json.dumps(AUTH_COOKIE_NAME)};
        const notice = {json.dumps(motivo)};
        const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
        window.parent.document.cookie = `${{cookieName}}=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Strict${{secure}}`;
        const url = new URL(window.parent.location.href);
        url.searchParams.delete("logout");
        if (notice) {{
            url.searchParams.set("auth_notice", notice);
        }} else {{
            url.searchParams.delete("auth_notice");
        }}
        window.parent.location.replace(url.toString());
    </script>
    """


def renderizar_limpeza_cookie_auth(motivo=""):

    st.html(
        script_limpar_cookie_auth(motivo),
        unsafe_allow_javascript=True
    )


def consumir_aviso_auth_query():
    aviso = st.query_params.get("auth_notice")
    if isinstance(aviso, list):
        aviso = aviso[-1] if aviso else ""
    aviso = str(aviso or "").strip()

    if not aviso:
        return

    nivel, mensagem = AUTH_NOTICE_MESSAGES.get(
        aviso,
        AUTH_NOTICE_MESSAGES["session_error"],
    )
    definir_feedback_login(mensagem, nivel)
    st.html(
        """
        <script>
            const url = new URL(window.parent.location.href);
            url.searchParams.delete("auth_notice");
            window.parent.history.replaceState({}, "", url.toString());
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def mostrar_feedback_login(destino=None):
    feedback = st.session_state.get("feedback_login") or {}
    mensagem = str(feedback.get("mensagem") or "").strip()
    if not mensagem:
        return

    nivel = str(feedback.get("nivel") or "error")
    destino = destino or st
    getattr(destino, nivel if nivel in AUTH_NOTICE_LEVELS else "error")(mensagem)


def sincronizar_token_navegador():

    token = st.session_state.get("auth_token")

    if st.query_params.get("logout") is not None:

        try:

            del st.query_params["logout"]

        except KeyError:

            pass

    if st.session_state.pop("limpar_auth_cookie", False):

        motivo = st.session_state.pop(
            "motivo_limpar_auth_cookie",
            "",
        )
        renderizar_limpeza_cookie_auth(motivo)
        st.stop()

    consumir_aviso_auth_query()

    if token:

        st.html(
            f"""
            <script>
                const cookieName = {json.dumps(AUTH_COOKIE_NAME)};
                const token = {json.dumps(token)};
                const maxAge = {AUTH_COOKIE_MAX_AGE};
                const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
                const cookieValue = `${{cookieName}}=${{encodeURIComponent(token)}}; Max-Age=${{maxAge}}; path=/; SameSite=Strict${{secure}}`;
                window.parent.document.cookie = cookieValue;
            </script>
            """,
            unsafe_allow_javascript=True
        )


def exigir_token_bootstrap():
    if st.session_state.get("bootstrap_autorizado"):
        return True

    if not bootstrap_token_configured():
        st.error(
            "A inicialização está bloqueada. Configure SGS_BOOTSTRAP_TOKEN "
            "no ambiente e reinicie o SGS."
        )
        return False

    with st.form("autorizar_bootstrap"):
        token = st.text_input(
            "Token de inicialização",
            type="password"
        )
        autorizar = st.form_submit_button("Autorizar inicialização")

    if autorizar:
        if verify_bootstrap_token(token):
            st.session_state["bootstrap_autorizado"] = True
            st.rerun()
        else:
            st.error("Token de inicialização inválido.")

    return False


def configurar_primeiro_master():

    st.markdown(
        bloco_identidade_sgs("sgt-login-hero"),
        unsafe_allow_html=True
    )

    st.warning(
        "Nenhum usuário cadastrado. Crie o primeiro usuário Master."
    )

    if not exigir_token_bootstrap():
        return False

    with st.form("primeiro_master"):

        usuario = st.text_input("Usuário Master")
        senha = st.text_input(
            "Senha",
            type="password"
        )
        confirmar = st.text_input(
            "Confirmar senha",
            type="password"
        )
        salvar = st.form_submit_button("Criar Master")

    if salvar:

        if not usuario or not senha:

            st.error("Informe usuário e senha.")

            return False

        if senha != confirmar:

            st.error("As senhas não conferem.")

            return False

        valid, message = validate_password(senha, usuario)

        if not valid:
            st.error(message)
            return False

        users = {
            usuario: create_user(
                usuario,
                senha,
                "Master",
                must_change_password=False
            )
        }

        save_users(users)
        registrar_log_usuario(
            "primeiro_master_criado",
            usuario=usuario,
            status="sucesso",
            detalhes={
                "perfil": "Master"
            }
        )

        st.success(
            "Usuário Master criado. Faça login para continuar."
        )

    return False


def mostrar_login():

    st.markdown(
        bloco_identidade_sgs("sgt-login-hero"),
        unsafe_allow_html=True
    )
    st.subheader("Login")
    area_feedback = st.empty()
    mostrar_feedback_login(area_feedback)

    with st.form("login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input(
            "Senha",
            type="password"
        )
        entrar = st.form_submit_button("Entrar")

    if entrar:
        st.session_state.pop("feedback_login", None)
        area_feedback.empty()
        login_autenticado = False

        try:
            bloqueado, segundos_restantes = login_lock_status(
                usuario
            )

            if bloqueado:
                minutos = max(
                    1,
                    int((segundos_restantes + 59) / 60)
                )
                registrar_log_usuario(
                    "login_bloqueado",
                    usuario=usuario,
                    status="falha",
                    detalhes={
                        "minutos_restantes": minutos
                    }
                )
                definir_feedback_login(
                    "Muitas tentativas inválidas. "
                    f"Tente novamente em {minutos} minuto(s).",
                    "error",
                )
                mostrar_feedback_login(area_feedback)
                return False

            autenticado = authenticate(
                usuario,
                senha
            )

            if autenticado:

                clear_login_failures(
                    usuario
                )

                token = create_session(usuario)
                registrar_sessao_autenticada(
                    autenticado,
                    token,
                )

                registrar_log_usuario(
                    "login",
                    usuario=usuario,
                    status="sucesso"
                )
                login_autenticado = True

            else:
                falhas = register_login_failure(
                    usuario
                )
                registrar_log_usuario(
                    "login",
                    usuario=usuario,
                    status="falha",
                    detalhes={
                        "falhas_consecutivas": falhas
                    }
                )
                definir_feedback_login(
                    "Usuário ou senha inválidos.",
                    "error",
                )
                mostrar_feedback_login(area_feedback)
        except Exception as erro:
            registrar_log_sistema(
                "login_indisponivel",
                usuario=str(usuario or "").strip(),
                status="erro",
                detalhes={"erro": str(erro)},
            )
            definir_feedback_login(
                "Não foi possível realizar o login agora. Tente novamente.",
                "error",
            )
            mostrar_feedback_login(area_feedback)

        if login_autenticado:
            st.rerun()

    return False


def exigir_login():

    token = (
        st.session_state.get("auth_token")
        or token_cookie()
    )

    if token:

        try:

            autenticado = authenticate_session(token)

        except Exception as erro:
            registrar_log_sistema(
                "validacao_sessao",
                usuario=(usuario_logado() or {}).get("username", ""),
                status="erro",
                detalhes={"erro": str(erro)},
            )
            agendar_limpeza_cookie_auth("session_error")
            sincronizar_token_navegador()
            st.stop()

        if autenticado:
            usuario_anterior = usuario_logado() or {}
            st.session_state["usuario"] = autenticado
            st.session_state["auth_token"] = token

            if not usuario_anterior:
                registrar_log_usuario(
                    "login_token",
                    usuario=autenticado["username"],
                    status="sucesso"
                )

            return True

        agendar_limpeza_cookie_auth("expired")
        sincronizar_token_navegador()
        st.stop()

    try:

        users = load_users()

    except Exception as erro:
        registrar_log_sistema(
            "carregamento_usuarios_login",
            usuario="",
            status="erro",
            detalhes={"erro": str(erro)},
        )
        definir_feedback_login(
            "Não foi possível carregar o acesso ao SGS. Tente novamente.",
            "error",
        )
        mostrar_feedback_login()
        st.stop()

    if not users:

        return configurar_primeiro_master()

    return mostrar_login()


def mostrar_troca_senha_obrigatoria():

    usuario = usuario_logado()

    st.markdown(
        bloco_identidade_sgs("sgt-login-hero"),
        unsafe_allow_html=True
    )
    st.warning("Altere sua senha para continuar.")

    with st.form("troca_senha_obrigatoria"):

        senha_atual = st.text_input(
            "Senha atual",
            type="password"
        )
        nova_senha = st.text_input(
            "Nova senha",
            type="password"
        )
        confirmar_senha = st.text_input(
            "Confirmar nova senha",
            type="password"
        )
        alterar = st.form_submit_button("Salvar nova senha")

    if alterar:

        if not senha_atual or not nova_senha:

            st.error("Informe a senha atual e a nova senha.")

            return

        if nova_senha != confirmar_senha:

            st.error("As senhas não conferem.")

            return

        sucesso, mensagem = update_password(
            usuario["username"],
            senha_atual,
            nova_senha
        )

        if sucesso:
            registrar_log_usuario(
                "senha_alterada",
                usuario=usuario["username"],
                status="sucesso",
                detalhes={
                    "origem": "primeiro_login"
                }
            )
            agendar_limpeza_cookie_auth("password_changed")
            st.rerun()

        registrar_log_usuario(
            "senha_alterada",
            usuario=usuario["username"],
            status="falha",
            detalhes={
                "origem": "primeiro_login",
                "mensagem": mensagem
            }
        )
        st.error(mensagem)


def executar_backup_apos_login():

    try:
        resultado_backup_automatico = executar_backup_automatico_se_necessario(
            usuario=usuario_logado().get("username", "sistema")
        )

        if resultado_backup_automatico:
            registrar_log_sistema(
                "backup_automatico",
                usuario=usuario_logado().get("username"),
                status="sucesso",
                detalhes=resultado_backup_automatico
            )
    except Exception as erro:
        registrar_log_sistema(
            "backup_automatico",
            usuario=usuario_logado().get("username"),
            status="erro",
            detalhes={
                "erro": str(erro)
            }
        )


def mostrar_barra_superior_conta():

    usuario = usuario_logado()

    st.markdown(
        bloco_identidade_sgs(),
        unsafe_allow_html=True
    )

    with st.container(
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap="small"
    ):

        st.markdown(
            '<span class="sgt-header-actions-marker"></span>',
            unsafe_allow_html=True
        )
        with st.popover(
            ":material/help:",
            help="Manual de uso"
        ):

            st.subheader("Ajuda")
            mostrar_ajuda_interativa()

        with st.popover(":material/account_circle:"):

            st.caption(
                account_display_label(usuario)
            )
            st.caption(
                f"Versão: {APP_VERSION}"
            )

            if "mostrar_troca_senha" not in st.session_state:

                st.session_state["mostrar_troca_senha"] = False

            if st.button("Trocar senha"):

                st.session_state["mostrar_troca_senha"] = not st.session_state[
                    "mostrar_troca_senha"
                ]

            if st.session_state["mostrar_troca_senha"]:

                with st.form("alterar_senha_usuario"):

                    senha_atual = st.text_input(
                        "Senha atual",
                        type="password"
                    )
                    nova_senha = st.text_input(
                        "Nova senha",
                        type="password"
                    )
                    confirmar_senha = st.text_input(
                        "Confirmar nova senha",
                        type="password"
                    )
                    alterar = st.form_submit_button("Salvar nova senha")

                if alterar:

                    if not nova_senha:

                        st.error("Informe a nova senha.")

                    elif nova_senha != confirmar_senha:

                        st.error("As senhas não conferem.")

                    else:

                        sucesso, mensagem = update_password(
                            usuario["username"],
                            senha_atual,
                            nova_senha
                        )

                        if sucesso:
                            st.session_state["mostrar_troca_senha"] = False
                            registrar_log_usuario(
                                "senha_alterada",
                                usuario=usuario["username"],
                                status="sucesso",
                                detalhes={
                                    "origem": "propria_conta"
                                }
                            )
                            agendar_limpeza_cookie_auth("password_changed")
                            st.rerun()

                        else:

                            registrar_log_usuario(
                                "senha_alterada",
                                usuario=usuario["username"],
                                status="falha",
                                detalhes={
                                    "origem": "propria_conta",
                                    "mensagem": mensagem
                                }
                            )
                            st.error(mensagem)

            if st.button("Sair"):
                token = (
                    st.session_state.get("auth_token")
                    or token_cookie()
                )
                try:
                    revoke_session(token)
                except Exception as erro:
                    registrar_log_sistema(
                        "logout",
                        usuario=usuario.get("username", ""),
                        status="erro",
                        detalhes={"erro": str(erro)},
                    )
                agendar_limpeza_cookie_auth("logout")
                st.rerun()


def mostrar_lembrete_importacao_mensal():

    usuario = usuario_logado()

    if str(usuario.get("profile") or "").strip() != "Master":

        return

    status = status_importacao_mensal(
        logs=carregar_logs_sistema(
            limite=5000
        )
    )

    if not status["atrasado"]:

        return

    pendencias = ", ".join(
        status["pendencias"]
    )
    st.warning(
        "Importação mensal pendente: "
        f"{pendencias}. "
        "Acesse Sistema > Importação para atualizar as bases. "
        f"Último SNMPc: {status['ultima_importacao_snmpc_texto']}. "
        f"Última base de clientes: {status['ultima_importacao_clientes_texto']}."
    )


def preparar_sessao_usuario():

    sincronizar_token_navegador()

    if not exigir_login():

        st.stop()

    if usuario_logado().get("must_change_password"):

        mostrar_troca_senha_obrigatoria()
        st.stop()

    executar_backup_apos_login()
    mostrar_barra_superior_conta()
    mostrar_lembrete_importacao_mensal()
