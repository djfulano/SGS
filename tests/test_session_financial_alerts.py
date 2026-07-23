import unittest
from unittest.mock import Mock
from unittest.mock import patch

from app.ui import session


class SessionFinancialAlertsTest(unittest.TestCase):

    def test_preparacao_reserva_alerta_sem_calcular(self):
        destino = object()
        usuario = {
            "username": "master",
            "profile": "Master",
            "must_change_password": False,
        }

        with (
            patch.object(session, "sincronizar_token_navegador"),
            patch.object(session, "exigir_login", return_value=True),
            patch.object(session, "usuario_logado", return_value=usuario),
            patch.object(session, "executar_backup_apos_login"),
            patch.object(session, "mostrar_barra_superior_conta"),
            patch.object(
                session,
                "reservar_alertas_sites_criticos",
                return_value=destino,
            ),
            patch.object(session, "mostrar_lembrete_importacao_mensal"),
            patch.object(session, "mostrar_alertas_sites_criticos") as calcular,
        ):
            resultado = session.preparar_sessao_usuario()

        self.assertIs(resultado, destino)
        calcular.assert_not_called()

    def test_usuario_sem_permissao_nao_calcula_alertas(self):
        with (
            patch.object(session, "usuario_logado", return_value={"profile": "Leitura"}),
            patch.object(session, "has_permission", return_value=False),
            patch.object(session, "assinatura_fontes_alertas") as assinatura,
            patch.object(session, "carregar_alertas_sites_criticos_cache") as carregar,
        ):
            session.mostrar_alertas_sites_criticos()

        assinatura.assert_not_called()
        carregar.assert_not_called()

    def test_alerta_e_renderizado_no_espaco_reservado(self):
        destino = Mock()
        resultado = {
            "sites": [1, 2],
            "acordos": [1],
            "total": 3,
            "atrasados": 1,
        }
        with (
            patch.object(session, "usuario_logado", return_value={"profile": "Master"}),
            patch.object(session, "has_permission", return_value=True),
            patch.object(session, "assinatura_fontes_alertas", return_value=("assinatura",)),
            patch.object(
                session,
                "carregar_alertas_sites_criticos_cache",
                return_value=resultado,
            ) as carregar,
        ):
            session.mostrar_alertas_sites_criticos(destino)

        carregar.assert_called_once_with(("assinatura",))
        destino.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
