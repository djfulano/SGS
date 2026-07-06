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
                self.assertEqual(
                    Path(second["path"]).parent.name,
                    "123"
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_add_site_contract_salva_multiplos_documentos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"

                for nome, conteudo in [
                    ("documento_a.pdf", b"a"),
                    ("documento_b.docx", b"b"),
                    ("documento_c.msg", b"c")
                ]:
                    contract_service.add_site_contract(
                        "123",
                        "Site A",
                        nome,
                        conteudo,
                        uploaded_by="tester"
                    )

                documentos = contract_service.list_site_documents("123")

                self.assertEqual(
                    len(documentos),
                    3
                )
                self.assertEqual(
                    {
                        documento["original_filename"]
                        for documento in documentos
                    },
                    {
                        "documento_a.pdf",
                        "documento_b.docx",
                        "documento_c.msg"
                    }
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

    def test_index_contract_folders_usa_codigo_aquiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_site = contract_service.CONTRACTS_DIR / "456"
                pasta_site.mkdir(parents=True)
                (pasta_site / "documento.pdf").write_bytes(b"pdf")
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.index_contract_folders({
                    "ABC_BH_123_IP": site
                })
                documentos = contract_service.list_site_contracts("456")

                self.assertEqual(
                    resumo["arquivos_indexados"],
                    1
                )
                self.assertEqual(
                    len(documentos),
                    1
                )
                self.assertEqual(
                    documentos[0]["site_name"],
                    "ABC_BH_123_IP"
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

    def test_restore_archived_contract_file_retorna_para_pasta_site(self):
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

                restored = contract_service.restore_archived_contract_file(
                    archived["id"],
                    restored_by="master"
                )
                ativos = contract_service.list_site_documents("123")
                arquivados = contract_service.list_site_documents(
                    "123",
                    archived=True
                )

                self.assertFalse(
                    restored["archived"]
                )
                self.assertNotIn(
                    "Arquivado",
                    Path(restored["path"]).parts
                )
                self.assertFalse(
                    Path(archived["path"]).exists()
                )
                self.assertTrue(
                    Path(restored["path"]).exists()
                )
                self.assertEqual(
                    len(ativos),
                    1
                )
                self.assertEqual(
                    arquivados,
                    []
                )
                self.assertEqual(
                    contract_service.read_contract_file(ativos[0]),
                    b"conteudo"
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_delete_archived_contract_file_remove_arquivo_e_indice(self):
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

                removed = contract_service.delete_archived_contract_file(
                    archived["id"]
                )
                ativos = contract_service.list_site_documents("123")
                arquivados = contract_service.list_site_documents(
                    "123",
                    archived=True
                )

                self.assertEqual(
                    removed["id"],
                    archived["id"]
                )
                self.assertFalse(
                    Path(archived["path"]).exists()
                )
                self.assertEqual(
                    ativos,
                    []
                )
                self.assertEqual(
                    arquivados,
                    []
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_delete_archived_contract_file_bloqueia_documento_ativo(self):
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

                with self.assertRaises(ValueError):
                    contract_service.delete_archived_contract_file(
                        record["id"]
                    )

                self.assertTrue(
                    Path(record["path"]).exists()
                )
                self.assertEqual(
                    len(contract_service.list_site_documents("123")),
                    1
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
                            "Pasta Esperada": "2",
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

    def test_migrar_pastas_documentos_para_codigo_aquiles_simula_sem_alterar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_origem = contract_service.CONTRACTS_DIR / "ABC_BH_123_IP"
                pasta_origem.mkdir(parents=True)
                arquivo = pasta_origem / "documento.pdf"
                arquivo.write_bytes(b"pdf")
                contract_service.save_contract_index({
                    "sites": {
                        "456": [
                            {
                                "id": "doc-1",
                                "site_code": "456",
                                "site_name": "ABC_BH_123_IP",
                                "original_filename": "documento.pdf",
                                "path": str(arquivo)
                            }
                        ]
                    }
                })
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.migrar_pastas_documentos_para_codigo_aquiles(
                    {
                        "ABC_BH_123_IP": site
                    },
                    dry_run=True,
                    usuario="tester"
                )
                indice = contract_service.load_contract_index()

                self.assertEqual(
                    resumo["pastas_migradas"],
                    1
                )
                self.assertEqual(
                    resumo["arquivos_movidos"],
                    1
                )
                self.assertEqual(
                    resumo["registros_atualizados"],
                    1
                )
                self.assertTrue(
                    arquivo.exists()
                )
                self.assertFalse(
                    (contract_service.CONTRACTS_DIR / "456" / "documento.pdf").exists()
                )
                self.assertEqual(
                    indice["sites"]["456"][0]["path"],
                    str(arquivo)
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_migrar_pastas_documentos_para_codigo_aquiles_move_ativos_e_arquivados(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_origem = contract_service.CONTRACTS_DIR / "ABC_BH_123_IP"
                pasta_arquivado = pasta_origem / "Arquivado"
                pasta_arquivado.mkdir(parents=True)
                arquivo_ativo = pasta_origem / "documento.pdf"
                arquivo_arquivado = pasta_arquivado / "antigo.pdf"
                arquivo_ativo.write_bytes(b"ativo")
                arquivo_arquivado.write_bytes(b"arquivado")
                contract_service.save_contract_index({
                    "sites": {
                        "456": [
                            {
                                "id": "doc-1",
                                "site_code": "456",
                                "site_name": "ABC_BH_123_IP",
                                "original_filename": "documento.pdf",
                                "path": str(arquivo_ativo)
                            },
                            {
                                "id": "doc-2",
                                "site_code": "456",
                                "site_name": "ABC_BH_123_IP",
                                "original_filename": "antigo.pdf",
                                "archived": True,
                                "path": str(arquivo_arquivado)
                            }
                        ]
                    }
                })
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.migrar_pastas_documentos_para_codigo_aquiles(
                    {
                        "ABC_BH_123_IP": site
                    },
                    dry_run=False,
                    usuario="tester"
                )
                indice = contract_service.load_contract_index()
                novo_ativo = contract_service.CONTRACTS_DIR / "456" / "documento.pdf"
                novo_arquivado = contract_service.CONTRACTS_DIR / "456" / "Arquivado" / "antigo.pdf"

                self.assertEqual(
                    resumo["arquivos_movidos"],
                    2
                )
                self.assertEqual(
                    resumo["registros_atualizados"],
                    2
                )
                self.assertTrue(
                    novo_ativo.exists()
                )
                self.assertTrue(
                    novo_arquivado.exists()
                )
                self.assertFalse(
                    pasta_origem.exists()
                )
                self.assertEqual(
                    indice["sites"]["456"][0]["path"],
                    str(novo_ativo)
                )
                self.assertEqual(
                    indice["sites"]["456"][1]["path"],
                    str(novo_arquivado)
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

    def test_migrar_pastas_documentos_para_codigo_aquiles_resolve_conflito_de_nome(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = contract_service.CONTRACTS_DIR
            original_index = contract_service.CONTRACTS_INDEX_FILE

            try:
                contract_service.CONTRACTS_DIR = Path(temp_dir) / "contracts"
                contract_service.CONTRACTS_INDEX_FILE = Path(temp_dir) / "contracts.json"
                pasta_origem = contract_service.CONTRACTS_DIR / "ABC_BH_123_IP"
                pasta_destino = contract_service.CONTRACTS_DIR / "456"
                pasta_origem.mkdir(parents=True)
                pasta_destino.mkdir(parents=True)
                arquivo_origem = pasta_origem / "documento.pdf"
                arquivo_origem.write_bytes(b"novo")
                (pasta_destino / "documento.pdf").write_bytes(b"existente")
                contract_service.save_contract_index({
                    "sites": {
                        "456": [
                            {
                                "id": "doc-1",
                                "site_code": "456",
                                "site_name": "ABC_BH_123_IP",
                                "original_filename": "documento.pdf",
                                "path": str(arquivo_origem)
                            }
                        ]
                    }
                })
                site = Site("ABC_BH_123_IP")
                site.codigo_topos = "456"

                resumo = contract_service.migrar_pastas_documentos_para_codigo_aquiles(
                    {
                        "ABC_BH_123_IP": site
                    },
                    dry_run=False,
                    usuario="tester"
                )

                self.assertEqual(
                    len(resumo["conflitos"]),
                    1
                )
                self.assertTrue(
                    (pasta_destino / "documento.pdf").exists()
                )
                self.assertEqual(
                    len(list(pasta_destino.glob("documento*.pdf"))),
                    2
                )
                indice = contract_service.load_contract_index()
                self.assertNotEqual(
                    indice["sites"]["456"][0]["path"],
                    str(pasta_destino / "documento.pdf")
                )
                self.assertTrue(
                    Path(indice["sites"]["456"][0]["path"]).exists()
                )

            finally:
                contract_service.CONTRACTS_DIR = original_dir
                contract_service.CONTRACTS_INDEX_FILE = original_index

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
