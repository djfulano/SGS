import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app.services.backup_service import calcular_fontes_backup
from app.services.backup_service import criar_backup
from app.services.backup_service import deve_executar_backup_automatico


class BackupServiceTest(unittest.TestCase):

    def test_criar_backup_zip_com_fontes_configuradas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            imports = base / "imports"
            config = base / "config"
            cache = base / "cache"
            backups = base / "backups"
            contracts = base / "contracts"

            imports.mkdir()
            config.mkdir()
            cache.mkdir()
            backups.mkdir()
            contracts.mkdir()

            (imports / "clientes.xlsx").write_text(
                "clientes",
                encoding="utf-8"
            )
            (config / "users.json").write_text(
                "{}",
                encoding="utf-8"
            )
            (cache / "mapa.json").write_text(
                "{}",
                encoding="utf-8"
            )
            (base / "rede.db").write_text(
                "db",
                encoding="utf-8"
            )
            (base / "VERSION").write_text(
                "teste",
                encoding="utf-8"
            )
            (contracts / "SITE_A").mkdir()
            (contracts / "SITE_A" / "documento.pdf").write_text(
                "documento",
                encoding="utf-8"
            )

            backup_config = {
                "backup_dir": str(backups),
                "retention": 5,
                "include_imports": True,
                "include_config": True,
                "include_cache": False,
                "include_contracts": False,
                "include_database": True,
                "include_system_files": True
            }

            with patch(
                "app.services.backup_service.IMPORTS_DIR",
                imports
            ), patch(
                "app.services.backup_service.CONFIG_DIR",
                config
            ), patch(
                "app.services.backup_service.CACHE_DIR",
                cache
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ), patch(
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ):
                resultado = criar_backup(
                    backup_config,
                    usuario="teste",
                    base_dir=base
                )

            caminho_backup = Path(resultado["path"])

            self.assertTrue(caminho_backup.exists())

            with ZipFile(caminho_backup) as zip_file:
                nomes = set(zip_file.namelist())

            self.assertIn("imports/clientes.xlsx", nomes)
            self.assertIn("config/users.json", nomes)
            self.assertIn("rede.db", nomes)
            self.assertIn("VERSION", nomes)
            self.assertIn("backup_metadata.json", nomes)
            self.assertNotIn("cache/mapa.json", nomes)
            self.assertNotIn("contracts/SITE_A/documento.pdf", nomes)

    def test_criar_backup_inclui_contracts_quando_configurado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            contracts = base / "contracts"
            pasta_site = contracts / "SITE_A"
            pasta_arquivado = pasta_site / "Arquivado"

            backups.mkdir()
            pasta_arquivado.mkdir(parents=True)
            (pasta_site / "documento.pdf").write_text(
                "documento",
                encoding="utf-8"
            )
            (pasta_arquivado / "antigo.pdf").write_text(
                "antigo",
                encoding="utf-8"
            )
            (backups / "nao_incluir.zip").write_text(
                "backup",
                encoding="utf-8"
            )

            backup_config = {
                "backup_dir": str(backups),
                "retention": 5,
                "include_imports": False,
                "include_config": False,
                "include_cache": False,
                "include_contracts": True,
                "include_database": False,
                "include_system_files": False
            }

            with patch(
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                base / "backup_config.json"
            ):
                resultado = criar_backup(
                    backup_config,
                    usuario="teste",
                    motivo="documentos",
                    base_dir=base
                )

            with ZipFile(resultado["path"]) as zip_file:
                nomes = set(zip_file.namelist())
                metadata = zip_file.read("backup_metadata.json").decode("utf-8")

            self.assertIn("contracts/SITE_A/documento.pdf", nomes)
            self.assertIn("contracts/SITE_A/Arquivado/antigo.pdf", nomes)
            self.assertNotIn("backups/nao_incluir.zip", nomes)
            self.assertIn('"backup_type": "documentos"', metadata)
            self.assertIn('"key": "contracts"', metadata)

    def test_criar_backup_aceita_arquivo_com_timestamp_antigo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            contracts = base / "contracts"
            pasta_site = contracts / "SITE_A"

            backups.mkdir()
            pasta_site.mkdir(parents=True)
            arquivo_antigo = pasta_site / "documento_antigo.pdf"
            arquivo_antigo.write_text(
                "documento",
                encoding="utf-8"
            )
            os.utime(
                arquivo_antigo,
                (0, 0)
            )

            backup_config = {
                "backup_dir": str(backups),
                "retention": 5,
                "include_imports": False,
                "include_config": False,
                "include_cache": False,
                "include_contracts": True,
                "include_database": False,
                "include_system_files": False
            }

            with patch(
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                base / "backup_config.json"
            ):
                resultado = criar_backup(
                    backup_config,
                    usuario="teste",
                    motivo="documentos",
                    base_dir=base
                )

            with ZipFile(resultado["path"]) as zip_file:
                nomes = set(zip_file.namelist())

            self.assertIn(
                "contracts/SITE_A/documento_antigo.pdf",
                nomes
            )

    def test_calcular_fontes_backup_retorna_previa(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            contracts = base / "contracts"
            imports = base / "imports"

            backups.mkdir()
            contracts.mkdir()
            imports.mkdir()
            (contracts / "documento.pdf").write_text(
                "documento",
                encoding="utf-8"
            )
            (imports / "clientes.xlsx").write_text(
                "clientes",
                encoding="utf-8"
            )

            backup_config = {
                "backup_dir": str(backups),
                "include_imports": True,
                "include_config": False,
                "include_cache": False,
                "include_contracts": True,
                "include_database": False,
                "include_system_files": False
            }

            with patch(
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ), patch(
                "app.services.backup_service.IMPORTS_DIR",
                imports
            ):
                fontes = calcular_fontes_backup(
                    backup_config,
                    base_dir=base
                )

            por_chave = {
                fonte["Chave"]: fonte
                for fonte in fontes
            }

            self.assertEqual(
                por_chave["imports"]["Arquivos"],
                1
            )
            self.assertEqual(
                por_chave["contracts"]["Arquivos"],
                1
            )
            self.assertGreater(
                por_chave["contracts"]["Tamanho bytes"],
                0
            )

    def test_deve_executar_backup_automatico_quando_ativo_sem_registro(self):
        self.assertTrue(
            deve_executar_backup_automatico({
                "enabled": True,
                "last_backup_at": "",
                "frequency": "Diário"
            })
        )

    def test_nao_executa_backup_automatico_quando_desativado(self):
        self.assertFalse(
            deve_executar_backup_automatico({
                "enabled": False,
                "last_backup_at": "",
                "frequency": "Diário"
            })
        )


if __name__ == "__main__":
    unittest.main()
