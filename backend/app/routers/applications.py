from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db


router = APIRouter(
    prefix="/applications",
    tags=["Applications"]
)


@router.post("/", response_model=schemas.ApplicationResponse)
def create_application(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db)
):
    existing_application = (
        db.query(models.Application)
        .filter(models.Application.name == application.name)
        .first()
    )

    if existing_application:
        raise HTTPException(
            status_code=400,
            detail="Application already exists"
        )

    new_application = models.Application(
        name=application.name,
        repository=application.repository
    )

    db.add(new_application)
    db.flush()

    environments = [
        models.Environment(
            name="dev",
            current_version=None,
            status="not_deployed",
            application_id=new_application.id
        ),
        models.Environment(
            name="staging",
            current_version=None,
            status="not_deployed",
            application_id=new_application.id
        ),
        models.Environment(
            name="prod",
            current_version=None,
            status="not_deployed",
            application_id=new_application.id
        )
    ]

    db.add_all(environments)

    db.commit()
    db.refresh(new_application)

    return new_application

@router.post("/{application_id}/deploy")
def deploy_application(
    application_id: int,
    deploy: schemas.DeployRequest,
    db: Session = Depends(get_db)
):
    # Знаходимо application по ID
    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )

    # Якщо application не існує
    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    # Знаходимо потрібне environment:
    # dev / staging / prod
    environment = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application_id,
            models.Environment.name == deploy.environment
        )
        .first()
    )

    # Якщо environment не існує
    if environment is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    # Стару версію запам'ятовуємо для можливого rollback
    environment.previous_version = environment.current_version

    # Встановлюємо нову версію
    environment.current_version = deploy.version

    # Змінюємо статус
    environment.status = "deployed"

    # Записуємо зміни в БД
    db.commit()

    # Оновлюємо Python-об'єкт даними з БД
    db.refresh(environment)

    # Повертаємо результат
    return {
        "message": "Deployment completed",
        "application": application.name,
        "environment": environment.name,
        "version": environment.current_version,
        "previous_version": environment.previous_version,
        "status": environment.status
    }


@router.post("/{application_id}/promote")
def promote_application(
    application_id: int,
    promote: schemas.PromoteRequest,
    db: Session = Depends(get_db)
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    if promote.target_environment == "staging":
        source_name = "dev"

    elif promote.target_environment == "prod":
        source_name = "staging"

    else:
        raise HTTPException(
            status_code=400,
            detail="Target environment must be staging or prod"
        )

    source_environment = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application_id,
            models.Environment.name == source_name
        )
        .first()
    )

    target_environment = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application_id,
            models.Environment.name == promote.target_environment
        )
        .first()
    )

    if source_environment is None or target_environment is None:
        raise HTTPException(
            status_code=404,
            detail="Required environment not found"
        )

    if source_environment.current_version is None:
        raise HTTPException(
            status_code=400,
            detail=f"Nothing is deployed in {source_name.upper()}"
        )

    target_environment.previous_version = target_environment.current_version
    target_environment.current_version = source_environment.current_version
    target_environment.status = "deployed"
    db.commit()
    db.refresh(target_environment)

    return {
        "message": "Application promoted",
        "application": application.name,
        "from": source_name,
        "to": promote.target_environment,
        "version": target_environment.current_version,
        "status": target_environment.status
    }

@router.post("/{application_id}/rollback")
def rollback_application(
    application_id: int,
    rollback: schemas.RollbackRequest,
    db: Session = Depends(get_db)
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    environment = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application_id,
            models.Environment.name == rollback.environment
        )
        .first()
    )

    if environment is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    if environment.previous_version is None:
        raise HTTPException(
            status_code=400,
            detail="No previous version available for rollback"
        )

    old_current_version = environment.current_version

    environment.current_version = environment.previous_version
    environment.previous_version = old_current_version
    environment.status = "deployed"

    db.commit()
    db.refresh(environment)

    return {
        "message": "Rollback completed",
        "application": application.name,
        "environment": environment.name,
        "version": environment.current_version,
        "previous_version": environment.previous_version,
        "status": environment.status
    }


@router.patch("/{application_id}/scaling")
def update_scaling(
    application_id: int,
    scaling: schemas.ScalingRequest,
    db: Session = Depends(get_db)
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    environment = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application_id,
            models.Environment.name == scaling.environment
        )
        .first()
    )

    if environment is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    if scaling.min_replicas < 1:
        raise HTTPException(
            status_code=400,
            detail="min_replicas must be at least 1"
        )

    if scaling.max_replicas < scaling.min_replicas:
        raise HTTPException(
            status_code=400,
            detail="max_replicas must be greater than or equal to min_replicas"
        )

    if scaling.target_cpu < 1 or scaling.target_cpu > 100:
        raise HTTPException(
            status_code=400,
            detail="target_cpu must be between 1 and 100"
        )

    environment.min_replicas = scaling.min_replicas
    environment.max_replicas = scaling.max_replicas
    environment.target_cpu = scaling.target_cpu

    db.commit()
    db.refresh(environment)

    return {
        "message": "Scaling configuration updated",
        "application": application.name,
        "environment": environment.name,
        "min_replicas": environment.min_replicas,
        "max_replicas": environment.max_replicas,
        "target_cpu": environment.target_cpu
    }