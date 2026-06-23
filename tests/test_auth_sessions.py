import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth import create_session
from app.auth import clear_login_failures
from app.auth import account_display_label
from app.auth import can_manage_users
from app.auth import can_view_values
from app.auth import has_permission
from app.auth import hash_token
from app.auth import load_profiles
from app.auth import login_lock_status
from app.auth import register_login_failure
from app.auth import save_profiles
from app.storage import read_json


class AuthSessionsTest(unittest.TestCase):

    def test_create_session_default_expires_in_24_hours(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_file = Path(temp_dir) / "sessions.json"

            with patch(
                "app.auth.SESSIONS_FILE",
                sessions_file
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
            1000 + 24 * 60 * 60
        )

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
