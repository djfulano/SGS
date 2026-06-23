import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import pandas as pd
    from app.services.products import montar_clientes_produtos_base
except ModuleNotFoundError:
    pd = None
    montar_clientes_produtos_base = None



@unittest.skipIf(pd is None, "pandas nao instalado")
class ProductsTest(unittest.TestCase):

    def test_base_produtos_considera_clientes_sem_vinculo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho_clientes = Path(temp_dir) / "clientes.xlsx"
            caminho_clientes.write_text("", encoding="utf-8")

            df_excel = pd.DataFrame([
                {
                    "Cliente": "Cliente SVA",
                    "Assinatura": "15554503",
                    "Produto": "NEOFIREWALL FN 30E WEB",
                    "Receita": 100,
                    "Endereco": "",
                    "Bairro": "",
                    "Cidade": ""
                }
            ])

            with patch(
                "app.services.products.CLIENTES_FILE",
                caminho_clientes
            ), patch(
                "app.services.products.carregar_clientes_excel_sva",
                return_value=df_excel
            ):
                df_base = montar_clientes_produtos_base({})

        self.assertIn(
            "NEOFIREWALL FN 30E WEB",
            set(df_base["Produto"])
        )
        self.assertEqual(
            df_base.loc[0, "Site"],
            ""
        )


if __name__ == "__main__":
    unittest.main()
