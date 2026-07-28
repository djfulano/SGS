import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth import create_session
from app.auth import create_user
from app.auth import authenticate
from app.auth import authenticate_session
from app.auth import clear_login_failures
from app.auth import account_display_label
from app.auth import can_manage_users
from app.auth import can_view_values
from app.auth import has_permission
from app.auth import hash_token
from app.auth import load_profiles
from app.auth import login_lock_status
from app.auth import register_login_failure
from app.auth import revoke_user_sessions
from app.auth import save_profiles
from app.auth import validate_password
from app.auth import verify_bootstrap_token
from app.storage import read_json
from app.storage import write_json_atomic
from app.ui.session import registrar_sessao_autenticada


class AuthSessionsTest(unittest.TestCase):

    def test_novo_login_cancela_limpeza_pendente_do_cookie_antigo(self):
        estado = {
            "limpar_auth_cookie": True,
            "usuario": {"username": "antigo"},
            "auth_token": "token-antigo",
        }
        usuario = {"username": "ana", "profile": "Master"}

        registrar_sessao_autenticada(
            usuario,
            "token-novo",
            estado,
        )

        self.assertNotIn("limpar_auth_cookie", estado)
        self.assertEqual(estado["usuario"], usuario)
        self.assertEqual(estado["auth_token"], "token-novo")

    def test_create_session_expires_in_12_hours_and_tracks_inactivity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_file = Path(temp_dir) / "sessions.json"
            users_file = Path(temp_dir) / "users.json"
            write_json_atomic(
                users_file,
                {
                    "usuario": create_user(
                        "usuario",
                        "uma frase senha segura",
                    )
                },
            )

            with patch(
                "app.auth.SESSIONS_FILE",
                sessions_file
            ), patch(
                "app.auth.USERS_FILE",
                users_file
            ), patch(
                "app.auth.time.time",
                return_value=1000
            ):
                token = create_session("usuario")

            sessions = read_json(
                sessions_file,
                {}
            )
            sessao = sessions[hash_token(token)]

        self.assertEqual(
            sessao["expires_at"],
            1000 + 12 * 60 * 60
        )
        self.assertEqual(sessao["last_seen_at"], 1000)
        self.assertEqual(sessao["schema_version"], 2)

    def test_password_policy_accepts_passphrase_and_rejects_username(self):
        self.assertEqual(
            validate_password("uma frase senha longa", "ana"),
            (True, ""),
        )
        self.assertEqual(validate_password("12345678", "ana"), (True, ""))
        self.assertEqual(
            validate_password("1234567", "ana"),
            (False, "A senha deve ter pelo menos 8 caracteres."),
        )
        self.assertFalse(validate_password("UsuarioMesmo", "usuariomesmo")[0])

    def test_bootstrap_requires_configured_matching_token(self):
        with patch.dict(
            "os.environ",
            {"SGS_BOOTSTRAP_TOKEN": "token-seguro-de-inicializacao"},
        ):
            self.assertTrue(
                verify_bootstrap_token("token-seguro-de-inicializacao")
            )
            self.assertFalse(verify_bootstrap_token("outro-token"))

        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(verify_bootstrap_token("qualquer-token"))

    def test_legacy_password_hash_is_upgraded_after_login(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            users_file = Path(temp_dir) / "users.json"
            legacy = create_user("ana", "uma frase senha segura")
            from app.auth import hash_password

            old_hash = hash_password(
                "uma frase senha segura",
                iterations=200_000,
            )
            legacy.update(old_hash)
            legacy.pop("iterations", None)
            write_json_atomic(users_file, {"ana": legacy})

            with patch("app.auth.USERS_FILE", users_file):
                authenticated = authenticate("ana", "uma frase senha segura")

            upgraded = read_json(users_file, {})["ana"]

        self.assertEqual(authenticated["username"], "ana")
        self.assertEqual(upgraded["iterations"], 600_000)

    def test_profile_change_invalidates_existing_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_file = Path(temp_dir) / "sessions.json"
            users_file = Path(temp_dir) / "users.json"
            user = create_user("ana", "uma frase senha segura", "Operador")
            write_json_atomic(users_file, {"ana": user})

            with patch(
                "app.auth.SESSIONS_FILE",
                sessions_file,
            ), patch(
                "app.auth.USERS_FILE",
                users_file,
            ), patch(
                "app.auth.time.time",
                return_value=1000,
            ):
                token = create_session("ana")
                user["profile"] = "Outro"
                write_json_atomic(users_file, {"ana": user})
                authenticated = authenticate_session(token)

        self.assertIsNone(authenticated)

    def test_revoke_user_sessions_only_removes_target_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_file = Path(temp_dir) / "sessions.json"
            write_json_atomic(
                sessions_file,
                {
                    "a": {"username": "ana"},
                    "b": {"username": "bia"},
                },
            )

            with patch("app.auth.SESSIONS_FILE", sessions_file):
                removed = revoke_user_sessions("ana")

            sessions = read_json(sessions_file, {})

        self.assertEqual(removed, 1)
        self.assertEqual(list(sessions), ["b"])

    def test_login_failure_locks_after_limit_and_clear_resets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            attempts_file = Path(temp_dir) / "login_attempts.json"

            with patch(
                "app.auth.LOGIN_ATTEMPTS_FILE",
                attempts_file
            ), patch(
                "app.auth.time.time",
                return_value=1000
            ):
                for _indice in range(5):
                    register_login_failure("Usuario")

                bloqueado, segundos = login_lock_status("usuario")

                self.assertTrue(bloqueado)
                self.assertEqual(segundos, 15 * 60)

                clear_login_failures("usuario")

                bloqueado, segundos = login_lock_status("usuario")

        self.assertFalse(bloqueado)
        self.assertEqual(segundos, 0)

    def test_load_profiles_cria_master_com_todas_permissoes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "profiles.json"

            with patch(
                "app.auth.PROFILES_FILE",
                profiles_file
            ):
                profiles = load_profiles()

        self.assertIn(
            "Master",
            profiles
        )
        self.assertIn(
            "gerenciar_perfis",
            profiles["Master"]["permissions"]
        )
        self.assertTrue(
            profiles["Master"]["system"]
        )

    def test_permissao_vem_do_perfil_quando_usuario_tem_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "profiles.json"

            with patch(
                "app.auth.PROFILES_FILE",
                profiles_file
            ):
                save_profiles({
                    "Operador": {
                        "name": "Operador",
                        "permissions": [
                            "mapa",
                            "usuarios"
                        ],
                        "system": False
                    }
                })
                usuario = {
                    "username": "ana",
                    "profile": "Operador",
                }

                self.assertTrue(
                    has_permission(
                        usuario,
                        "mapa"
                    )
                )
                self.assertTrue(
                    can_manage_users(usuario)
                )
                self.assertFalse(
                    has_permission(
                        usuario,
                        "sites"
                    )
                )

    def test_usuario_sem_profile_nao_usa_permissoes_legadas(self):
        usuario = {
            "username": "legado",
            "permissions": [
                "sites"
            ]
        }

        self.assertFalse(
            has_permission(
                usuario,
                "sites"
            )
        )

    def test_profile_substitui_campos_legados_de_valores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "profiles.json"

            with patch(
                "app.auth.PROFILES_FILE",
                profiles_file
            ):
                save_profiles({
                    "Sem Valores": {
                        "name": "Sem Valores",
                        "permissions": [
                            "mapa"
                        ],
                        "system": False
                    }
                })
                usuario = {
                    "username": "joao",
                    "profile": "Sem Valores",
                    "permissions": [
                        "visualizar_valores_clientes"
                    ],
                    "can_view_values": True
                }

                self.assertFalse(
                    can_view_values(usuario)
                )

    def test_role_master_legado_nao_concede_permissao_sem_profile(self):
        usuario = {
            "username": "master_antigo",
            "role": "Master"
        }

        self.assertFalse(
            has_permission(
                usuario,
                "usuarios"
            )
        )

    def test_rotulo_usuario_conta_nao_exige_role(self):
        self.assertEqual(
            account_display_label({
                "username": "ana",
                "profile": "Operador"
            }),
            "ana (Operador)"
        )

    def test_rotulo_usuario_conta_usa_role_apenas_como_fallback_visual(self):
        self.assertEqual(
            account_display_label({
                "username": "legado",
                "role": "Adm"
            }),
            "legado (Adm)"
        )


if __name__ == "__main__":
    unittest.main()
