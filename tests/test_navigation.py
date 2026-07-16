import unittest

from app.ui.navigation import preparar_navegacao_mapa_endereco


class NavigationTest(unittest.TestCase):

    def test_prepara_mapa_geral_com_busca_do_endereco(self):
        estado = {"mapa_geral_busca_limpar_pendente": True}

        aplicado = preparar_navegacao_mapa_endereco(
            estado,
            "Rua Teste, 10"
        )

        self.assertTrue(aplicado)
        self.assertEqual(estado["mapa_subaba"], "mapa_geral")
        self.assertEqual(estado["mapa_geral_busca"], "Rua Teste, 10")
        self.assertEqual(estado["proxima_aba_principal"], "mapa")
        self.assertNotIn("mapa_geral_busca_limpar_pendente", estado)

    def test_ignora_endereco_vazio(self):
        estado = {}

        self.assertFalse(preparar_navegacao_mapa_endereco(estado, "  "))
        self.assertEqual(estado, {})


if __name__ == "__main__":
    unittest.main()
