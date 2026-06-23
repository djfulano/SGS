from app.database.database import Base
from app.database.database import SessionLocal
from app.database.database import engine
from app.logs import registrar_log_sistema

from app.models.site_model import SiteModel
from app.models.cliente_model import ClienteModel


def sincronizar_banco(sites):

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:

        with session.begin():

            session.query(ClienteModel).delete()

            session.query(SiteModel).delete()

            sites_db = {}

            for site in sites.values():

                site_db = SiteModel(
                    nome=site.nome,
                    tipo=site.tipo
                )

                session.add(site_db)

                session.flush()

                sites_db[site.nome] = site_db

            for site in sites.values():

                if site.pai:

                    site_db = sites_db[site.nome]

                    pai_db = sites_db[site.pai.nome]

                    site_db.parent_id = pai_db.id

            total_clientes = 0

            for site in sites.values():

                site_db = sites_db.get(site.nome)

                if not site_db:

                    continue

                for cliente in site.clientes:

                    cliente_db = ClienteModel(
                        nome=cliente.nome,
                        receita=cliente.receita,
                        num_assinatura=cliente.num_assinatura,
                        site_id=site_db.id
                    )

                    session.add(cliente_db)

                    total_clientes += 1

        registrar_log_sistema(
            "sincronizar_banco",
            status="sucesso",
            detalhes={
                "sites": len(sites_db),
                "clientes": total_clientes
            }
        )

    finally:

        session.close()


def salvar_sites(sites):

    sincronizar_banco(sites)


def salvar_clientes(sites):

    sincronizar_banco(sites)
