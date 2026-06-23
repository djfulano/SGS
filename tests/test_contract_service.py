import tempfile
import unittest
from pathlib import Path

from app.models.site import Site
from app.services import contract_service


class ContractServiceTest(unittest.TestCase):

    def test_add_site_contract_creates_version_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"

                first = contract_service.add_site_contract(
                    "123",
                    "Site A",
                    "contrato.pdf",
                    b"versao 1",
                    uploaded_by="tester"
                )
                second = contract_service.add_site_contract(
                    "123",
                    "Site A",
                    "contrato.pdf",
                    b"versao 2",
                    uploaded_by="tester"
                )

                versions = contract_service.list_site_contracts("123")

                self.assertEqual(first["version"], 1)
                self.assertEqual(second["version"], 2)
                self.assertEqual(len(versions), 2)
                self.assertEqual(
                    contract_service.read_contract_file(second),
                    b"versao 2"
                )
                self.assertIn(
                    "Site_A",
                    second["path"]
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_index_contract_folders_usa_nome_snmpc_e_aceita_msg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_site = contract_service.CONTRACTS_DIR / "ABC_BH_123_IP"
                pasta_site.mkdir(parents=True)
                (pasta_site / "contrato.pdf").write_bytes(b"pdf")
                (pasta_site / "email.msg").write_bytes(b"msg")
                (pasta_site / "Thumbs.db").write_bytes(b"thumb")
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.index_contract_folders({
                    "ABC_BH_123_IP": site
                })
                resumo_repetido = contract_service.index_contract_folders({
                    "ABC_BH_123_IP": site
                })
                versions = contract_service.list_site_contracts("456")

                self.assertEqual(
                    resumo["arquivos_indexados"],
                    2
                )
                self.assertEqual(
                    resumo_repetido["arquivos_indexados"],
                    0
                )
                self.assertEqual(
                    len(versions),
                    2
                )
                self.assertEqual(
                    {
                        contrato["original_filename"]
                        for contrato in versions
                    },
                    {
                        "contrato.pdf",
                        "email.msg"
                    }
                )
                self.assertTrue(
                    any(
                        "Thumbs.db" in arquivo
                        for arquivo in resumo["arquivos_ignorados"]
                    )
                )
                self.assertEqual(
                    contract_service.read_contract_file(versions[0]),
                    b"pdf"
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_index_contract_folders_reporta_site_nao_localizado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_site = contract_service.CONTRACTS_DIR / "SEM_CADASTRO_IP"
                pasta_site.mkdir(parents=True)
                (pasta_site / "contrato.pdf").write_bytes(b"pdf")

                resumo = contract_service.index_contract_folders({})

                self.assertEqual(
                    resumo["sites_nao_localizados"],
                    [
                        "SEM_CADASTRO_IP"
                    ]
                )
                self.assertEqual(
                    resumo["arquivos_indexados"],
                    0
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_archive_contract_file_move_para_pasta_arquivado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                record = contract_service.add_site_contract(
                    "123",
                    "ABC_BH_123_IP",
                    "documento.pdf",
                    b"conteudo",
                    uploaded_by="tester"
                )

                archived = contract_service.archive_contract_file(
                    record["id"],
                    archived_by="master"
                )
                ativos = contract_service.list_site_documents("123")
                arquivados = contract_service.list_site_documents(
                    "123",
                    archived=True
                )

                self.assertTrue(
                    archived["archived"]
                )
                self.assertIn(
                    "Arquivado",
                    archived["path"]
                )
                self.assertFalse(
                    Path(record["path"]).exists()
                )
                self.assertTrue(
                    Path(archived["path"]).exists()
                )
                self.assertEqual(
                    ativos,
                    []
                )
                self.assertEqual(
                    len(arquivados),
                    1
                )
                self.assertEqual(
                    contract_service.read_contract_file(arquivados[0]),
                    b"conteudo"
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_compare_sites_and_document_folders_lista_diferencas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                (contract_service.CONTRACTS_DIR / "COM_PASTA_IP").mkdir(parents=True)
                pasta_sem_site = contract_service.CONTRACTS_DIR / "SEM_SITE_IP"
                pasta_sem_site.mkdir()
                (pasta_sem_site / "documento.pdf").write_bytes(b"pdf")
                (pasta_sem_site / "Thumbs.db").write_bytes(b"thumb")
                (contract_service.CONTRACTS_DIR / "Arquivado").mkdir()
                site_com_pasta = Site("COM_PASTA_IP")
                site_com_pasta.codigo_topos = "1"
                site_sem_pasta = Site("SEM_PASTA_IP")
                site_sem_pasta.codigo_topos = "2"
                site_sem_pasta.nome_cadastro = "Sem Pasta"
                site_sem_pasta.status_cadastro = "Ativo"
                site_sem_pasta.cidade = "Sao Paulo"
                site_sem_pasta.uf = "SP"

                sites_sem_pasta, pastas_sem_site = contract_service.compare_sites_and_document_folders({
                    "COM_PASTA_IP": site_com_pasta,
                    "SEM_PASTA_IP": site_sem_pasta
                })

                self.assertEqual(
                    sites_sem_pasta,
                    [
                        {
                            "Site SNMPc": "SEM_PASTA_IP",
                            "Código Aquiles": "2",
                            "Nome Cadastro": "Sem Pasta",
                            "Status Cadastro": "Ativo",
                            "Cidade": "Sao Paulo",
                            "UF": "SP"
                        }
                    ]
                )
                self.assertEqual(
                    len(pastas_sem_site),
                    1
                )
                self.assertEqual(
                    pastas_sem_site[0]["Pasta"],
                    "SEM_SITE_IP"
                )
                self.assertEqual(
                    pastas_sem_site[0]["Qtd arquivos"],
                    2
                )
                self.assertEqual(
                    pastas_sem_site[0]["Qtd arquivos válidos"],
                    1
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir

    def test_registros_antigos_fora_da_pasta_atual_sao_ignorados(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_site = contract_service.CONTRACTS_DIR / "ABC_BH_123_IP"
                pasta_site.mkdir(parents=True)
                (pasta_site / "contrato.pdf").write_bytes(b"pdf")
                antigo = Path(temp_dir) / "config" / "contracts" / "arquivo.pdf"
                antigo.parent.mkdir(parents=True)
                antigo.write_bytes(b"antigo")
                contract_service.save_contract_index({
                    "sites": {
                        "456": [
                            {
                                "original_filename": "arquivo.pdf",
                                "size": 6,
                                "path": str(antigo)
                            }
                        ]
                    }
                })
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.index_contract_folders({
                    "ABC_BH_123_IP": site
                })
                versions = contract_service.list_site_contracts("456")

                self.assertEqual(
                    resumo["arquivos_indexados"],
                    1
                )
                self.assertEqual(
                    len(versions),
                    1
                )
                self.assertEqual(
                    versions[0]["original_filename"],
                    "contrato.pdf"
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_read_contract_file_bloqueia_caminho_fora_da_pasta(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_DIR.mkdir()
                segredo = Path(temp_dir) / "segredo.txt"
                segredo.write_bytes(b"nao deve ler")

                self.assertIsNone(
                    contract_service.read_contract_file(
                        {
                            "path": str(segredo)
                        }
                    )
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir

    def test_add_site_contract_rejeita_extensao_nao_permitida(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"

                with self.assertRaises(ValueError):
                    contract_service.add_site_contract(
                        "123",
                        "Site A",
                        "script.exe",
                        b"conteudo",
                        uploaded_by="tester"
                    )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index


if __name__ == "__main__":
    unittest.main()
