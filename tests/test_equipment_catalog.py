import unittest
from io import BytesIO

import pandas as pd

from app.services.equipment_catalog import EQUIPMENT_CATALOG_COLUMNS
from app.services.equipment_catalog import import_equipment_catalog_excel
from app.services.equipment_catalog import normalize_catalog_dataframe


class EquipmentCatalogTest(unittest.TestCase):

    def test_catalogo_usa_modelo_fabricante_e_software(self):
        df = normalize_catalog_dataframe(pd.DataFrame([
            {
                "Ícone": "AP",
                "Modelo": "AP 300",
                "Fabricante": "Ubiquiti",
                "Software": "AirOS",
                "Tipo": "WiFi",
                "Código": "EQ1",
                "Valor": "R$ 50,00"
            }
        ]))

        self.assertEqual(df.columns.tolist(), EQUIPMENT_CATALOG_COLUMNS)
        self.assertEqual(df.loc[0, "Modelo"], "AP 300")
        self.assertEqual(df.loc[0, "Fabricante"], "Ubiquiti")
        self.assertEqual(df.loc[0, "Software"], "AirOS")
        self.assertEqual(df.loc[0, "Valor"], 50)

    def test_catalogo_antigo_nome_vira_modelo(self):
        df = normalize_catalog_dataframe(pd.DataFrame([
            {
                "Ícone": "ONU",
                "Nome": "ONU XPTO",
                "Tipo": "Fibra"
            }
        ]))

        self.assertEqual(df.loc[0, "Modelo"], "ONU XPTO")
        self.assertNotIn("Nome", df.columns)

    def test_importacao_excel_antigo_nome_vira_modelo(self):
        arquivo = BytesIO()
        pd.DataFrame([
            {
                "Ícone": "RADIO",
                "Nome": "Rocket M5",
                "Tipo": "Rádio"
            }
        ]).to_excel(
            arquivo,
            index=False
        )
        arquivo.seek(0)

        df = import_equipment_catalog_excel(
            arquivo,
            pd.DataFrame()
        )

        self.assertEqual(df.loc[0, "Modelo"], "Rocket M5")

    def test_modelo_prevalece_quando_nome_tambem_existe(self):
        df = normalize_catalog_dataframe(pd.DataFrame([
            {
                "Ícone": "SW",
                "Nome": "Nome antigo",
                "Modelo": "Modelo novo"
            }
        ]))

        self.assertEqual(df.loc[0, "Modelo"], "Modelo novo")


if __name__ == "__main__":
    unittest.main()
