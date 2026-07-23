import json

import streamlit as st

from app.auth import UsersFileError
from app.auth import account_display_label
from app.auth import authenticate
from app.auth import authenticate_session
from app.auth import clear_login_failures
from app.auth import create_session
from app.auth import create_user
from app.auth import load_users
from app.auth import login_lock_status
from app.auth import register_login_failure
from app.auth import revoke_session
from app.auth import save_users
from app.auth import update_password
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
AUTH_COOKIE_MAX_AGE = 24 * 60 * 60


def usuario_logado():

    return st.session_state.get("usuario")


def token_cookie():

    try:

        return st.context.cookies.get(AUTH_COOKIE_NAME, "")

    except Exception:

        return ""


def script_limpar_cookie_auth():

    return f"""
    <script>
        const cookieName = {json.dumps(AUTH_COOKIE_NAME)};
        const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
        window.parent.document.cookie = `${{cookieName}}=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax${{secure}}`;
        const url = new URL(window.parent.location.href);
        url.searchParams.delete("logout");
        window.parent.location.replace(url.toString());
    </script>
    """


def renderizar_limpeza_cookie_auth():

    st.info("Saindo...")
    st.html(
        script_limpar_cookie_auth(),
        unsafe_allow_javascript=True
    )


def sincronizar_token_navegador():

    token = st.session_state.get("auth_token")

    if st.query_params.get("logout") is not None:

        try:

            del st.query_params["logout"]

        except KeyError:

            pass

    if st.session_state.pop("limpar_auth_cookie", False):

        renderizar_limpeza_cookie_auth()
        st.stop()

    if token:

        st.html(
            f"""
            <script>
                const cookieName = {json.dumps(AUTH_COOKIE_NAME)};
                const token = {json.dumps(token)};
                const maxAge = {AUTH_COOKIE_MAX_AGE};
                const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
                const cookieValue = `${{cookieName}}=${{encodeURIComponent(token)}}; Max-Age=${{maxAge}}; path=/; SameSite=Lax${{secure}}`;
                window.parent.document.cookie = cookieValue;
            </script>
            """,
            unsafe_allow_javascript=True
        )


def configurar_primeiro_master():

    st.markdown(
        bloco_identidade_sgs("sgt-login-hero"),
        unsafe_allow_html=True
    )

    st.warning(
        "Nenhum usuário cadastrado. Crie o primeiro usuário Master."
    )

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

    with st.form("login"):

        usuario = st.text_input("Usuário")
        senha = st.text_input(
            "Senha",
            type="password"
        )
        entrar = st.form_submit_button("Entrar")

    if entrar:

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
            st.error(
                f"Muitas tentativas inválidas. Tente novamente em {minutos} minuto(s)."
            )
            return False

        autenticado = authenticate(
            usuario,
            senha
        )

        if autenticado:

            clear_login_failures(
                usuario
            )
            st.session_state["usuario"] = autenticado

            token = create_session(usuario)
            st.session_state["auth_token"] = token

            registrar_log_usuario(
                "login",
                usuario=usuario,
                status="sucesso"
            )
            st.rerun()

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
        st.error("Usuário ou senha inválidos.")

    return False


def exigir_login():

    if usuario_logado():

        return True

    token = token_cookie()

    if token:

        try:

            autenticado = authenticate_session(token)

        except UsersFileError as erro:

            st.error(str(erro))
            st.stop()

        if autenticado:

            st.session_state["usuario"] = autenticado
            st.session_state["auth_token"] = token
            registrar_log_usuario(
                "login_token",
                usuario=autenticado["username"],
                status="sucesso"
            )

            return True

        st.session_state.pop(
            "usuario",
            None
        )
        st.session_state.pop(
            "auth_token",
            None
        )

    try:

        users = load_users()

    except UsersFileError as erro:

        st.error(str(erro))
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

            users = load_users()
            usuario_atualizado = users.get(
                usuario["username"],
                usuario
            )
            st.session_state["usuario"] = {
                key: value
                for key, value in usuario_atualizado.items()
                if key not in {
                    "salt",
                    "hash"
                }
            }
            registrar_log_usuario(
                "senha_alterada",
                usuario=usuario["username"],
                status="sucesso",
                detalhes={
                    "origem": "primeiro_login"
                }
            )
            st.success(mensagem)
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

                            users = load_users()
                            usuario_atualizado = users.get(
                                usuario["username"],
                                usuario
                            )
                            st.session_state["usuario"] = {
                                key: value
                                for key, value in usuario_atualizado.items()
                                if key not in {
                                    "salt",
                                    "hash"
                                }
                            }
                            st.session_state["mostrar_troca_senha"] = False
                            registrar_log_usuario(
                                "senha_alterada",
                                usuario=usuario["username"],
                                status="sucesso",
                                detalhes={
                                    "origem": "propria_conta"
                                }
                            )
                            st.success(mensagem)

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

                revoke_session(
                    st.session_state.get("auth_token")
                    or token_cookie()
                )
                st.session_state.pop(
                    "usuario",
                    None
                )
                st.session_state.pop(
                    "auth_token",
                    None
                )
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
