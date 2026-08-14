import unittest

from app.auth import MODULES


class AuthModulesTest(unittest.TestCase):

    def test_permissoes_clientes_estao_cadastradas(self):
        chaves = {
            chave
            for chave, _rotulo in MODULES
        }

        self.assertIn("clientes", chaves)
        self.assertIn("clientes_consulta", chaves)
        self.assertIn("clientes_relatorios", chaves)
        self.assertIn("clientes_insights", chaves)
        self.assertIn("clientes_ranking", chaves)
        self.assertIn("cancelamentos_sites", chaves)
        self.assertIn("cancelamentos_consulta", chaves)
        self.assertIn("cancelamentos_editar", chaves)
        self.assertIn("cancelamentos_concluir", chaves)
        self.assertIn("insights", chaves)
        self.assertIn("insights_visao_geral", chaves)
        self.assertIn("insights_financeiro", chaves)
        self.assertIn("insights_clientes", chaves)
        self.assertIn("insights_sites", chaves)
        self.assertIn("insights_operacional", chaves)
        self.assertIn("insights_riscos", chaves)
        self.assertIn("sites_deficitarios", chaves)
        self.assertIn("sites_documentos", chaves)
        self.assertIn("viabilidade", chaves)
        self.assertIn("pre_venda", chaves)
        self.assertIn("viabilidade_consulta", chaves)
        self.assertIn("viabilidade_migracao", chaves)
        self.assertIn("viabilidade_estudos", chaves)


if __name__ == "__main__":
    unittest.main()
