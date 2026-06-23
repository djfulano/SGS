import unittest

from app.models.cliente import Cliente
from app.models.site import Site


class SiteTest(unittest.TestCase):

    def test_receita_soma_clientes_e_filhos(self):
        raiz = Site("POP_A", "POP")
        filho = Site("BH_A", "BH")

        raiz.adicionar_cliente(Cliente("Cliente 1", 100.5, "12345678"))
        filho.adicionar_cliente(Cliente("Cliente 2", 50, "87654321"))
        raiz.adicionar_filho(filho)

        self.assertEqual(raiz.calcular_receita(), 150.5)

    def test_nao_cria_ciclo_na_arvore(self):
        raiz = Site("POP_A", "POP")
        filho = Site("BH_A", "BH")

        self.assertTrue(raiz.adicionar_filho(filho))
        self.assertFalse(filho.adicionar_filho(raiz))
        self.assertIs(filho.pai, raiz)


if __name__ == "__main__":
    unittest.main()
