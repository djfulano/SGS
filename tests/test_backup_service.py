import tempfile
import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app.services.backup_service import calcular_fontes_backup
from app.services.backup_service import criar_backup
from app.services.backup_service import deve_executar_backup_automatico
from app.services.backup_service import inspecionar_backup
from app.services.backup_service import listar_backups
from app.services.backup_service import load_backup_config
from app.services.backup_service import read_backup_file
from app.services.backup_service import restaurar_backup


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
                "app.services.backup_service.BACKUP_DIR",
                backups
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
                "app.services.backup_service.BACKUP_DIR",
                backups
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
                "app.services.backup_service.BACKUP_DIR",
                backups
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
                "app.services.backup_service.BACKUP_DIR",
                backups
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

    def test_load_backup_config_normaliza_backup_dir_para_destino_oficial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            config_file = base / "backup_config.json"
            config_file.write_text(
                json.dumps({
                    "backup_dir": "/opt/SGS/backups",
                    "retention": 3
                }),
                encoding="utf-8"
            )

            with patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config_file
            ), patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ):
                config = load_backup_config()

            self.assertEqual(
                config["backup_dir"],
                str(backups)
            )
            self.assertEqual(
                config["retention"],
                3
            )

    def test_criar_e_listar_backup_usam_destino_oficial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            destino_antigo = base / "fora_do_volume"
            imports = base / "imports"
            config = base / "config"
            imports.mkdir()
            config.mkdir()
            destino_antigo.mkdir()
            (imports / "clientes.xlsx").write_text(
                "clientes",
                encoding="utf-8"
            )

            backup_config = {
                "backup_dir": str(destino_antigo),
                "include_imports": True,
                "include_config": False,
                "include_cache": False,
                "include_contracts": False,
                "include_database": False,
                "include_system_files": False
            }

            with patch(
                "app.services.backup_service.IMPORTS_DIR",
                imports
            ), patch(
                "app.services.backup_service.CONFIG_DIR",
                config
            ), patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ):
                resultado = criar_backup(
                    backup_config,
                    usuario="teste",
                    base_dir=base
                )
                backups_listados = listar_backups(destino_antigo)

            self.assertTrue(
                str(resultado["path"]).startswith(str(backups))
            )
            self.assertFalse(
                list(destino_antigo.glob("sgs_backup_*.zip"))
            )
            self.assertEqual(
                len(backups_listados),
                1
            )

    def test_criar_backup_sem_persistir_nao_altera_configuracao(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            config = base / "config"
            backups.mkdir()
            config.mkdir()
            config_file = config / "backup_config.json"
            config_file.write_text(
                json.dumps({
                    "backup_dir": str(backups),
                    "retention": 3
                }),
                encoding="utf-8"
            )

            backup_config = {
                "backup_dir": str(backups),
                "retention": 9999,
                "include_imports": False,
                "include_config": False,
                "include_cache": False,
                "include_contracts": False,
                "include_database": False,
                "include_system_files": False
            }

            with patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config_file
            ):
                criar_backup(
                    backup_config,
                    usuario="teste",
                    base_dir=base,
                    persistir_config=False
                )
                config_carregada = load_backup_config()

            self.assertEqual(
                config_carregada["retention"],
                3
            )

    def test_read_backup_file_le_arquivo_da_pasta_oficial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backups = Path(temp_dir) / "backups"
            backups.mkdir()
            arquivo = backups / "sgs_backup_teste.zip"
            arquivo.write_bytes(b"backup")

            with patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ):
                conteudo = read_backup_file(
                    "sgs_backup_teste.zip"
                )

            self.assertEqual(
                conteudo,
                b"backup"
            )

    def test_read_backup_file_aceita_caminho_relativo_da_lista(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backups = Path(temp_dir) / "backups"
            backups.mkdir()
            arquivo = backups / "sgs_backup_teste.zip"
            arquivo.write_bytes(b"backup")

            with patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ):
                conteudo = read_backup_file(
                    "backups/sgs_backup_teste.zip"
                )

            self.assertEqual(
                conteudo,
                b"backup"
            )

    def test_read_backup_file_bloqueia_arquivo_fora_da_pasta_oficial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            externo = base / "fora.zip"
            backups.mkdir()
            externo.write_bytes(b"fora")

            with patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ):
                with self.assertRaises(ValueError):
                    read_backup_file(
                        externo
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

    def test_inspecionar_backup_bloqueia_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backup = base / "malicioso.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "../evil.txt",
                    "x"
                )
                zip_file.writestr(
                    r"..\evil2.txt",
                    "x"
                )
                zip_file.writestr(
                    r"C:\temp\evil3.txt",
                    "x"
                )

            info = inspecionar_backup(backup)

            self.assertFalse(info["restauravel"])
            self.assertEqual(
                info["entradas_invalidas"],
                [
                    "../evil.txt",
                    r"..\evil2.txt",
                    r"C:\temp\evil3.txt"
                ]
            )

            with self.assertRaises(ValueError):
                restaurar_backup(
                    backup,
                    base_dir=base,
                    criar_backup_previo=False
                )

    def test_restaurar_backup_substitui_snapshot_e_cria_backup_previo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            imports = base / "imports"
            config = base / "config"
            cache = base / "cache"
            contracts = base / "contracts"
            backups = base / "backups"

            for pasta in [
                imports,
                config,
                cache,
                contracts,
                backups
            ]:
                pasta.mkdir()

            (imports / "atual.xlsx").write_text(
                "atual",
                encoding="utf-8"
            )
            (imports / "remover.xlsx").write_text(
                "remover",
                encoding="utf-8"
            )
            (config / "users.json").write_text(
                '{"atual": true}',
                encoding="utf-8"
            )
            (cache / "mapa.json").write_text(
                "cache-atual",
                encoding="utf-8"
            )
            (contracts / "SITE_ATUAL").mkdir()
            (contracts / "SITE_ATUAL" / "doc.pdf").write_text(
                "contrato atual",
                encoding="utf-8"
            )
            (base / "rede.db").write_text(
                "db-atual",
                encoding="utf-8"
            )

            backup = backups / "sgs_backup_restore.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "imports/restaurado.xlsx",
                    "novo"
                )
                zip_file.writestr(
                    "config/users.json",
                    '{"restaurado": true}'
                )
                zip_file.writestr(
                    "cache/mapa.json",
                    "cache-novo"
                )
                zip_file.writestr(
                    "contracts/SITE_NOVO/doc.pdf",
                    "contrato novo"
                )
                zip_file.writestr(
                    "rede.db",
                    "db-novo"
                )

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
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ), patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ):
                resultado = restaurar_backup(
                    backup,
                    usuario="teste",
                    restaurar_contracts=False,
                    incluir_cache=True,
                    base_dir=base
                )

            self.assertTrue(
                Path(resultado["backup_previo"]["path"]).exists()
            )
            self.assertEqual(
                (imports / "restaurado.xlsx").read_text(encoding="utf-8"),
                "novo"
            )
            self.assertFalse((imports / "remover.xlsx").exists())
            self.assertEqual(
                (config / "users.json").read_text(encoding="utf-8"),
                '{"restaurado": true}'
            )
            self.assertEqual(
                (cache / "mapa.json").read_text(encoding="utf-8"),
                "cache-novo"
            )
            self.assertEqual(
                (base / "rede.db").read_text(encoding="utf-8"),
                "db-novo"
            )
            self.assertTrue(
                (contracts / "SITE_ATUAL" / "doc.pdf").exists()
            )
            self.assertFalse(
                (contracts / "SITE_NOVO" / "doc.pdf").exists()
            )

    def test_restaurar_backup_ignora_cache_ocupado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            imports = base / "imports"
            config = base / "config"
            cache = base / "cache"
            backups = base / "backups"

            for pasta in [
                imports,
                config,
                cache,
                backups
            ]:
                pasta.mkdir()

            (imports / "atual.xlsx").write_text(
                "atual",
                encoding="utf-8"
            )
            (cache / "mapa.json").write_text(
                "cache-atual",
                encoding="utf-8"
            )

            backup = backups / "sgs_backup_cache_ocupado.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "imports/restaurado.xlsx",
                    "novo"
                )
                zip_file.writestr(
                    "cache/mapa.json",
                    "cache-novo"
                )

            from app.services import backup_service

            copiar_original = backup_service._copiar_fonte_extraida

            def copiar_com_cache_ocupado(origem, destino, tipo):
                if Path(destino) == cache:
                    raise OSError(
                        16,
                        "Device or resource busy",
                        str(destino)
                    )

                return copiar_original(
                    origem,
                    destino,
                    tipo
                )

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
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ), patch(
                "app.services.backup_service._copiar_fonte_extraida",
                side_effect=copiar_com_cache_ocupado
            ):
                resultado = restaurar_backup(
                    backup,
                    usuario="teste",
                    incluir_cache=True,
                    criar_backup_previo=False,
                    base_dir=base
                )

            self.assertEqual(
                (imports / "restaurado.xlsx").read_text(encoding="utf-8"),
                "novo"
            )
            self.assertEqual(
                (cache / "mapa.json").read_text(encoding="utf-8"),
                "cache-atual"
            )
            self.assertTrue(
                resultado["avisos"]
            )

    def test_restaurar_backup_nao_move_banco_sqlite_em_uso(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backups = base / "backups"
            config = base / "config"
            imports = base / "imports"
            cache = base / "cache"

            for pasta in [
                backups,
                config,
                imports,
                cache
            ]:
                pasta.mkdir()

            banco = base / "rede.db"
            banco.write_text(
                "db-atual",
                encoding="utf-8"
            )

            backup = backups / "sgs_backup_database.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "rede.db",
                    "db-restaurado"
                )

            def move_bloqueado(origem, destino):
                raise OSError(
                    16,
                    "Device or resource busy",
                    str(origem)
                )

            with patch(
                "app.services.backup_service.CONFIG_DIR",
                config
            ), patch(
                "app.services.backup_service.IMPORTS_DIR",
                imports
            ), patch(
                "app.services.backup_service.CACHE_DIR",
                cache
            ), patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ), patch(
                "app.services.backup_service.shutil.move",
                side_effect=move_bloqueado
            ):
                restaurar_backup(
                    backup,
                    usuario="teste",
                    incluir_cache=False,
                    criar_backup_previo=False,
                    base_dir=base
                )

            self.assertEqual(
                banco.read_text(encoding="utf-8"),
                "db-restaurado"
            )

    def test_restaurar_backup_restaurando_contracts_quando_marcado(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            contracts = base / "contracts"
            backups = base / "backups"
            config = base / "config"
            imports = base / "imports"
            cache = base / "cache"

            for pasta in [
                contracts,
                backups,
                config,
                imports,
                cache
            ]:
                pasta.mkdir()

            (contracts / "SITE_ANTIGO").mkdir()
            (contracts / "SITE_ANTIGO" / "doc.pdf").write_text(
                "antigo",
                encoding="utf-8"
            )
            (base / "rede.db").write_text(
                "db",
                encoding="utf-8"
            )
            backup = backups / "sgs_backup_contracts.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "contracts/SITE_NOVO/doc.pdf",
                    "novo"
                )

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
                "app.services.backup_service.CONTRACTS_DIR",
                contracts
            ), patch(
                "app.services.backup_service.BACKUP_DIR",
                backups
            ), patch(
                "app.services.backup_service.BACKUP_CONFIG_FILE",
                config / "backup_config.json"
            ):
                restaurar_backup(
                    backup,
                    usuario="teste",
                    restaurar_contracts=True,
                    incluir_cache=False,
                    base_dir=base
                )

            self.assertFalse(
                (contracts / "SITE_ANTIGO" / "doc.pdf").exists()
            )
            self.assertEqual(
                (contracts / "SITE_NOVO" / "doc.pdf").read_text(
                    encoding="utf-8"
                ),
                "novo"
            )

    def test_restaurar_backup_recusa_zip_sem_fonte_restauravel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            backup = base / "vazio.zip"

            with ZipFile(backup, "w") as zip_file:
                zip_file.writestr(
                    "README.md",
                    "sem dados"
                )

            with self.assertRaises(ValueError):
                restaurar_backup(
                    backup,
                    base_dir=base,
                    criar_backup_previo=False
                )


if __name__ == "__main__":
    unittest.main()
