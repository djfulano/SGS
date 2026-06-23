import unittest
from zipfile import ZipFile
from io import BytesIO

try:
    import pandas as pd

    from app.services.map_export import cor_kml
    from app.services.map_export import montar_kml_mapa
    from app.services.map_export import montar_kmz_mapa
except ModuleNotFoundError:
    pd = None
    cor_kml = None
    montar_kml_mapa = None
    montar_kmz_mapa = None


@unittest.skipIf(pd is None, "pandas nao instalado")
class MapExportTest(unittest.TestCase):

    def setUp(self):
        self.df_sites = pd.DataFrame([
            {
                "Site": "SITE & A",
                "Latitude": -19.9,
                "Longitude": -43.9,
                "Endereco": "Rua Alfa",
                "Cidade": "Belo Horizonte",
                "Cor": [20, 150, 70, 220],
                "Setorial": "POP"
            }
        ])
        self.df_clientes = pd.DataFrame([
            {
                "Cliente": "Cliente Alfa",
                "Latitude": -19.91,
                "Longitude": -43.91,
                "Produto": "NeoSoft",
                "Receita": "Restrito",
                "Equipamento": "ONU 1",
                "Distância Site Km": 1.2
            }
        ])
        self.df_links_clientes = pd.DataFrame([
            {
                "Site": "SITE & A",
                "Cliente": "Cliente Alfa",
                "Origem": [-43.9, -19.9],
                "Destino": [-43.91, -19.91],
                "Distância Km": 1.2,
                "Cor": [20, 150, 70, 125]
            }
        ])
        self.df_links_sites = pd.DataFrame([
            {
                "Site Pai": "SITE & A",
                "Site Filho": "SITE B",
                "Origem": [-43.9, -19.9],
                "Destino": [-44.0, -19.8],
                "Distância Km": 10.5,
                "Cor": [210, 30, 30, 145]
            }
        ])
        self.df_nao_plotados = pd.DataFrame([
            {
                "Tipo Item": "Cliente",
                "Cliente": "Cliente sem coordenada",
                "Motivo": "Sem coordenadas válidas"
            }
        ])

    def test_monta_kml_com_pastas_e_coordenadas(self):
        kml = montar_kml_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            campos_detalhe=[
                "Endereço",
                "Coordenadas",
                "Receita",
                "Distância"
            ]
        ).decode("utf-8")

        self.assertIn("<name>Sites</name>", kml)
        self.assertIn("<name>Clientes</name>", kml)
        self.assertIn("<name>Vínculos site x cliente</name>", kml)
        self.assertIn("-43.90000000,-19.90000000,0", kml)
        self.assertIn("-43.91000000,-19.91000000,0", kml)
        self.assertIn("SITE &amp; A", kml)
        self.assertIn("Restrito", kml)

    def test_monta_kmz_com_doc_kml(self):
        kmz = montar_kmz_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados
        )

        with ZipFile(BytesIO(kmz)) as arquivo_zip:
            self.assertIn(
                "doc.kml",
                arquivo_zip.namelist()
            )
            conteudo = arquivo_zip.read("doc.kml").decode("utf-8")

        self.assertIn(
            "<kml",
            conteudo
        )

    def test_selecao_de_itens_remove_pastas_nao_escolhidas(self):
        kml = montar_kml_mapa(
            self.df_sites,
            self.df_clientes,
            self.df_links_clientes,
            self.df_links_sites,
            self.df_nao_plotados,
            itens=[
                "sites"
            ]
        ).decode("utf-8")

        self.assertIn(
            "<name>Sites</name>",
            kml
        )
        self.assertNotIn(
            "<name>Clientes</name>",
            kml
        )

    def test_cor_kml_converte_rgba_para_aabbggrr(self):
        self.assertEqual(
            cor_kml([255, 0, 0, 128]),
            "800000ff"
        )


if __name__ == "__main__":
    unittest.main()
