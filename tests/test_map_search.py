import unittest

try:
    import pandas as pd

    from app.ui.views.map import aplicar_busca_mapa
    from app.ui.views.map import camadas_marcadores_geometricos
    from app.ui.views.map import centro_zoom_mapa
    from app.ui.views.map import deve_atualizar_cache_mapa_geral
    from app.ui.views.map import marcador_endereco_temporario
    from app.ui.views.map import ocultar_valores_clientes_mapa
    from app.ui.views.map import pontos_centro_mapa
    from app.ui.views.map import preparar_marcadores_busca
    from app.ui.views.map import preparar_marcadores_clientes
    from app.ui.views.map import preparar_marcadores_sites
    from app.ui.views.map import sanitizar_tooltip_receita
except ModuleNotFoundError:
    pd = None
    aplicar_busca_mapa = None
    camadas_marcadores_geometricos = None
    centro_zoom_mapa = None
    deve_atualizar_cache_mapa_geral = None
    marcador_endereco_temporario = None
    ocultar_valores_clientes_mapa = None
    pontos_centro_mapa = None
    preparar_marcadores_busca = None
    preparar_marcadores_clientes = None
    preparar_marcadores_sites = None
    sanitizar_tooltip_receita = None


@unittest.skipIf(pd is None, "pandas nao instalado")
class MapSearchTest(unittest.TestCase):

    def setUp(self):
        self.df_sites = pd.DataFrame([
            {
                "Site": "SITE_A",
                "Endereco": "Rua Alfa",
                "Cidade": "Belo Horizonte",
                "UF": "MG",
                "CEP": "30100000",
                "Setorial": "Direto",
                "Latitude": -19.9,
                "Longitude": -43.9
            },
            {
                "Site": "SITE_B",
                "Endereco": "Rua Beta",
                "Cidade": "Contagem",
                "UF": "MG",
                "CEP": "32000000",
                "Setorial": "Norte",
                "Latitude": -19.8,
                "Longitude": -44.0
            }
        ])
        self.df_clientes = pd.DataFrame([
            {
                "Cliente": "Cliente Alfa",
                "Assinatura": "123",
                "Produto": "NeoSoft",
                "Endereco": "Av Cliente",
                "Cidade": "Belo Horizonte",
                "Site": "SITE_A",
                "Setorial": "Direto",
                "Equipamento": "ONU 1",
                "Latitude": -19.91,
                "Longitude": -43.91
            }
        ])
        self.df_links_clientes = pd.DataFrame([
            {
                "Site": "SITE_A",
                "Cliente": "Cliente Alfa",
                "Assinatura": "123",
                "Setorial": "Direto",
                "Produto": "NeoSoft"
            }
        ])
        self.df_links_sites = pd.DataFrame([
            {
                "Site Pai": "SITE_A",
                "Site Filho": "SITE_B",
                "Setorial": "Norte"
            }
        ])
        self.df_nao_plotados = pd.DataFrame([
            {
                "Site": "SITE_C",
                "Cliente": "",
                "Assinatura": "",
                "Endereco": "Rua Gama",
                "Motivo": "Sem coordenadas válidas",
                "Vínculo": ""
            }
        ])

    def test_cache_mapa_geral_exige_todos_os_sites_clientes_e_filhos(self):
        self.assertTrue(
            deve_atualizar_cache_mapa_geral(
                ["SITE_A", "SITE_B"],
                {
                    "SITE_A": object(),
                    "SITE_B": object()
                },
                True,
                True,
                10,
                {
                    "clientes_total": 10
                }
            )
        )

    def test_cache_mapa_geral_bloqueia_mapa_parcial(self):
        self.assertFalse(
            deve_atualizar_cache_mapa_geral(
                ["SITE_A"],
                {
                    "SITE_A": object(),
                    "SITE_B": object()
                },
                True,
                True,
                10,
                {
                    "clientes_total": 10
                }
            )
        )

    def test_cache_mapa_geral_bloqueia_limite_menor_que_clientes(self):
        self.assertFalse(
            deve_atualizar_cache_mapa_geral(
                ["SITE_A", "SITE_B"],
                {
                    "SITE_A": object(),
                    "SITE_B": object()
                },
                True,
                True,
                5,
                {
                    "clientes_total": 10
                }
            )
        )

    def test_busca_encontra_site_por_endereco(self):
        resultado = aplicar_busca_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            "Rua Alfa"
        )

        self.assertEqual(len(resultado["sites"]), len(self.df_sites))
        self.assertEqual(
            list(resultado["sites_resultado"]["Site"]),
            ["SITE_A"]
        )
        self.assertTrue(resultado["clientes_resultado"].empty)

    def test_sanitiza_tooltip_de_receita_sem_permissao(self):
        tooltip = (
            "<b>Cliente Alfa</b><br/>"
            "Produto: NeoSoft<br/>"
            "Receita: R$ 100,00<br/>"
            "Distância: 1.00 km"
        )

        self.assertEqual(
            sanitizar_tooltip_receita(tooltip),
            (
                "<b>Cliente Alfa</b><br/>"
                "Produto: NeoSoft<br/>"
                "Receita: Restrito<br/>"
                "Distância: 1.00 km"
            )
        )

    def test_oculta_receita_e_tooltip_no_mapa_sem_permissao(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente Alfa",
                "Receita": 100,
                "Mensalidade": 100,
                "Tooltip": (
                    "<b>Cliente Alfa</b><br/>"
                    "Receita: R$ 100,00"
                )
            }
        ])

        resultado = ocultar_valores_clientes_mapa(
            df,
            pode_ver_valores=False
        )

        self.assertEqual(
            resultado.loc[0, "Receita"],
            "Restrito"
        )
        self.assertEqual(
            resultado.loc[0, "Mensalidade"],
            "Restrito"
        )
        self.assertIn(
            "Receita: Restrito",
            resultado.loc[0, "Tooltip"]
        )

    def test_mantem_receita_e_tooltip_no_mapa_com_permissao(self):
        df = pd.DataFrame([
            {
                "Cliente": "Cliente Alfa",
                "Receita": 100,
                "Tooltip": "Receita: R$ 100,00"
            }
        ])

        resultado = ocultar_valores_clientes_mapa(
            df,
            pode_ver_valores=True
        )

        self.assertEqual(
            resultado.loc[0, "Receita"],
            100
        )
        self.assertEqual(
            resultado.loc[0, "Tooltip"],
            "Receita: R$ 100,00"
        )

    def test_busca_continua_funcionando_com_receita_restrita(self):
        clientes = ocultar_valores_clientes_mapa(
            self.df_clientes.assign(
                Receita=[100],
                Tooltip=["Receita: R$ 100,00"]
            ),
            pode_ver_valores=False
        )

        resultado = aplicar_busca_mapa(
            self.df_sites,
            clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            "Cliente Alfa"
        )

        self.assertEqual(
            list(resultado["clientes_resultado"]["Cliente"]),
            ["Cliente Alfa"]
        )
        self.assertEqual(
            resultado["clientes_resultado"].iloc[0]["Receita"],
            "Restrito"
        )

    def test_busca_encontra_cliente_por_assinatura_produto_e_equipamento(self):
        for termo in ["123", "NeoSoft", "ONU 1"]:
            resultado = aplicar_busca_mapa(
                self.df_sites,
                self.df_clientes,
                self.df_links_clientes,
                self.df_links_sites,
                self.df_nao_plotados,
                termo
            )

            self.assertEqual(
                list(resultado["clientes_resultado"]["Cliente"]),
                ["Cliente Alfa"]
            )
            self.assertEqual(
                list(resultado["sites_resultado"]["Site"]),
                ["SITE_A"]
            )
            self.assertEqual(len(resultado["sites"]), len(self.df_sites))

    def test_busca_filtra_vinculos_compativeis_com_pontos_visiveis(self):
        resultado = aplicar_busca_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            "Cliente Alfa"
        )

        self.assertEqual(
            len(resultado["links_clientes_resultado"]),
            1
        )
        self.assertTrue(
            resultado["links_sites_resultado"].empty
        )

    def test_busca_filtra_itens_nao_plotados_por_motivo(self):
        resultado = aplicar_busca_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            "Sem coordenadas"
        )

        self.assertEqual(
            len(resultado["nao_plotados"]),
            1
        )
        self.assertEqual(
            resultado["resultados_nao_plotados"],
            1
        )

    def test_marcador_temporario_usa_ponto_geocodificado(self):
        marcador = marcador_endereco_temporario(
            "Rua Externa",
            {
                "lat": -20,
                "lon": -44
            }
        )

        self.assertEqual(
            marcador.loc[0, "Endereco"],
            "Rua Externa"
        )
        self.assertEqual(
            marcador.loc[0, "Latitude"],
            -20
        )
        self.assertEqual(
            marcador.loc[0, "Longitude"],
            -44
        )

    def test_busca_sem_resultado_mantem_mapa_original(self):
        resultado = aplicar_busca_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            "Nada disso existe"
        )

        self.assertTrue(resultado["sem_resultado"])
        self.assertEqual(
            len(resultado["sites"]),
            len(self.df_sites)
        )
        self.assertEqual(
            len(resultado["clientes"]),
            len(self.df_clientes)
        )

    def test_centro_usa_marcador_temporario(self):
        marcador = marcador_endereco_temporario(
            "Rua Externa",
            {
                "lat": -20,
                "lon": -44
            }
        )

        latitudes, longitudes = pontos_centro_mapa(
            pd.DataFrame(),
            pd.DataFrame(),
            marcador
        )

        self.assertEqual(latitudes, [-20])
        self.assertEqual(longitudes, [-44])

    def test_centro_zoom_usa_zoom_proximo_para_item_plotado(self):
        latitudes, longitudes, zoom = centro_zoom_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_sites.iloc[[0]],
            pd.DataFrame(),
            pd.DataFrame(),
            True
        )

        self.assertEqual(latitudes, [-19.9])
        self.assertEqual(longitudes, [-43.9])
        self.assertEqual(zoom, 14)

    def test_centro_zoom_usa_zoom_mais_proximo_para_endereco(self):
        marcador = marcador_endereco_temporario(
            "Rua Externa",
            {
                "lat": -20,
                "lon": -44
            }
        )

        latitudes, longitudes, zoom = centro_zoom_mapa(
            self.df_sites,
            self.df_clientes,
            pd.DataFrame(),
            pd.DataFrame(),
            marcador,
            True
        )

        self.assertEqual(latitudes, [-20])
        self.assertEqual(longitudes, [-44])
        self.assertEqual(zoom, 16)

    def test_centro_zoom_sem_busca_mantem_padrao(self):
        _latitudes, _longitudes, zoom = centro_zoom_mapa(
            self.df_sites,
            self.df_clientes,
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            False
        )

        self.assertEqual(zoom, 9)

    def test_marcador_site_preserva_coordenada_e_tooltip(self):
        df_sites = self.df_sites.copy()
        df_sites["Tooltip"] = "Site tooltip"
        df_sites["Cor"] = [[30, 80, 120, 230] for _indice in range(len(df_sites))]

        marcadores = preparar_marcadores_sites(
            df_sites,
            zoom_mapa=13
        )

        self.assertEqual(
            marcadores.loc[0, "Latitude"],
            self.df_sites.loc[0, "Latitude"]
        )
        self.assertEqual(
            marcadores.loc[0, "Tooltip"],
            "Site tooltip"
        )
        self.assertIn("Raio Marcador", marcadores.columns)
        self.assertIn("CorMarcador", marcadores.columns)
        self.assertIn("RaioMarcador", marcadores.columns)
        self.assertIn("Cor Borda", marcadores.columns)
        self.assertEqual(
            marcadores.loc[0, "Cor Marcador"],
            [30, 80, 120, 191]
        )
        self.assertEqual(
            marcadores.loc[0, "CorMarcador"],
            [30, 80, 120, 191]
        )
        self.assertEqual(marcadores.loc[0, "Raio Marcador"], 22.5)
        self.assertEqual(marcadores.loc[0, "RaioMarcador"], 22.5)
        self.assertEqual(marcadores.loc[0, "Raio Min Pixels"], 10)
        self.assertEqual(marcadores.loc[0, "RaioMinPixels"], 10)
        self.assertEqual(marcadores.loc[0, "Raio Max Pixels"], 23)
        self.assertEqual(marcadores.loc[0, "RaioMaxPixels"], 23)
        self.assertEqual(marcadores.loc[0, "Largura Borda"], 1)
        self.assertEqual(marcadores.loc[0, "LarguraBorda"], 1)
        self.assertNotIn("Raio Halo", marcadores.columns)
        self.assertNotIn("Cor Centro", marcadores.columns)

    def test_camadas_marcadores_usam_colunas_tecnicas_sem_espaco(self):
        marcadores = preparar_marcadores_sites(
            self.df_sites,
            zoom_mapa=13
        )

        camada = camadas_marcadores_geometricos(marcadores)[0]
        configuracao = camada.to_json()

        self.assertIn('"getFillColor": "@@=CorMarcador"', configuracao)
        self.assertIn('"getLineColor": "@@=CorBorda"', configuracao)
        self.assertIn('"getRadius": "@@=RaioMarcador"', configuracao)
        self.assertIn('"getLineWidth": "@@=LarguraBorda"', configuracao)

    def test_marcador_define_limites_visuais_em_pixels(self):
        marcadores = preparar_marcadores_sites(
            self.df_sites,
            zoom_mapa=8
        )

        self.assertEqual(
            marcadores.loc[0, "Raio Marcador"],
            22.5
        )
        self.assertEqual(
            marcadores.loc[0, "Raio Min Pixels"],
            10
        )
        self.assertEqual(
            marcadores.loc[0, "Raio Max Pixels"],
            23
        )

    def test_marcador_cliente_e_menor_que_site(self):
        df_sites = self.df_sites.copy()
        df_clientes = self.df_clientes.copy()

        marcadores_sites = preparar_marcadores_sites(
            df_sites,
            zoom_mapa=13
        )
        marcadores_clientes = preparar_marcadores_clientes(
            df_clientes,
            zoom_mapa=13
        )

        self.assertLess(
            marcadores_clientes.loc[0, "Raio Marcador"],
            marcadores_sites.loc[0, "Raio Marcador"]
        )
        self.assertEqual(marcadores_clientes.loc[0, "Raio Marcador"], 12.5)
        self.assertEqual(marcadores_clientes.loc[0, "RaioMarcador"], 12.5)
        self.assertEqual(marcadores_clientes.loc[0, "Raio Min Pixels"], 7)
        self.assertEqual(marcadores_clientes.loc[0, "RaioMinPixels"], 7)
        self.assertEqual(marcadores_clientes.loc[0, "Raio Max Pixels"], 17)
        self.assertEqual(marcadores_clientes.loc[0, "RaioMaxPixels"], 17)
        self.assertEqual(
            marcadores_clientes.loc[0, "Cor Marcador"],
            [130, 130, 130, 191]
        )
        self.assertEqual(
            marcadores_clientes.loc[0, "Cor Marcador"][3],
            191
        )

    def test_marcador_busca_e_destacado(self):
        marcador = marcador_endereco_temporario(
            "Rua Externa",
            {
                "lat": -20,
                "lon": -44
            }
        )

        visual = preparar_marcadores_busca(
            marcador,
            zoom_mapa=13
        )

        self.assertEqual(
            visual.loc[0, "Cor Marcador"],
            [245, 180, 40, 191]
        )
        self.assertEqual(visual.loc[0, "Raio Marcador"], 30)
        self.assertEqual(visual.loc[0, "RaioMarcador"], 30)
        self.assertEqual(visual.loc[0, "Raio Min Pixels"], 12)
        self.assertEqual(visual.loc[0, "RaioMinPixels"], 12)
        self.assertEqual(visual.loc[0, "Raio Max Pixels"], 28)
        self.assertEqual(visual.loc[0, "RaioMaxPixels"], 28)
        self.assertNotIn("Raio Halo", visual.columns)

    def test_helpers_marcadores_retornam_vazio(self):
        vazio = pd.DataFrame()

        self.assertTrue(preparar_marcadores_sites(vazio).empty)
        self.assertTrue(preparar_marcadores_clientes(vazio).empty)
        self.assertTrue(preparar_marcadores_busca(vazio).empty)


if __name__ == "__main__":
    unittest.main()
