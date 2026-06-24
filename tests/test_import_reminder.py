from datetime import date
import unittest

from app.services.import_reminder import status_importacao_mensal


def log_importacao(data, *, snmpc=False, clientes=False, status="sucesso"):
    return {
        "data_hora": f"{data}T10:00:00-03:00",
        "evento": "aplicar_importacao",
        "status": status,
        "detalhes": {
            "snmpc_enviado": snmpc,
            "clientes_enviado": clientes,
            "data_importacao": data
        }
    }


class ImportReminderTest(unittest.TestCase):

    def test_sem_importacao_pende_snmpc_e_clientes(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 1),
            logs=[]
        )

        self.assertTrue(
            status["atrasado"]
        )
        self.assertEqual(
            status["pendencias"],
            [
                "SNMPc",
                "Base de clientes"
            ]
        )

    def test_importou_so_snmpc_no_mes_pende_clientes(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 15),
            logs=[
                log_importacao(
                    "2026-06-02",
                    snmpc=True
                )
            ]
        )

        self.assertEqual(
            status["pendencias"],
            [
                "Base de clientes"
            ]
        )

    def test_importou_so_clientes_no_mes_pende_snmpc(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 15),
            logs=[
                log_importacao(
                    "2026-06-02",
                    clientes=True
                )
            ]
        )

        self.assertEqual(
            status["pendencias"],
            [
                "SNMPc"
            ]
        )

    def test_importou_snmpc_e_clientes_no_mes_nao_pende(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 15),
            logs=[
                log_importacao(
                    "2026-06-02",
                    snmpc=True
                ),
                log_importacao(
                    "2026-06-03",
                    clientes=True
                )
            ]
        )

        self.assertFalse(
            status["atrasado"]
        )
        self.assertEqual(
            status["pendencias"],
            []
        )

    def test_importacao_mes_anterior_nao_quita_mes_atual(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 1),
            logs=[
                log_importacao(
                    "2026-05-31",
                    snmpc=True,
                    clientes=True
                )
            ]
        )

        self.assertTrue(
            status["atrasado"]
        )
        self.assertEqual(
            status["ultima_importacao_snmpc_texto"],
            "31/05/2026"
        )
        self.assertEqual(
            status["ultima_importacao_clientes_texto"],
            "31/05/2026"
        )

    def test_importacao_com_erro_nao_conta(self):
        status = status_importacao_mensal(
            agora=date(2026, 6, 15),
            logs=[
                log_importacao(
                    "2026-06-02",
                    snmpc=True,
                    clientes=True,
                    status="erro"
                )
            ]
        )

        self.assertEqual(
            status["pendencias"],
            [
                "SNMPc",
                "Base de clientes"
            ]
        )


if __name__ == "__main__":
    unittest.main()
