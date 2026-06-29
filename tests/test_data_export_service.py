import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from app.services import data_export_service


class DataExportServiceTest(unittest.TestCase):

    def test_arquivo_para_download_retorna_none_quando_ausente(self):
        with TemporaryDirectory() as temp_dir:
            resultado = data_export_service.arquivo_para_download(
                Path(temp_dir) / "ausente.xlsx"
            )

        self.assertIsNone(resultado)

    def test_arquivo_para_download_retorna_bytes(self):
        with TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "clientes.xlsx"
            caminho.write_bytes(b"conteudo")

            resultado = data_export_service.arquivo_para_download(caminho)

        self.assertEqual(resultado["data"], b"conteudo")
        self.assertEqual(resultado["file_name"], "clientes.xlsx")

    def test_exportar_equipamentos_excel_usa_novas_colunas(self):
        df = pd.DataFrame([
            {
                "Ícone": "AP",
                "Modelo": "AP 300",
                "Fabricante": "Ubiquiti",
                "Software": "AirOS",
                "Tipo": "WiFi",
                "Código": "EQ1",
                "Valor": 50
            }
        ])

        with patch(
            "app.services.data_export_service.load_equipment_catalog",
            return_value=df
        ):
            conteudo = data_export_service.exportar_equipamentos_excel()

        with TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "equipamentos.xlsx"
            caminho.write_bytes(conteudo)
            df_exportado = pd.read_excel(caminho)

        self.assertEqual(
            df_exportado.columns.tolist(),
            [
                "Ícone",
                "Modelo",
                "Fabricante",
                "Software",
                "Tipo",
                "Código",
                "Valor"
            ]
        )

    def test_exportar_indice_documentos_nao_inclui_conteudo_fisico(self):
        with patch(
            "app.services.data_export_service.load_contract_index",
            return_value={
                "sites": {
                    "123": [
                        {
                            "original_filename": "contrato.pdf",
                            "path": "/app/contracts/SITE/contrato.pdf",
                            "size": 10,
                            "notes": "Teste"
                        }
                    ]
                }
            }
        ):
            conteudo = data_export_service.exportar_indice_documentos_excel()

        with TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "documentos.xlsx"
            caminho.write_bytes(conteudo)
            df_exportado = pd.read_excel(caminho)

        self.assertIn("Caminho", df_exportado.columns)
        self.assertNotIn("Conteúdo", df_exportado.columns)
        self.assertEqual(df_exportado.loc[0, "Arquivo"], "contrato.pdf")

    def test_exportar_mapa_retorna_none_sem_cache(self):
        with patch(
            "app.services.data_export_service.carregar_cache_mapa",
            return_value={}
        ):
            self.assertIsNone(data_export_service.exportar_mapa())

    def test_exportar_mapa_usa_pacote_compilado(self):
        pacote = {
            "gerado_em": "2026-06-29 10:00:00",
            "sites": [
                {
                    "Site": "POP_A",
                    "Latitude": -23.5,
                    "Longitude": -46.6
                }
            ],
            "clientes": [],
            "links_clientes": [],
            "links_sites": [],
            "nao_plotados": []
        }

        with patch(
            "app.services.data_export_service.carregar_cache_mapa",
            return_value={
                "abc": pacote
            }
        ):
            conteudo = data_export_service.exportar_mapa("KML")

        self.assertIn(b"<kml", conteudo)
        self.assertIn(b"POP_A", conteudo)


if __name__ == "__main__":
    unittest.main()
