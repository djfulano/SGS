import unittest
from unittest.mock import patch

import pandas as pd

from app.services.site_registry_service import normalize_site_contacts
from app.services.site_registry_service import normalize_site_due_day
from app.services.site_registry_service import prepare_registry_for_save
from app.services.site_registry_service import SITE_TYPE_OPTIONS
from app.services.site_registry_service import duplicated_site_codes
from app.services.site_registry_service import validate_unique_site_codes
from app.services.site_registry_service import upsert_site
from app.ui.views.site_management import contatos_arquivados
from app.ui.views.site_management import contatos_ativos
from app.ui.views.site_management import contatos_para_exibicao
from app.ui.views.site_management import indice_tipo_contato
from app.ui.views.site_management import normalizar_tipo_contato_exibicao
from app.ui.views.site_management import nome_destaque_site
from app.ui.views.site_management import opcoes_tipo_contato
from app.ui.views.site_management import opcoes_contatos_com_indices
from app.ui.views.site_management import opcoes_cadastradas_site
from app.ui.views.site_management import opcoes_dia_vencimento_padrao
from app.ui.views.site_management import pode_visualizar_custos_site
from app.ui.views.site_management import valor_custo_site


class SiteManagementTest(unittest.TestCase):

    def test_vencimento_padrao_e_opcional_e_limitado(self):
        opcoes, indice_vazio = opcoes_dia_vencimento_padrao("")
        _opcoes, indice_atual = opcoes_dia_vencimento_padrao("18")

        self.assertEqual(opcoes[0], "")
        self.assertEqual(opcoes[-1], 28)
        self.assertEqual(indice_vazio, 0)
        self.assertEqual(opcoes[indice_atual], 18)
        self.assertEqual(normalize_site_due_day(1), 1)
        self.assertEqual(normalize_site_due_day(28), 28)

        with self.assertRaisesRegex(ValueError, "entre 1 e 28"):
            normalize_site_due_day(29)

    def test_prepara_planilha_preserva_vencimento_vazio(self):
        preparado = prepare_registry_for_save(pd.DataFrame([{
            "CÓDIGO AQUILES": "100",
            "CUSTO": "1000",
            "DIA VENCIMENTO": "",
        }]))

        self.assertEqual(preparado.iloc[0]["DIA VENCIMENTO"], "")

    def test_salva_vencimento_vazio_independente_de_site_critico(self):
        cadastro = pd.DataFrame({
            "CÓDIGO AQUILES": pd.Series(["100"], dtype="str"),
            "DIA VENCIMENTO": pd.Series(["18"], dtype="str"),
        })
        with patch(
            "app.services.site_registry_service.load_site_registry",
            return_value=cadastro,
        ), patch(
            "app.services.site_registry_service.save_site_registry",
            return_value=None,
        ) as salvar:
            upsert_site(
                {
                    "CÓDIGO AQUILES": "100",
                    "SITE CRÍTICO": "Não",
                    "DIA VENCIMENTO": "",
                },
                original_code="100",
            )

        dataframe_salvo = salvar.call_args.args[0]
        self.assertEqual(dataframe_salvo.iloc[0]["DIA VENCIMENTO"], "")

    def test_atualiza_dia_vencimento_em_coluna_textual(self):
        cadastro = pd.DataFrame({
            "CÓDIGO AQUILES": pd.Series(["100"], dtype="str"),
            "DIA VENCIMENTO": pd.Series([""], dtype="str"),
        })
        with patch(
            "app.services.site_registry_service.load_site_registry",
            return_value=cadastro,
        ), patch(
            "app.services.site_registry_service.save_site_registry",
            return_value=None,
        ) as salvar:
            upsert_site(
                {
                    "CÓDIGO AQUILES": "100",
                    "SITE CRÍTICO": "Sim",
                    "DIA VENCIMENTO": 18,
                },
                original_code="100",
            )

        dataframe_salvo = salvar.call_args.args[0]
        self.assertEqual(dataframe_salvo.iloc[0]["DIA VENCIMENTO"], 18)

    def test_nome_destaque_prioriza_nome_cadastro(self):
        self.assertEqual(
            nome_destaque_site({
                "Nome Cadastro": "VITA ALTO DA LAPA",
                "Site SNMPc": "VIT_POP_105743_IP",
                "Busca": "texto composto"
            }),
            "VITA ALTO DA LAPA"
        )

    def test_custo_fica_restrito_sem_permissao(self):
        with patch(
            "app.ui.views.site_management.has_permission",
            return_value=False
        ):
            self.assertFalse(pode_visualizar_custos_site({"profile": "NOC"}))
            self.assertEqual(valor_custo_site(1234.56), "Restrito")

    def test_custo_e_formatado_com_permissao(self):
        with patch(
            "app.ui.views.site_management.has_permission",
            return_value=True
        ), patch(
            "app.ui.views.site_management._formatar_moeda",
            side_effect=lambda valor: f"R$ {valor:.2f}"
        ):
            self.assertTrue(pode_visualizar_custos_site({"profile": "Master"}))
            self.assertEqual(valor_custo_site(1234.56), "R$ 1234.56")

    def test_detecta_codigos_repetidos_dos_sites(self):
        df = pd.DataFrame([
            {
                "CÓDIGO AQUILES": "100",
                "CÓDIGO MICROSIGA": "200",
                "CÓDIGO CONDOMINIO": "300",
                "ABREVIAÇÃO": "POPA",
                "SMNPC": "POP_A",
                "NOME": "Site A",
                "Favorecido": "Fornecedor A",
                "Status": "Ativo"
            },
            {
                "CÓDIGO AQUILES": "101",
                "CÓDIGO MICROSIGA": "200",
                "CÓDIGO CONDOMINIO": "301",
                "ABREVIAÇÃO": "POPB",
                "SMNPC": "POP_B",
                "NOME": "Site B",
                "Favorecido": "Fornecedor B",
                "Status": "Ativo"
            },
            {
                "CÓDIGO AQUILES": "100",
                "CÓDIGO MICROSIGA": "202",
                "CÓDIGO CONDOMINIO": "300",
                "ABREVIAÇÃO": "POPA",
                "SMNPC": "POP_A",
                "NOME": "Site A",
                "Favorecido": "Fornecedor A",
                "Status": "Cancelado"
            }
        ])

        duplicados = duplicated_site_codes(df)

        self.assertEqual(
            set(duplicados["Campo"]),
            {
                "Código Aquiles",
                "Código Microsiga",
                "Código Condomínio",
                "Abreviação",
                "SNMPc",
                "Nome",
                "Favorecido"
            }
        )
        self.assertIn(
            "POP_A",
            set(duplicados["SNMPc"])
        )

    def test_valida_codigos_unicos_ao_criar_site(self):
        df = pd.DataFrame([
            {
                "CÓDIGO AQUILES": "100",
                "CÓDIGO MICROSIGA": "200",
                "CÓDIGO CONDOMINIO": "300",
                "ABREVIAÇÃO": "POP_A",
                "SMNPC": "POP_A"
            }
        ])

        with self.assertRaisesRegex(ValueError, "Código Microsiga 200"):
            validate_unique_site_codes(
                df,
                {
                    "CÓDIGO AQUILES": "101",
                    "CÓDIGO MICROSIGA": "200",
                    "CÓDIGO CONDOMINIO": "301",
                    "ABREVIAÇÃO": "POP_B",
                    "SMNPC": "POP_B",
                    "NOME": "Site B",
                    "Favorecido": "Fornecedor B"
                },
                original_code=""
            )

        with self.assertRaisesRegex(ValueError, "SNMPc POP_A"):
            validate_unique_site_codes(
                df,
                {
                    "CÓDIGO AQUILES": "101",
                    "CÓDIGO MICROSIGA": "201",
                    "CÓDIGO CONDOMINIO": "301",
                    "ABREVIAÇÃO": "POP_B",
                    "SMNPC": "POP_A",
                    "NOME": "Site B",
                    "Favorecido": "Fornecedor B"
                },
                original_code=""
            )

    def test_valida_codigos_unicos_permite_editar_mesmo_site(self):
        df = pd.DataFrame([
            {
                "CÓDIGO AQUILES": "100",
                "CÓDIGO MICROSIGA": "200",
                "CÓDIGO CONDOMINIO": "300",
                "ABREVIAÇÃO": "POP_A",
                "SMNPC": "POP_A",
                "NOME": "Site A",
                "Favorecido": "Fornecedor A"
            }
        ])

        validate_unique_site_codes(
            df,
            {
                "CÓDIGO AQUILES": "100",
                "CÓDIGO MICROSIGA": "200",
                "CÓDIGO CONDOMINIO": "300",
                "ABREVIAÇÃO": "POP_A",
                "SMNPC": "POP_A",
                "NOME": "Site A",
                "Favorecido": "Fornecedor A"
            },
            original_code="100"
        )

    def test_opcoes_cadastradas_site_mantem_vazio_primeiro(self):
        df = pd.DataFrame({
            "Status": [
                "Ativo",
                "Cancelado"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "Status",
            "",
            extras=[
                "Ativo"
            ]
        )

        self.assertEqual(
            opcoes[0],
            ""
        )
        self.assertEqual(
            opcoes.count("Ativo"),
            1
        )

    def test_opcoes_cadastradas_site_inclui_extras_e_valor_atual(self):
        df = pd.DataFrame({
            "Relacionamento": [
                "Restrito",
                "Sem histórico"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "Relacionamento",
            "Valor novo",
            extras=[
                "Sem histórico"
            ]
        )

        self.assertIn(
            "Sem histórico",
            opcoes
        )
        self.assertIn(
            "Valor novo",
            opcoes
        )
        self.assertEqual(
            opcoes[0],
            ""
        )

    def test_opcoes_cadastradas_site_tipo_inclui_cliente(self):
        df = pd.DataFrame({
            "TIPO": [
                "POP",
                "BH"
            ]
        })

        opcoes = opcoes_cadastradas_site(
            df,
            "TIPO",
            "",
            extras=SITE_TYPE_OPTIONS
        )

        self.assertIn(
            "Cliente",
            opcoes
        )
        self.assertEqual(
            opcoes[0],
            ""
        )

    def test_normaliza_contatos_antigos_com_observacoes_vazias(self):
        df = pd.DataFrame({
            "CODIGO": [
                "123"
            ],
            "TIPO": [
                "Sindico"
            ],
            "NOME": [
                "Maria"
            ],
            "TELEFONE": [
                "11999990000"
            ],
            "EMAIL": [
                "maria@example.com"
            ]
        })

        normalizado = normalize_site_contacts(df)

        self.assertIn(
            "Observações",
            normalizado.columns
        )
        self.assertEqual(
            normalizado.loc[0, "Observações"],
            ""
        )

    def test_normaliza_contatos_aceita_alias_observacao(self):
        df = pd.DataFrame({
            "CODIGO": [
                "123"
            ],
            "TIPO": [
                "Zelador"
            ],
            "NOME": [
                "João"
            ],
            "OBS": [
                "Atende em horário comercial"
            ]
        })

        normalizado = normalize_site_contacts(df)

        self.assertEqual(
            normalizado.loc[0, "Observações"],
            "Atende em horário comercial"
        )

    def test_contatos_para_exibicao_remove_codigo(self):
        df = pd.DataFrame({
            "CÓDIGO AQUILES": [
                "123"
            ],
            "Tipo de contato": [
                "Portaria"
            ],
            "Nome": [
                "Portaria A"
            ],
            "Telefones": [
                "1111"
            ],
            "Emails": [
                "portaria@example.com"
            ],
            "Observações": [
                "24h"
            ]
        })

        exibicao = contatos_para_exibicao(df)

        self.assertNotIn(
            "CÓDIGO AQUILES",
            exibicao.columns
        )
        self.assertEqual(
            list(exibicao.columns),
            [
                "Tipo",
                "Nome",
                "Telefones",
                "E-mails",
                "Observações"
            ]
        )

    def test_opcoes_contatos_nao_expoem_indice(self):
        df = pd.DataFrame({
            "Tipo de contato": [
                "Sindico"
            ],
            "Nome": [
                "Maria"
            ],
            "Telefones": [
                "11999990000"
            ],
            "Emails": [
                ""
            ]
        }, index=[
            42
        ])

        opcoes, indices = opcoes_contatos_com_indices(df)

        self.assertEqual(
            opcoes,
            [
                "Sindico - Maria - 11999990000"
            ]
        )
        self.assertEqual(
            indices[opcoes[0]],
            42
        )

    def test_tipo_contato_desconhecido_abre_com_outro(self):
        self.assertEqual(
            indice_tipo_contato("Principal"),
            6
        )

    def test_tipo_contato_exibe_sindico_sem_acento_e_aceita_com_acento(self):
        self.assertIn(
            "Sindico",
            opcoes_tipo_contato()
        )
        self.assertEqual(
            normalizar_tipo_contato_exibicao("Síndico"),
            "Sindico"
        )
        self.assertEqual(
            indice_tipo_contato("Síndico"),
            0
        )

    def test_normaliza_contatos_antigos_com_arquivamento_vazio(self):
        df = pd.DataFrame({
            "CODIGO": [
                "123"
            ],
            "TIPO": [
                "Sindico"
            ],
            "NOME": [
                "Maria"
            ]
        })

        normalizado = normalize_site_contacts(df)

        self.assertEqual(
            normalizado.loc[0, "Arquivado"],
            ""
        )
        self.assertEqual(
            normalizado.loc[0, "Arquivado em"],
            ""
        )
        self.assertEqual(
            normalizado.loc[0, "Arquivado por"],
            ""
        )

    def test_normaliza_contatos_preserva_campos_de_arquivamento(self):
        df = pd.DataFrame({
            "CODIGO": [
                "123"
            ],
            "TIPO": [
                "Zelador"
            ],
            "NOME": [
                "João"
            ],
            "ARQUIVADO": [
                "Sim"
            ],
            "ARQUIVADO EM": [
                "2026-07-07 10:00:00"
            ],
            "ARQUIVADO POR": [
                "master"
            ]
        })

        normalizado = normalize_site_contacts(df)

        self.assertEqual(
            normalizado.loc[0, "Arquivado"],
            "Sim"
        )
        self.assertEqual(
            normalizado.loc[0, "Arquivado em"],
            "2026-07-07 10:00:00"
        )
        self.assertEqual(
            normalizado.loc[0, "Arquivado por"],
            "master"
        )

    def test_separa_contatos_ativos_e_arquivados(self):
        df = pd.DataFrame({
            "Tipo de contato": [
                "Sindico",
                "Zelador"
            ],
            "Nome": [
                "Maria",
                "João"
            ],
            "Arquivado": [
                "",
                "Sim"
            ]
        })

        self.assertEqual(
            contatos_ativos(df)["Nome"].tolist(),
            [
                "Maria"
            ]
        )
        self.assertEqual(
            contatos_arquivados(df)["Nome"].tolist(),
            [
                "João"
            ]
        )

    def test_contatos_arquivados_para_exibicao_mostra_metadados(self):
        df = pd.DataFrame({
            "Tipo de contato": [
                "Zelador"
            ],
            "Nome": [
                "João"
            ],
            "Telefones": [
                "1111"
            ],
            "Emails": [
                ""
            ],
            "Observações": [
                "Antigo"
            ],
            "Arquivado em": [
                "2026-07-07 10:00:00"
            ],
            "Arquivado por": [
                "master"
            ]
        })

        exibicao = contatos_para_exibicao(
            df,
            incluir_arquivamento=True
        )

        self.assertEqual(
            list(exibicao.columns),
            [
                "Tipo",
                "Nome",
                "Telefones",
                "E-mails",
                "Observações",
                "Arquivado em",
                "Arquivado por"
            ]
        )


if __name__ == "__main__":
    unittest.main()
