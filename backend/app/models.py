from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(
        String,
        unique=True,
        nullable=False
    )

    repository = Column(
        String,
        nullable=False
    )

    environments = relationship(
        "Environment",
        back_populates="application",
        cascade="all, delete-orphan"
    )


class Environment(Base):
    __tablename__ = "environments"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    current_version = Column(
        String,
        nullable=True
    )

    previous_version = Column(
        String,
        nullable=True
    )


    status = Column(
        String,
        default="Not deployed"
    )

    replicas = Column(
        Integer,
        default=1
    )

    application = relationship(
        "Application",
        back_populates="environments"
    )


    min_replicas = Column(
    Integer,
    nullable=False,
    default=1
    )

    max_replicas = Column(
    Integer,
    nullable=False,
    default=3
    )   

    target_cpu = Column(
    Integer,
    nullable=False,
    default=60
    )