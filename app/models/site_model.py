from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from app.database.database import Base


class SiteModel(Base):

    __tablename__ = "sites"

    id = Column(
        Integer,
        primary_key=True
    )

    nome = Column(
        String,
        unique=True
    )

    tipo = Column(String)

    parent_id = Column(
        Integer,
        ForeignKey("sites.id"),
        nullable=True
    )

    filhos = relationship(
        "SiteModel"
    )