from sqlalchemy import Column, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from sqlalchemy import DateTime
from .database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    builds = relationship("Build", back_populates="application")
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


class Build(Base):
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False
    )

    jenkins_queue_id = Column(Integer, nullable=True)
    jenkins_build_number = Column(Integer, nullable=True)

    status = Column(String, default="QUEUED", nullable=False)

    image_uri = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    finished_at = Column(DateTime(timezone=True), nullable=True)

    application = relationship("Application", back_populates="builds")
