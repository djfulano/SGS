import base64
import hashlib
import hmac
import os
import secrets
import time

from app.config import LOGIN_ATTEMPTS_FILE
from app.config import PROFILES_FILE
from app.config import SESSIONS_FILE
from app.config import USERS_FILE
from app.storage import read_json
from app.storage import read_json_authoritative
from app.storage import update_json_atomic
from app.storage import write_json_atomic


class UsersFileError(RuntimeError):

    pass

MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_ITERATIONS = 200_000
SESSION_ABSOLUTE_SECONDS = 12 * 60 * 60
SESSION_IDLE_SECONDS = 60 * 60
SESSION_TOUCH_INTERVAL_SECONDS = 5 * 60
SESSION_SCHEMA_VERSION = 2

MODULES = [
    ("resumo_superior", "Resumo > Barra superior"),
    ("sites", "Topologia"),
    ("gerenciar_sites", "Gerenciamento de Sites"),
    ("gerenciar_sites_resumo_financeiro", "Gerenciamento de Sites > Resumo Financeiro"),
    ("gerenciar_sites_detalhes", "Gerenciamento de Sites > Detalhes"),
    ("gerenciar_sites_arquivos", "Gerenciamento de Sites > Documentos"),
    ("gerenciar_sites_contatos", "Gerenciamento de Sites > Contatos"),
    ("gerenciar_sites_editar", "Gerenciamento de Sites > Editar"),
    ("clientes", "Clientes"),
    ("clientes_consulta", "Clientes > Consulta"),
    ("clientes_resumo_assinaturas", "Clientes > Resumo de Clientes"),
    ("clientes_custos_sites", "Clientes > Custos por Cliente"),
    ("clientes_relatorios", "Clientes > Relatórios"),
    ("clientes_insights", "Clientes > Insights"),
    ("insights", "Insights"),
    ("insights_visao_geral", "Insights > Visão Geral"),
    ("insights_financeiro", "Insights > Financeiro"),
    ("insights_clientes", "Insights > Clientes"),
    ("insights_sites", "Insights > Sites"),
    ("insights_operacional", "Insights > Operacional"),
    ("insights_riscos", "Insights > Riscos"),
    ("analises_conciliacao", "Análises e Conciliação"),
    ("conciliacao_sites", "Análises e Conciliação > Conciliação SNMPc x Sites"),
    ("ranking", "Análises e Conciliação > Ranking"),
    ("relatorio_gerencial", "Análises e Conciliação > Relatório Gerencial"),
    ("custos_receita", "Análises e Conciliação > Custos x Receita"),
    ("sites_deficitarios", "Análises e Conciliação > Sites Deficitários"),
    ("sites_documentos", "Análises e Conciliação > Sites x Documentos"),
    ("pagamentos_sem_site", "Análises e Conciliação > Pagamentos sem site"),
    ("sem_vinculo", "Análises e Conciliação > Sem Vínculo"),
    ("sites_sem_clientes", "Análises e Conciliação > Sites sem Clientes"),
    ("clientes_snmpc_cancelados", "Análises e Conciliação > Clientes no SNMPc Cancelado"),
    ("ferramentas", "Equipamentos"),
    ("enlaces", "Equipamentos > Enlaces"),
    ("equipamentos_por_site", "Equipamentos > Equipamentos por Site"),
    ("buscar_equipamentos", "Equipamentos > Buscar Equipamentos"),
    ("base_equipamentos", "Equipamentos > Editar Equipamentos"),
    ("editar_base_equipamentos", "Equipamentos > Editar Base de Equipamentos"),
    ("suporte", "Suporte"),
    ("suporte_agendamento", "Suporte > Agendamento"),
    ("retirada", "Suporte > Retirada"),
    ("predios", "Suporte > Prédios"),
    ("viabilidade", "Viabilidade"),
    ("viabilidade_consulta", "Viabilidade > Viabilidade"),
    ("viabilidade_migracao", "Viabilidade > Migração"),
    ("viabilidade_oportunidades_site", "Viabilidade > Oportunidades por Site"),
    ("viabilidade_estudos", "Viabilidade > Estudos de Engenharia"),
    ("gestao_viabilidades", "Viabilidade > Gestão de Viabilidades"),
    ("gestao_viabilidades_dashboard", "Viabilidade > Dashboard"),
    ("gestao_viabilidades_consulta", "Viabilidade > Histórico"),
    ("gestao_viabilidades_importar", "Viabilidade > Importação"),
    ("financeiro", "Financeiro"),
    ("financeiro_dashboard", "Financeiro > Dashboard"),
    ("financeiro_alertas_criticos", "Financeiro > Alertas de Sites Críticos"),
    ("financeiro_prioridades", "Financeiro > Prioridades"),
    ("financeiro_historico_site", "Financeiro > Histórico por Site"),
    ("financeiro_relatorio", "Financeiro > Relatório"),
    ("financeiro_pagamentos", "Financeiro > Pagamentos"),
    ("financeiro_acordos", "Financeiro > Acordos"),
    ("financeiro_conciliacao", "Financeiro > Conciliação"),
    ("financeiro_importar", "Financeiro > Importação"),
    ("financeiro_exportacoes", "Financeiro > Exportações"),
    ("financeiro_editar", "Financeiro > Editar"),
    ("mapa", "Mapa"),
    ("produtos", "Produtos"),
    ("sva", "Produtos > SVA"),
    ("editar_produtos", "Produtos > Editar Produtos"),
    ("historico", "Histórico"),
    ("sites_removidos", "Histórico > Sites Removidos"),
    ("clientes_cancelados", "Histórico > Clientes Cancelados"),
    ("sistema", "Sistema"),
    ("importacao", "Sistema > Importação"),
    ("importar_dados", "Sistema > Executar Importações"),
    ("logs", "Sistema > LOG"),
    ("configuracoes", "Sistema > Configurações"),
    ("editar_configuracoes", "Sistema > Editar Configurações"),
    ("backup", "Sistema > Backup"),
    ("exportacoes", "Sistema > Exportações"),
    ("usuarios", "Sistema > Usuários"),
    ("gerenciar_perfis", "Sistema > Perfis"),
    ("editar_sites", "Ação > Editar cadastro de sites"),
    ("incluir_contatos_sites", "Ação > Incluir contatos dos sites"),
    ("editar_contatos_sites", "Ação > Editar contatos dos sites"),
    ("gerenciar_contatos_arquivados_sites", "Ação > Gerenciar contatos arquivados dos sites"),
    ("editar_contratos_sites", "Ação > Editar documentos dos sites"),
    ("visualizar_valores_clientes", "Valores > Visualizar valores dos clientes"),
    ("visualizar_valores_custos", "Valores > Visualizar valores de custos"),
    ("copiar_tabelas", "Tabelas > Copiar tabelas")
]


def load_users():
    return read_json(
        USERS_FILE,
        {},
        strict=True,
        error_factory=lambda caminho: UsersFileError(
            f"Arquivo de usuários inválido: {USERS_FILE}"
        )
    )


def save_users(users):
    write_json_atomic(
        USERS_FILE,
        users,
        backup_previous=True,
    )


def update_users_atomic(updater):
    return update_json_atomic(
        USERS_FILE,
        {},
        updater,
        authoritative=True,
        backup_previous=True,
    )


def default_profiles():
    return {
        "Master": {
            "name": "Master",
            "permissions": all_permissions(),
            "system": True
        }
    }


def normalize_profile(profile):
    if not isinstance(profile, dict):
        profile = {}

    name = str(profile.get("name") or "").strip()
    permissions = [
        permission
        for permission in profile.get("permissions", [])
        if permission in all_permissions()
    ]

    return {
        "name": name,
        "permissions": sorted(set(permissions)),
        "system": bool(profile.get("system"))
    }


def ensure_profiles(profiles=None):
    profiles = dict(profiles or load_profiles_raw())
    defaults = default_profiles()
    changed = False

    for name, profile in defaults.items():
        if name not in profiles:
            profiles[name] = profile
            changed = True

    for name, profile in list(profiles.items()):
        normalized = normalize_profile({
            **profile,
            "name": profile.get("name") or name
        })
        if name == "Master":
            normalized["permissions"] = all_permissions()
            normalized["system"] = True

        if normalized != profile:
            profiles[name] = normalized
            changed = True

    if changed:
        save_profiles(profiles)

    return profiles


def load_profiles_raw():
    return read_json_authoritative(
        PROFILES_FILE,
        {}
    )


def load_profiles():
    return ensure_profiles()


def save_profiles(profiles):
    write_json_atomic(
        PROFILES_FILE,
        profiles,
        backup_previous=True,
    )


def update_profiles_atomic(updater):
    return update_json_atomic(
        PROFILES_FILE,
        {},
        updater,
        authoritative=True,
        backup_previous=True,
    )


def load_sessions():
    return read_json_authoritative(
        SESSIONS_FILE,
        {}
    )


def save_sessions(sessions):
    write_json_atomic(
        SESSIONS_FILE,
        sessions,
        backup_previous=True,
    )


def load_login_attempts():
    return read_json_authoritative(
        LOGIN_ATTEMPTS_FILE,
        {}
    )


def save_login_attempts(attempts):
    write_json_atomic(
        LOGIN_ATTEMPTS_FILE,
        attempts,
        backup_previous=True,
    )


def chave_login_attempt(username):
    return str(
        username
        or ""
    ).strip().casefold()


def login_lock_status(username):
    chave = chave_login_attempt(username)

    if not chave:

        return False, 0

    attempts = load_login_attempts()
    registro = attempts.get(chave) or {}
    locked_until = int(
        registro.get("locked_until") or 0
    )
    agora = int(time.time())

    if locked_until <= agora:

        if locked_until:
            update_json_atomic(
                LOGIN_ATTEMPTS_FILE,
                {},
                lambda current: {
                    key: value
                    for key, value in current.items()
                    if key != chave
                },
                authoritative=True,
                backup_previous=True,
            )

        return False, 0

    return True, locked_until - agora


def register_login_failure(username):
    chave = chave_login_attempt(username)

    if not chave:

        return 0

    falhas = 0

    def add_failure(attempts):
        nonlocal falhas
        registro = attempts.get(chave, {})
        falhas = int(registro.get("failures") or 0) + 1
        registro = {
            "failures": falhas,
            "last_failure_at": int(time.time()),
            "locked_until": 0,
        }
        if falhas >= MAX_LOGIN_FAILURES:
            registro["locked_until"] = int(time.time()) + LOGIN_LOCK_SECONDS
        attempts[chave] = registro
        return attempts

    update_json_atomic(
        LOGIN_ATTEMPTS_FILE,
        {},
        add_failure,
        authoritative=True,
        backup_previous=True,
    )

    return falhas


def clear_login_failures(username):
    chave = chave_login_attempt(username)

    if not chave:

        return

    update_json_atomic(
        LOGIN_ATTEMPTS_FILE,
        {},
        lambda attempts: {
            key: value
            for key, value in attempts.items()
            if key != chave
        },
        authoritative=True,
        backup_previous=True,
    )


def hash_token(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def validate_password(password, username=""):
    password = str(password or "")
    username = str(username or "").strip()

    if len(password) < PASSWORD_MIN_LENGTH:
        return (
            False,
            f"A senha deve ter pelo menos {PASSWORD_MIN_LENGTH} caracteres."
        )

    if len(password) > PASSWORD_MAX_LENGTH:
        return (
            False,
            f"A senha deve ter no máximo {PASSWORD_MAX_LENGTH} caracteres."
        )

    if username and hmac.compare_digest(
        password.casefold(),
        username.casefold()
    ):
        return False, "A senha não pode ser igual ao nome do usuário."

    return True, ""


def bootstrap_token_configured():
    return bool(str(os.getenv("SGS_BOOTSTRAP_TOKEN") or "").strip())


def verify_bootstrap_token(informed_token):
    configured_token = str(os.getenv("SGS_BOOTSTRAP_TOKEN") or "").strip()
    informed_token = str(informed_token or "")

    if not configured_token:
        return False

    return hmac.compare_digest(
        informed_token.encode("utf-8"),
        configured_token.encode("utf-8")
    )


def user_session_fingerprint(user):
    fields = (
        str(user.get("username") or ""),
        str(user.get("profile") or ""),
        str(user.get("hash") or ""),
        "1" if user.get("must_change_password") else "0",
    )
    return hashlib.sha256(
        "\x1f".join(fields).encode("utf-8")
    ).hexdigest()


def limpar_sessoes_expiradas(sessions):

    agora = int(time.time())

    return {
        chave: sessao
        for chave, sessao in sessions.items()
        if (
            int(sessao.get("schema_version", 0)) == SESSION_SCHEMA_VERSION
            and int(sessao.get("expires_at", 0)) > agora
            and (
                agora - int(sessao.get("last_seen_at", 0))
                <= SESSION_IDLE_SECONDS
            )
        )
    }


def create_session(username):

    token = secrets.token_urlsafe(32)
    agora = int(time.time())
    users = load_users()
    user = users.get(username)

    if not user:
        raise UsersFileError("Usuário não encontrado para criar a sessão.")

    session_record = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "username": username,
        "created_at": agora,
        "last_seen_at": agora,
        "expires_at": agora + SESSION_ABSOLUTE_SECONDS,
        "user_fingerprint": user_session_fingerprint(user)
    }

    def add_session(sessions):
        sessions = limpar_sessoes_expiradas(sessions)
        sessions[hash_token(token)] = session_record
        return sessions

    update_json_atomic(
        SESSIONS_FILE,
        {},
        add_session,
        authoritative=True,
        backup_previous=True,
    )

    return token


def authenticate_session(token):

    if not token:

        return None

    sessions_original = load_sessions()
    sessions = limpar_sessoes_expiradas(sessions_original)
    token_hash = hash_token(token)
    sessao = sessions.get(token_hash)

    if not sessao:
        if sessions != sessions_original:
            update_json_atomic(
                SESSIONS_FILE,
                {},
                limpar_sessoes_expiradas,
                authoritative=True,
                backup_previous=True,
            )

        return None

    users = load_users()
    user = users.get(sessao.get("username"))

    if (
        not user
        or not hmac.compare_digest(
            str(sessao.get("user_fingerprint") or ""),
            user_session_fingerprint(user)
        )
    ):

        update_json_atomic(
            SESSIONS_FILE,
            {},
            lambda current: {
                key: value
                for key, value in current.items()
                if key != token_hash
            },
            authoritative=True,
            backup_previous=True,
        )

        return None

    agora = int(time.time())
    ultima_atividade = int(sessao.get("last_seen_at", 0))

    if agora - ultima_atividade >= SESSION_TOUCH_INTERVAL_SECONDS:
        expected_fingerprint = str(sessao.get("user_fingerprint") or "")

        def touch_session(current):
            current_session = current.get(token_hash)
            if (
                current_session
                and hmac.compare_digest(
                    str(current_session.get("user_fingerprint") or ""),
                    expected_fingerprint,
                )
            ):
                current_session["last_seen_at"] = agora
                current[token_hash] = current_session
            return limpar_sessoes_expiradas(current)

        update_json_atomic(
            SESSIONS_FILE,
            {},
            touch_session,
            authoritative=True,
            backup_previous=True,
        )
    elif sessions != sessions_original:
        update_json_atomic(
            SESSIONS_FILE,
            {},
            limpar_sessoes_expiradas,
            authoritative=True,
            backup_previous=True,
        )

    return {
        key: value
        for key, value in user.items()
        if key not in {
            "salt",
            "hash"
        }
    }


def revoke_session(token):

    if not token:

        return

    token_hash = hash_token(token)

    def remove_session(sessions):
        sessions.pop(token_hash, None)
        return sessions

    update_json_atomic(
        SESSIONS_FILE,
        {},
        remove_session,
        authoritative=True,
        backup_previous=True,
    )


def revoke_user_sessions(username):
    username = str(username or "").strip()

    if not username:
        return 0

    removed = 0

    def remove_sessions(sessions):
        nonlocal removed
        filtered = {
            key: session
            for key, session in sessions.items()
            if str(session.get("username") or "") != username
        }
        removed = len(sessions) - len(filtered)
        return filtered

    update_json_atomic(
        SESSIONS_FILE,
        {},
        remove_sessions,
        authoritative=True,
        backup_previous=True,
    )

    return removed


def revoke_all_sessions():
    update_json_atomic(
        SESSIONS_FILE,
        {},
        lambda _sessions: {},
        authoritative=True,
        backup_previous=True,
    )


def hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):

    if salt is None:

        salt = os.urandom(16)

    if isinstance(salt, str):

        salt = base64.b64decode(salt.encode("ascii"))

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        int(iterations)
    )

    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
        "iterations": int(iterations)
    }


def verify_password(password, user):
    iterations = int(
        user.get("iterations")
        or LEGACY_PBKDF2_ITERATIONS
    )

    password_hash = hash_password(
        password,
        user["salt"],
        iterations=iterations
    )

    return hmac.compare_digest(
        password_hash["hash"],
        user["hash"]
    )


def update_password(username, current_password, new_password):
    users = load_users()
    user = users.get(username)

    if not user:

        return False, "Usuário não encontrado."

    if not verify_password(
        current_password,
        user
    ):

        return False, "Senha atual inválida."

    valid, message = validate_password(new_password, username)

    if not valid:
        return False, message

    password_data = hash_password(new_password)

    def apply_password(current_users):
        current_user = current_users.get(username)
        if not current_user:
            raise UsersFileError("Usuário não encontrado.")
        current_user = dict(current_user)
        current_user["salt"] = password_data["salt"]
        current_user["hash"] = password_data["hash"]
        current_user["iterations"] = password_data["iterations"]
        current_user["must_change_password"] = False
        current_users[username] = current_user
        return current_users

    update_users_atomic(apply_password)
    revoke_user_sessions(username)

    return True, "Senha atualizada. Entre novamente para continuar."


def all_permissions():

    return [
        key
        for key, _label in MODULES
    ]


def create_user(
    username,
    password,
    profile="Master",
    must_change_password=True,
):
    valid, message = validate_password(password, username)

    if not valid:
        raise ValueError(message)

    password_data = hash_password(password)

    return {
        "username": username,
        "profile": str(profile or "").strip(),
        "must_change_password": bool(must_change_password),
        "salt": password_data["salt"],
        "hash": password_data["hash"],
        "iterations": password_data["iterations"]
    }


def authenticate(username, password):

    users = load_users()
    user = users.get(username)

    if not user:

        return None

    if not verify_password(password, user):

        return None

    current_iterations = int(
        user.get("iterations")
        or LEGACY_PBKDF2_ITERATIONS
    )

    if current_iterations < PBKDF2_ITERATIONS:
        password_data = hash_password(password)

        def upgrade_hash(current_users):
            current_user = dict(current_users.get(username) or {})
            if not current_user:
                return current_users
            current_user["salt"] = password_data["salt"]
            current_user["hash"] = password_data["hash"]
            current_user["iterations"] = password_data["iterations"]
            current_users[username] = current_user
            return current_users

        users = update_users_atomic(upgrade_hash)
        user = users[username]

    return {
        key: value
        for key, value in user.items()
        if key not in {
            "salt",
            "hash"
        }
    }


def has_permission(user, permission):

    if not user:

        return False

    return permission in effective_permissions(user)


def effective_permissions(user):
    if not user:
        return []

    profile_name = str(user.get("profile") or "").strip()

    if not profile_name:
        return []

    profiles = load_profiles()
    profile = profiles.get(profile_name)

    if not profile:
        return []

    if profile_name == "Master":
        return all_permissions()

    return sorted(set(profile.get("permissions", [])))


def can_manage_users(user):

    return has_permission(
        user,
        "usuarios"
    )


def can_view_values(user):

    if not user:

        return False

    return has_permission(
        user,
        "visualizar_valores_clientes"
    )


def can_view_cost_values(user):
    return has_permission(
        user,
        "visualizar_valores_custos"
    )


def can_view_top_summary(user):
    return has_permission(
        user,
        "resumo_superior"
    )


def can_copy_tables(user):
    return has_permission(
        user,
        "copiar_tabelas"
    )


def account_display_label(user):
    user = user or {}
    username = str(
        user.get("username")
        or "Usuário"
    ).strip()
    profile = str(
        user.get("profile")
        or user.get("role")
        or "Sem perfil"
    ).strip()

    return f"{username} ({profile})"
