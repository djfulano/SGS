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
from app.storage import write_json_atomic


class UsersFileError(RuntimeError):

    pass

MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60

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
    ("financeiro_historico_site", "Financeiro > Histórico por Site"),
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
        users
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
    return read_json(
        PROFILES_FILE,
        {}
    )


def load_profiles():
    return ensure_profiles()


def save_profiles(profiles):
    write_json_atomic(
        PROFILES_FILE,
        profiles
    )


def load_sessions():
    return read_json(
        SESSIONS_FILE,
        {}
    )


def save_sessions(sessions):
    write_json_atomic(
        SESSIONS_FILE,
        sessions
    )


def load_login_attempts():
    return read_json(
        LOGIN_ATTEMPTS_FILE,
        {}
    )


def save_login_attempts(attempts):
    write_json_atomic(
        LOGIN_ATTEMPTS_FILE,
        attempts
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
            attempts.pop(
                chave,
                None
            )
            save_login_attempts(attempts)

        return False, 0

    return True, locked_until - agora


def register_login_failure(username):
    chave = chave_login_attempt(username)

    if not chave:

        return 0

    attempts = load_login_attempts()
    registro = attempts.get(
        chave,
        {}
    )
    falhas = int(
        registro.get("failures") or 0
    ) + 1
    registro = {
        "failures": falhas,
        "last_failure_at": int(time.time()),
        "locked_until": 0
    }

    if falhas >= MAX_LOGIN_FAILURES:
        registro["locked_until"] = int(time.time()) + LOGIN_LOCK_SECONDS

    attempts[chave] = registro
    save_login_attempts(attempts)

    return falhas


def clear_login_failures(username):
    chave = chave_login_attempt(username)

    if not chave:

        return

    attempts = load_login_attempts()
    attempts.pop(
        chave,
        None
    )
    save_login_attempts(attempts)


def hash_token(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def limpar_sessoes_expiradas(sessions):

    agora = int(time.time())

    return {
        chave: sessao
        for chave, sessao in sessions.items()
        if int(sessao.get("expires_at", 0)) > agora
    }


def create_session(username, hours=24):

    token = secrets.token_urlsafe(32)
    sessions = limpar_sessoes_expiradas(
        load_sessions()
    )
    sessions[hash_token(token)] = {
        "username": username,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + hours * 60 * 60
    }
    save_sessions(sessions)

    return token


def authenticate_session(token):

    if not token:

        return None

    sessions = limpar_sessoes_expiradas(
        load_sessions()
    )
    token_hash = hash_token(token)
    sessao = sessions.get(token_hash)

    if not sessao:

        save_sessions(sessions)

        return None

    users = load_users()
    user = users.get(sessao.get("username"))

    if not user:

        sessions.pop(
            token_hash,
            None
        )
        save_sessions(sessions)

        return None

    save_sessions(sessions)

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

    sessions = load_sessions()
    sessions.pop(
        hash_token(token),
        None
    )
    save_sessions(sessions)


def hash_password(password, salt=None):

    if salt is None:

        salt = os.urandom(16)

    if isinstance(salt, str):

        salt = base64.b64decode(salt.encode("ascii"))

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000
    )

    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii")
    }


def verify_password(password, user):

    password_hash = hash_password(
        password,
        user["salt"]
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

    password_data = hash_password(new_password)
    user["salt"] = password_data["salt"]
    user["hash"] = password_data["hash"]
    user["must_change_password"] = False
    users[username] = user

    save_users(users)

    return True, "Senha atualizada."


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

    password_data = hash_password(password)

    return {
        "username": username,
        "profile": str(profile or "").strip(),
        "must_change_password": bool(must_change_password),
        "salt": password_data["salt"],
        "hash": password_data["hash"]
    }


def authenticate(username, password):

    users = load_users()
    user = users.get(username)

    if not user:

        return None

    if not verify_password(password, user):

        return None

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
