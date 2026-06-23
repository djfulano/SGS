from app.database.database import engine
from app.database.database import Base

from app.models.site_model import SiteModel
from app.models.cliente_model import ClienteModel

from app.config import CLIENTES_FILE
from app.importers.structure_importer import importar_estrutura_atual

from app.importers.excel_importer import importar_clientes

from app.services.database_service import sincronizar_banco


# Criar banco/tabelas
Base.metadata.create_all(bind=engine)


# =========================
# IMPORTAR ESTRUTURA
# =========================

sites, assinaturas, equipamentos = importar_estrutura_atual()


# =========================
# IMPORTAR CLIENTES
# =========================

clientes_sem_site = importar_clientes(
    CLIENTES_FILE,
    assinaturas
)


# =========================
# SALVAR NO BANCO
# =========================

sincronizar_banco(sites)


# =========================
# MOSTRAR ESTRUTURA
# =========================

print("\nESTRUTURA DA REDE\n")


raizes = []

for site in sites.values():

    if site.pai is None:

        raizes.append(site)


for raiz in raizes:

    raiz.exibir_arvore()


# =========================
# MOSTRAR INCONSISTÊNCIAS
# =========================

print("\nCLIENTES SEM SITE\n")


for nome, assinatura in clientes_sem_site[:20]:

    print(f"{nome} -> {assinatura}")


print("\nPROCESSAMENTO FINALIZADO\n")
