from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import ForeignKey

from app.database.database import Base


class ClienteModel(Base):

    __tablename__ = "clientes"

    id = Column(
        Integer,
        primary_key=True
    )

    nome = Column(String)

    receita = Column(Float)

    num_assinatura = Column(String)

    site_id = Column(
        Integer,
        ForeignKey("sites.id")
    )