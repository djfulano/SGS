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
                "Produtos > Editar produtos"
            ),
            "Produtos"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "visualizar_valores_clientes",
                "Valores > Visualizar valores dos clientes"
            ),
            "Valores"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "importar_dados",
                "Sistema > Executar importações"
            ),
            "Sistema"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "suporte_agendamento",
                "Suporte > Agendamento"
            ),
            "Suporte"
        )
        self.assertEqual(
            grupo_permissao_perfil(
                "retirada",
                "Suporte > Retirada"
            ),
            "Suporte"
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

    def test_grade_ordena_por_modulo_logico(self):
        df_grade = montar_grade_permissoes_perfil(
            [],
            {}
        )
        grupos = df_grade["Módulo"].drop_duplicates().tolist()

        self.assertLess(
            grupos.index("Gerenciamento de Sites"),
            grupos.index("Clientes")
        )
        self.assertLess(
            grupos.index("Equipamentos"),
            grupos.index("Suporte")
        )
        self.assertLess(
            grupos.index("Sistema"),
            grupos.index("Valores")
        )

    def test_permissoes_de_suporte_e_equipamentos_ficam_em_grupos_corretos(self):
        df_grade = montar_grade_permissoes_perfil(
            [],
            {}
        )
        grupos_por_chave = dict(
            zip(
                df_grade["Chave"],
                df_grade["Módulo"]
            )
        )

        self.assertEqual(
            grupos_por_chave["suporte_agendamento"],
            "Suporte"
        )
        self.assertEqual(
            grupos_por_chave["predios"],
            "Suporte"
        )
        self.assertEqual(
            grupos_por_chave["retirada"],
            "Suporte"
        )
        self.assertEqual(
            grupos_por_chave["equipamentos_por_site"],
            "Equipamentos"
        )
        self.assertEqual(
            grupos_por_chave["base_equipamentos"],
            "Equipamentos"
        )
        self.assertEqual(
            grupos_por_chave["importacao"],
            "Sistema"
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
