import unittest

from app.auth import all_permissions
from app.ui.views.system import extrair_permissoes_grade_perfil
from app.ui.views.system import grupo_permissao_perfil
from app.ui.views.system import montar_grade_permissoes_perfil


class ProfilePermissionsGridTest(unittest.TestCase):

    def test_grupo_usa_modulo_antes_do_separador(self):
        self.assertEqual(
            grupo_permissao_perfil(
                "gerenciar_sites_contatos",
                "Gerenciamento de Sites > Contatos"
            ),
            "Gerenciamento de Sites"
        )

    def test_grupo_permissoes_especiais(self):
        self.assertEqual(
            grupo_permissao_perfil(
                "editar_produtos",
                "Editar produtos"
            ),
            "Produtos"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "visualizar_valores_clientes",
                "Visualizar valores dos clientes"
            ),
            "Valores"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "importar_dados",
                "Executar importações"
            ),
            "Sistema"
        )

    def test_grade_marca_permissoes_atuais(self):
        df_grade = montar_grade_permissoes_perfil(
            [
                "mapa",
                "editar_sites"
            ],
            {}
        )

        selecionadas = set(
            df_grade.loc[
                df_grade["Selecionar"],
                "Chave"
            ]
        )

        self.assertEqual(
            selecionadas,
            {
                "mapa",
                "editar_sites"
            }
        )

    def test_extrai_chaves_selecionadas_da_grade(self):
        df_grade = montar_grade_permissoes_perfil(
            [
                "mapa"
            ],
            {}
        )
        df_grade.loc[
            df_grade["Chave"] == "editar_sites",
            "Selecionar"
        ] = True
        df_grade.loc[
            df_grade["Chave"] == "mapa",
            "Selecionar"
        ] = False

        permissoes = extrair_permissoes_grade_perfil(df_grade)

        self.assertIn(
            "editar_sites",
            permissoes
        )
        self.assertNotIn(
            "mapa",
            permissoes
        )

    def test_master_pode_marcar_todas_permissoes_na_grade(self):
        df_grade = montar_grade_permissoes_perfil(
            all_permissions(),
            {}
        )

        self.assertEqual(
            set(
                extrair_permissoes_grade_perfil(df_grade)
            ),
            set(
                all_permissions()
            )
        )


if __name__ == "__main__":
    unittest.main()
