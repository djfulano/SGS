import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

try:
    from app.models.cliente import Cliente
    from app.models.site import Site
    from app.services.map_settings import load_map_config
    from app.services.map_service import chave_cache_mapa
    from app.services.map_service import compilar_dados_mapa
    from app.services.map_service import cor_linha_cliente_por_site
    from app.services.map_service import cor_ponto_site
    from app.services.map_service import cor_setorial
    from app.services.map_service import dataframes_mapa
    from app.services.map_service import diagnostico_site_nao_plotado
    from app.services.map_service import distancia_km
    from app.services.map_service import geocodificar_endereco_maptiler
    from app.services.map_service import geocodificar_clientes_mapa_com_diagnostico
    from app.services.map_service import maptiler_satellite_style_url
    from app.services.map_service import ponto_site_mapa
    from app.services.map_service import provedor_mapa_satelite
except ModuleNotFoundError:
    load_map_config = None
    chave_cache_mapa = None
    compilar_dados_mapa = None
    cor_linha_cliente_por_site = None
    cor_ponto_site = None
    cor_setorial = None
    dataframes_mapa = None
    diagnostico_site_nao_plotado = None
    distancia_km = None
    geocodificar_endereco_maptiler = None
    geocodificar_clientes_mapa_com_diagnostico = None
    maptiler_satellite_style_url = None
    ponto_site_mapa = None
    provedor_mapa_satelite = None


class SiteMapaFake:

    def __init__(
        self,
        nome="SITE_A",
        endereco="Rua A",
        numero="10",
        bairro="Centro",
        cidade="Sao Paulo",
        uf="SP",
        cep="01001000",
        latitude=0,
        longitude=0,
        pai=None,
        clientes=None
    ):
        self.nome = nome
        self.tipo = "BH"
        self.status_cadastro = "Ativo"
        self.endereco = endereco
        self.numero = numero
        self.bairro = bairro
        self.cidade = cidade
        self.uf = uf
        self.cep = cep
        self.latitude = latitude
        self.longitude = longitude
        self.pai = pai
        self.clientes = clientes or []


class ClienteMapaFake:

    def __init__(
        self,
        nome="Cliente A",
        assinatura="123",
        endereco="Rua A, 10",
        bairro="Centro",
        cidade="Sao Paulo",
        cep="01001000",
        setorial="Direto"
    ):
        self.nome = nome
        self.num_assinatura = assinatura
        self.endereco_completo = endereco
        self.bairro = bairro
        self.cidade = cidade
        self.cep = cep
        self.setorial = setorial


@unittest.skipIf(chave_cache_mapa is None, "pandas nao instalado")
class MapServiceTest(unittest.TestCase):

    def test_mapa_gera_um_marcador_e_multiplas_linhas_por_assinatura(self):
        principal = Site("BEL_POP_1_IP", "POP")
        adicional = Site("FUV_POP_2_IP", "POP")
        principal.latitude = -23.0
        principal.longitude = -46.0
        adicional.latitude = -23.01
        adicional.longitude = -46.01
        cliente = Cliente("DAVO ITAQUERA", 900, "10986201")
        cliente.endereco_completo = "Rua A, 10"
        cliente.cidade = "Sao Paulo"
        principal.adicionar_cliente(cliente, setorial="BEL_S10")
        adicional.adicionar_cliente_adicional(cliente, setorial="FUV_S6")

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 30,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ), patch(
            "app.services.map_service.geocodificar_endereco",
            return_value={"lat": -23.005, "lon": -46.005, "provider": "teste"}
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {principal.nome: principal},
                {principal.nome: principal, adicional.nome: adicional},
                incluir_clientes=True,
                limite_clientes=100
            )

        self.assertEqual(len(pacote["clientes"]), 1)
        self.assertEqual(len(pacote["links_clientes"]), 2)
        self.assertEqual(
            {item["Vínculo"] for item in pacote["links_clientes"]},
            {"Principal", "Adicional"}
        )

    def test_cor_setorial_usa_paleta_fixa_por_tipo(self):
        self.assertEqual(
            cor_setorial("SITE_POP_1_IP", "Direto"),
            [20, 150, 70, 220]
        )
        self.assertEqual(
            cor_setorial("SITE_POP_1_IP", "SETOR_BH_1"),
            [245, 130, 35, 220]
        )
        self.assertEqual(
            cor_setorial("SITE_POP_1_IP", "SETOR_REP_1"),
            [245, 210, 45, 220]
        )

    def test_cor_linha_cliente_usa_cor_do_site_com_alpha_de_linha(self):
        self.assertEqual(
            cor_linha_cliente_por_site([245, 130, 35, 220]),
            [245, 130, 35, 125]
        )

    def test_cor_ponto_site_prioriza_tipo_no_nome_do_site(self):
        self.assertEqual(
            cor_ponto_site("ABC_BH_1_IP", "ABC_POP_1_IP", "Direto"),
            [245, 130, 35, 220]
        )

    def test_chave_cache_mapa_muda_quando_endereco_muda(self):
        site_antigo = SiteMapaFake(endereco="Rua Antiga")
        site_novo = SiteMapaFake(endereco="Rua Nova")

        chave_antiga = chave_cache_mapa(
            {"SITE_A": site_antigo},
            incluir_clientes=False,
            limite_clientes=100
        )
        chave_nova = chave_cache_mapa(
            {"SITE_A": site_novo},
            incluir_clientes=False,
            limite_clientes=100
        )

        self.assertNotEqual(
            chave_antiga,
            chave_nova
        )

    def test_chave_cache_mapa_muda_quando_limite_distancia_muda(self):
        site = SiteMapaFake()

        chave_antiga = chave_cache_mapa(
            {"SITE_A": site},
            incluir_clientes=True,
            limite_clientes=100,
            limite_site_site_km=30,
            limite_site_cliente_km=30
        )
        chave_nova = chave_cache_mapa(
            {"SITE_A": site},
            incluir_clientes=True,
            limite_clientes=100,
            limite_site_site_km=50,
            limite_site_cliente_km=30
        )

        self.assertNotEqual(
            chave_antiga,
            chave_nova
        )

    def test_chave_cache_mapa_muda_quando_enlaces_mudam(self):
        site = SiteMapaFake()

        chave_sem_enlace = chave_cache_mapa(
            {"SITE_A": site},
            incluir_clientes=False,
            limite_clientes=100,
            enlaces_sites=[]
        )
        chave_com_enlace = chave_cache_mapa(
            {"SITE_A": site},
            incluir_clientes=False,
            limite_clientes=100,
            enlaces_sites=[
                {
                    "ID Link": "1",
                    "Site Origem": "SITE_A",
                    "Site Destino": "SITE_B",
                    "Tipo Enlace": "POP x POP"
                }
            ]
        )

        self.assertNotEqual(
            chave_sem_enlace,
            chave_com_enlace
        )

    def test_distancia_km_calcula_aproximadamente(self):

        distancia = distancia_km(
            -23.0,
            -46.0,
            -23.0,
            -45.0
        )

        self.assertGreater(
            distancia,
            100
        )
        self.assertLess(
            distancia,
            110
        )

    def test_ponto_site_mapa_forca_geocoding_do_endereco(self):
        site = SiteMapaFake(
            latitude=-23.0,
            longitude=-46.0
        )
        cache = {}

        with patch(
            "app.services.map_service.geocodificar_endereco",
            return_value={
                "lat": -22.0,
                "lon": -45.0
            }
        ) as geocodificar:
            ponto = ponto_site_mapa(
                site,
                cache,
                atualizar_geocoding=True
            )

        geocodificar.assert_called_once()
        self.assertEqual(
            ponto["Latitude"],
            -22.0
        )
        self.assertEqual(
            ponto["Longitude"],
            -45.0
        )
        self.assertEqual(
            ponto["Fonte Coordenada"],
            "Endereco"
        )

    def test_dataframes_mapa_retorna_itens_nao_plotados(self):
        pacote = {
            "sites": [],
            "clientes": [],
            "links_clientes": [],
            "links_sites": [],
            "nao_plotados": [
                {
                    "Tipo Item": "Site",
                    "Site": "SITE_A",
                    "Motivo": "Sem coordenadas"
                }
            ]
        }

        _sites, _clientes, _links_clientes, _links_sites, nao_plotados = dataframes_mapa(
            pacote
        )

        self.assertEqual(
            nao_plotados.iloc[0]["Site"],
            "SITE_A"
        )

    def test_diagnostico_site_sem_coordenada_e_sem_endereco(self):
        site = SiteMapaFake(
            endereco="",
            numero="",
            bairro="",
            cidade="",
            uf="",
            cep="",
            latitude=0,
            longitude=0
        )

        diagnostico = diagnostico_site_nao_plotado(
            site,
            {}
        )

        self.assertEqual(
            diagnostico["Motivo"],
            "Sem coordenadas válidas e sem endereço para geocodificar"
        )

    def test_recompilar_clientes_remove_cache_negativo(self):
        import pandas as pd

        df_clientes = pd.DataFrame([
            {
                "Cliente": "Cliente A",
                "Assinatura": "123",
                "Site": "SITE_A",
                "Endereco": "Rua A, 10, Sao Paulo, Brasil"
            }
        ])
        cache = {
            "RUA A, 10, SAO PAULO, BRASIL": None
        }

        with patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value=cache
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ), patch(
            "app.services.map_service.geocodificar_endereco",
            return_value={
                "lat": -23.0,
                "lon": -46.0
            }
        ) as geocodificar:
            df_plotados, nao_plotados = geocodificar_clientes_mapa_com_diagnostico(
                df_clientes,
                atualizar_geocoding=True
            )

        geocodificar.assert_called_once()
        self.assertEqual(len(df_plotados), 1)
        self.assertEqual(nao_plotados, [])

    def test_chave_geocoding_inclui_provedor(self):
        from app.services.map_service import chave_geocoding

        self.assertEqual(
            chave_geocoding(
                "Rua A, 10",
                "maptiler"
            ),
            "MAPTILER::RUA A, 10"
        )

    def test_geocodificar_endereco_maptiler_retorna_primeiro_ponto(self):

        class RespostaFake:

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "features": [
                        {
                            "geometry": {
                                "coordinates": [
                                    -46.0,
                                    -23.0
                                ]
                            }
                        }
                    ]
                }

        with patch(
            "app.services.map_service.maptiler_api_key",
            return_value="token"
        ), patch(
            "app.services.map_service.requests.get",
            return_value=RespostaFake()
        ) as requisicao:
            ponto = geocodificar_endereco_maptiler(
                "Rua A, 10, Brasil"
            )

        requisicao.assert_called_once()
        self.assertEqual(
            ponto,
            {
                "lat": -23.0,
                "lon": -46.0,
                "provider": "maptiler"
            }
        )

    def test_compilar_mapa_nao_plota_site_filho_acima_de_30_km(self):

        pai = SiteMapaFake(
            nome="PAI",
            latitude=-23.0,
            longitude=-46.0
        )
        filho = SiteMapaFake(
            nome="FILHO",
            pai=pai,
            latitude=-23.0,
            longitude=-45.0
        )

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 30,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {"PAI": pai},
                {
                    "PAI": pai,
                    "FILHO": filho
                },
                incluir_clientes=False,
                limite_clientes=100
            )

        sites_plotados = {
            item["Site"]
            for item in pacote["sites"]
        }
        motivos = [
            item["Motivo"]
            for item in pacote["nao_plotados"]
        ]

        self.assertIn(
            "PAI",
            sites_plotados
        )
        self.assertNotIn(
            "FILHO",
            sites_plotados
        )
        self.assertTrue(
            any("mais de 30 km" in motivo for motivo in motivos)
        )

    def test_compilar_mapa_plota_enlace_snmpc_pop_pop_em_azul(self):
        fuv = SiteMapaFake(
            nome="FUV_POP_108506_IP",
            latitude=-23.0,
            longitude=-46.0
        )
        san = SiteMapaFake(
            nome="SAN_POP_105452_IP",
            latitude=-23.1,
            longitude=-46.1
        )
        fuv.tipo = "POP"
        san.tipo = "POP"

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 30,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {"FUV_POP_108506_IP": fuv},
                {
                    "FUV_POP_108506_IP": fuv,
                    "SAN_POP_105452_IP": san
                },
                incluir_clientes=False,
                limite_clientes=100,
                enlaces_sites=[
                    {
                        "Tipo Enlace": "POP x POP",
                        "Nome Link": "FUV x SAN",
                        "Site Origem": "FUV_POP_108506_IP",
                        "Site Destino": "SAN_POP_105452_IP",
                        "ID Link": "100"
                    }
                ]
            )

        enlaces_snmpc = [
            link
            for link in pacote["links_sites"]
            if str(link.get("Tipo Vínculo", "")).startswith("Enlace SNMPc")
        ]

        self.assertEqual(len(enlaces_snmpc), 1)
        self.assertEqual(enlaces_snmpc[0]["Cor"], [35, 110, 255, 180])
        self.assertIsNone(san.pai)

    def test_compilar_mapa_enlace_snmpc_sem_coordenada_vai_para_nao_plotados(self):
        fuv = SiteMapaFake(
            nome="FUV_POP_108506_IP",
            latitude=-23.0,
            longitude=-46.0
        )
        aus = SiteMapaFake(
            nome="AUS_POP_92309_IP",
            latitude=0,
            longitude=0
        )

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 30,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ), patch(
            "app.services.map_service.geocodificar_endereco",
            return_value=None
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {"FUV_POP_108506_IP": fuv},
                {
                    "FUV_POP_108506_IP": fuv,
                    "AUS_POP_92309_IP": aus
                },
                incluir_clientes=False,
                limite_clientes=100,
                enlaces_sites=[
                    {
                        "Tipo Enlace": "POP x POP",
                        "Nome Link": "FUV x AUS",
                        "Site Origem": "FUV_POP_108506_IP",
                        "Site Destino": "AUS_POP_92309_IP",
                        "ID Link": "101"
                    }
                ]
            )

        self.assertTrue(
            any(
                item.get("Tipo Item") == "Enlace SNMPc"
                for item in pacote["nao_plotados"]
            )
        )

    def test_compilar_mapa_nao_plota_cliente_acima_de_30_km(self):

        cliente = ClienteMapaFake()
        site = SiteMapaFake(
            nome="SITE_A",
            latitude=-23.0,
            longitude=-46.0,
            clientes=[
                cliente
            ]
        )

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 30,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ), patch(
            "app.services.map_service.geocodificar_endereco",
            return_value={
                "lat": -23.0,
                "lon": -45.0,
                "provider": "maptiler"
            }
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {"SITE_A": site},
                {
                    "SITE_A": site
                },
                incluir_clientes=True,
                limite_clientes=100
            )

        self.assertEqual(
            pacote["clientes"],
            []
        )
        self.assertTrue(
            any(
                item["Tipo Item"] == "Cliente"
                and "mais de 30 km" in item["Motivo"]
                for item in pacote["nao_plotados"]
            )
        )

    def test_limites_site_e_cliente_sao_aplicados_separadamente(self):
        cliente = ClienteMapaFake()
        pai = SiteMapaFake(
            nome="PAI",
            latitude=-23.0,
            longitude=-46.0
        )
        filho = SiteMapaFake(
            nome="FILHO",
            pai=pai,
            latitude=-23.0,
            longitude=-45.0,
            clientes=[
                cliente
            ]
        )

        with patch(
            "app.services.map_service.carregar_cache_mapa",
            return_value={}
        ), patch(
            "app.services.map_service.limites_mapa",
            return_value={
                "site_site": 150,
                "site_cliente": 30,
                "limite_clientes_padrao": 100
            }
        ), patch(
            "app.services.map_service.salvar_cache_mapa"
        ), patch(
            "app.services.map_service.carregar_cache_geocoding",
            return_value={}
        ), patch(
            "app.services.map_service.salvar_cache_geocoding"
        ), patch(
            "app.services.map_service.geocodificar_endereco",
            return_value={
                "lat": -23.0,
                "lon": -44.0,
                "provider": "maptiler"
            }
        ):
            pacote, _cacheado = compilar_dados_mapa(
                {"PAI": pai},
                {
                    "PAI": pai,
                    "FILHO": filho
                },
                incluir_clientes=True,
                limite_clientes=100
            )

        self.assertIn(
            "FILHO",
            {
                item["Site"]
                for item in pacote["sites"]
            }
        )
        self.assertTrue(
            any(
                item["Tipo Item"] == "Cliente"
                and item["Limite Km"] == 30
                for item in pacote["nao_plotados"]
            )
        )

    def test_load_map_config_retorna_defaults_para_configuracao_antiga(self):
        with TemporaryDirectory() as pasta:
            config_teste = Path(pasta) / "map_config.json"
            config_teste.write_text(
                '{"satellite_provider": "maptiler"}',
                encoding="utf-8"
            )

            with patch(
                "app.services.map_settings.MAP_CONFIG_FILE",
                config_teste
            ):
                config = load_map_config()

        self.assertEqual(
            config["max_site_site_distance_km"],
            30.0
        )
        self.assertEqual(
            config["max_site_client_distance_km"],
            30.0
        )
        self.assertEqual(
            config["default_client_limit"],
            100
        )

    def test_maptiler_satellite_style_url_usa_chave_configurada(self):

        with TemporaryDirectory() as pasta:
            config_teste = Path(pasta) / "map_config.json"

            with patch(
                "app.services.map_settings.MAP_CONFIG_FILE",
                config_teste
            ), patch.dict(
                "os.environ",
                {
                    "MAPTILER_API_KEY": "token teste",
                    "MAPTILER_SATELLITE_STYLE_ID": "hybrid"
                },
                clear=False
            ):
                url = maptiler_satellite_style_url()

        self.assertEqual(
            url,
            "https://api.maptiler.com/maps/hybrid/style.json?key=token+teste"
        )

    def test_provedor_mapa_satelite_padrao_e_maptiler(self):

        with TemporaryDirectory() as pasta:
            config_teste = Path(pasta) / "map_config.json"

            with patch(
                "app.services.map_settings.MAP_CONFIG_FILE",
                config_teste
            ), patch.dict(
                "os.environ",
                {
                    "MAP_SATELLITE_PROVIDER": ""
                },
                clear=False
            ):
                provedor = provedor_mapa_satelite()

        self.assertEqual(
            provedor,
            "maptiler"
        )


if __name__ == "__main__":
    unittest.main()
