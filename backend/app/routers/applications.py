from time import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from ..kubernetes_client import apps_v1, core_v1, autoscaling_v2


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
            models.Environment.name == deploy.environment
        )
        .first()
    )

    if environment is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    if deploy.environment != "dev":
        raise HTTPException(
            status_code=400,
            detail="Direct deployment is currently allowed only to dev"
        )

    namespace = "dev"
    deployment_name = application.name

    image = f"{application.repository}:{deploy.version}"

    labels = {
        "app": application.name
    }

    
    container = client.V1Container(
        name=application.name,
        image=image,
        ports=[
            client.V1ContainerPort(
                container_port=8000
            )
        ],

        startup_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=5,
            failure_threshold=12,
            timeout_seconds=2
        ),

        readiness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=5,
            failure_threshold=3,
            timeout_seconds=2
        ),

        liveness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=10,
            failure_threshold=3,
            timeout_seconds=2
        )
    )


    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels=labels
        ),
        spec=client.V1PodSpec(
            containers=[container]
        )
    )

    deployment_spec = client.V1DeploymentSpec(
        replicas=environment.min_replicas,
        selector=client.V1LabelSelector(
            match_labels=labels
        ),
        template=pod_template
    )

    deployment_body = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=deployment_name
        ),
        spec=deployment_spec
    )

    try:
        apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        apps_v1.replace_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=deployment_body
        )

    except ApiException as error:
        if error.status == 404:
            apps_v1.create_namespaced_deployment(
                namespace=namespace,
                body=deployment_body
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Kubernetes deployment error: {error.reason}"
            )

    service_body = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=deployment_name
        ),
        spec=client.V1ServiceSpec(
            selector=labels,
            ports=[
                client.V1ServicePort(
                    port=80,
                    target_port=8000
                )
            ]
        )
    )

    try:
        core_v1.read_namespaced_service(
            name=deployment_name,
            namespace=namespace
        )

    except ApiException as error:
        if error.status == 404:
            core_v1.create_namespaced_service(
                namespace=namespace,
                body=service_body
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Kubernetes service error: {error.reason}"
            )

    environment.previous_version = environment.current_version
    environment.current_version = deploy.version
    environment.status = "deployed"

    db.commit()
    db.refresh(environment)

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
            detail=f"Nothing is deployed in {source_name}"
        )





    namespace = promote.target_environment
    deployment_name = application.name
    version = source_environment.current_version
    image = f"{application.repository}:{version}"

    labels = {"app": application.name}




    container = client.V1Container(
        name=application.name,
        image=image,
        ports=[
            client.V1ContainerPort(container_port=8000)
        ],

        startup_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=5,
            failure_threshold=12,
            timeout_seconds=2
        ),

        readiness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=5,
            failure_threshold=3,
            timeout_seconds=2
        ),

        liveness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/health",
                port=8000
            ),
            period_seconds=10,
            failure_threshold=3,
            timeout_seconds=2
        )
    )

    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=labels),
        spec=client.V1PodSpec(
            containers=[container]
        )
    )

    deployment_body = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=client.V1DeploymentSpec(
            replicas=target_environment.min_replicas,
            selector=client.V1LabelSelector(
                match_labels=labels
            ),
            template=pod_template
        )
    )

    try:
        existing = apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        deployment_body.metadata.resource_version = (
            existing.metadata.resource_version
        )

        apps_v1.replace_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=deployment_body
        )

    except ApiException as error:
        if error.status == 404:
            try:
                apps_v1.create_namespaced_deployment(
                    namespace=namespace,
                    body=deployment_body
                )
            except ApiException as create_error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Kubernetes deployment error: {create_error.reason}"
                )
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Kubernetes deployment error: {error.reason}"
            )

    service_body = client.V1Service(
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=client.V1ServiceSpec(
            selector=labels,
            ports=[
                client.V1ServicePort(
                    port=80,
                    target_port=8000
                )
            ]
        )
    )

    try:
        core_v1.read_namespaced_service(
            name=deployment_name,
            namespace=namespace
        )

    except ApiException as error:
        if error.status == 404:
            try:
                core_v1.create_namespaced_service(
                    namespace=namespace,
                    body=service_body
                )
            except ApiException as create_error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Kubernetes service error: {create_error.reason}"
                )
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Kubernetes service error: {error.reason}"
            )

    target_environment.previous_version = target_environment.current_version
    target_environment.current_version = version
    target_environment.status = "deploying"

    db.commit()
    db.refresh(target_environment)

    return {
        "message": "Promotion submitted to Kubernetes",
        "application": application.name,
        "from": source_name,
        "to": namespace,
        "version": version,
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

    namespace = environment.name
    deployment_name = application.name

    old_current_version = environment.current_version
    rollback_version = environment.previous_version

    image = f"{application.repository}:{rollback_version}"

    try:
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

    except ApiException as error:
        if error.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Kubernetes Deployment not found"
            )

        raise HTTPException(
            status_code=502,
            detail=f"Kubernetes error: {error.reason}"
        )

    # Змінюємо image у Deployment
    containers = deployment.spec.template.spec.containers

    container = next(
        (c for c in containers if c.name == application.name),
        None
    )

    if container is None:
        raise HTTPException(
            status_code=500,
            detail="Application container not found in Deployment"
        )

    container.image = image

    try:
        apps_v1.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": container.name,
                                    "image": image
                                }
                            ]
                        }
                    }
                }
            }
        )

    except ApiException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Kubernetes rollback error: {error.reason}"
        )

    environment.current_version = rollback_version
    environment.previous_version = old_current_version
    environment.status = "deploying"

    db.commit()
    db.refresh(environment)

    return {
        "message": "Rollback submitted to Kubernetes",
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
            detail="max_replicas must be >= min_replicas"
        )

    if not 1 <= scaling.target_cpu <= 100:
        raise HTTPException(
            status_code=400,
            detail="target_cpu must be between 1 and 100"
        )

    if scaling.environment != "dev":
        raise HTTPException(
            status_code=400,
            detail="Scaling is currently supported only in dev"
        )

    namespace = "dev"
    deployment_name = application.name

    try:
        apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

    except ApiException as error:
        if error.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Deployment not found. Deploy application first."
            )

        raise HTTPException(
            status_code=502,
            detail=f"Kubernetes Deployment error: {error.reason}"
        )

    hpa_body = client.V2HorizontalPodAutoscaler(
        metadata=client.V1ObjectMeta(
            name=deployment_name
        ),
        spec=client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=client.V2CrossVersionObjectReference(
                api_version="apps/v1",
                kind="Deployment",
                name=deployment_name
            ),
            min_replicas=scaling.min_replicas,
            max_replicas=scaling.max_replicas,
            metrics=[
                client.V2MetricSpec(
                    type="Resource",
                    resource=client.V2ResourceMetricSource(
                        name="cpu",
                        target=client.V2MetricTarget(
                            type="Utilization",
                            average_utilization=scaling.target_cpu
                        )
                    )
                )
            ]
        )
    )

    try:
        autoscaling_v2.read_namespaced_horizontal_pod_autoscaler(
            name=deployment_name,
            namespace=namespace
        )

    except ApiException as error:
        if error.status != 404:
            raise HTTPException(
                status_code=502,
                detail=f"Kubernetes HPA read error: {error.reason}"
            )
        try:
            autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                namespace=namespace,
                body=hpa_body
            )

        except ApiException as create_error:
            raise HTTPException(
                status_code=502,
                detail=f"Kubernetes HPA create error: {create_error.reason}"
            )

    else:
        try:
            autoscaling_v2.patch_namespaced_horizontal_pod_autoscaler(
                name=deployment_name,
                namespace=namespace,
                body=hpa_body
            )

        except ApiException as patch_error:
            raise HTTPException(
                status_code=502,
                detail=f"Kubernetes HPA patch error: {patch_error.reason}"
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


@router.get("/{application_id}/status")
def get_application_status(
    application_id: int,
    environment: str,
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

    env = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application.id,
            models.Environment.name == environment
        )
        .first()
    )

    if env is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    namespace = environment
    deployment_name = application.name

    try:
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        pods = core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={deployment_name}"
        )

    except ApiException as error:
        if error.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Deployment not found in Kubernetes"
            )

        if error.status == 403:
            raise HTTPException(
                status_code=502,
                detail="CloudForge lacks Kubernetes read permissions"
            )

        raise HTTPException(
            status_code=502,
            detail="Failed to communicate with Kubernetes API"
        )

    desired_replicas = deployment.spec.replicas or 0
    ready_replicas = deployment.status.ready_replicas or 0
    available_replicas = deployment.status.available_replicas or 0
    updated_replicas = deployment.status.updated_replicas or 0

    pod_details = []

    for pod in pods.items:
        container_statuses = (
            pod.status.container_statuses or []
        )

        restarts = sum(
            container.restart_count or 0
            for container in container_statuses
        )

        pod_ready = any(
            condition.type == "Ready"
            and condition.status == "True"
            for condition in (pod.status.conditions or [])
        )

        containers_ready = (
            len(container_statuses) > 0
            and all(
                container.ready
                for container in container_statuses
            )
        )

                
        pod_details.append({
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "ready": pod_ready and containers_ready,
            "restarts": restarts,
            "containers": [
                {
                    "name": container.name,
                    "ready": container.ready,
                    "restart_count": container.restart_count
                }
                for container in container_statuses
            ],
            "probes": [
                {
                    "container": container.name,
                    "startup": {
                        "path": container.startup_probe.http_get.path,
                        "port": container.startup_probe.http_get.port
                    } if container.startup_probe and container.startup_probe.http_get else None,
                    "readiness": {
                        "path": container.readiness_probe.http_get.path,
                        "port": container.readiness_probe.http_get.port
                    } if container.readiness_probe and container.readiness_probe.http_get else None,
                    "liveness": {
                        "path": container.liveness_probe.http_get.path,
                        "port": container.liveness_probe.http_get.port
                    } if container.liveness_probe and container.liveness_probe.http_get else None
                }
                for container in pod.spec.containers
            ]
        })

    if desired_replicas == 0:
        status = "scaled_down"

    elif (
        ready_replicas == desired_replicas
        and available_replicas == desired_replicas
        and updated_replicas == desired_replicas
    ):
        status = "healthy"

    elif ready_replicas > 0:
        status = "degraded"

    else:
        status = "unhealthy"

    return {
        "application_id": application.id,
        "application": application.name,
        "environment": environment,
        "current_version": env.current_version,
        "previous_version": env.previous_version,
        "status": status,
        "deployment": {
            "desired_replicas": desired_replicas,
            "ready_replicas": ready_replicas,
            "available_replicas": available_replicas,
            "updated_replicas": updated_replicas
        },
        "pods": pod_details
    }




def format_k8s_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.isoformat()


@router.get("/{application_id}/events")
def get_application_events(
    application_id: int,
    environment: str,
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

    env = (
        db.query(models.Environment)
        .filter(
            models.Environment.application_id == application.id,
            models.Environment.name == environment
        )
        .first()
    )

    if env is None:
        raise HTTPException(
            status_code=404,
            detail="Environment not found"
        )

    namespace = env.name

    try:
        deployment = apps_v1.read_namespaced_deployment(
            name=application.name,
            namespace=namespace
        )

        pods = core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={application.name}"
        )

        events_response = core_v1.list_namespaced_event(
            namespace=namespace
        )

    except ApiException as error:
        if error.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Deployment or namespace not found"
            )

        if error.status == 403:
            raise HTTPException(
                status_code=502,
                detail="CloudForge lacks Kubernetes read permissions"
            )

        raise HTTPException(
            status_code=502,
            detail="Failed to communicate with Kubernetes API"
        )

    pod_uids = {
        pod.metadata.uid
        for pod in pods.items
        if pod.metadata and pod.metadata.uid
    }

    pod_names = {
        pod.metadata.name
        for pod in pods.items
        if pod.metadata and pod.metadata.name
    }

    deployment_uid = deployment.metadata.uid

    application_events = []

    for event in events_response.items:
        involved = event.involved_object

        if involved is None:
            continue

        belongs_to_application = (
            (
                involved.kind == "Pod"
                and involved.uid in pod_uids
            )
            or (
                involved.kind == "Pod"
                and not involved.uid
                and involved.name in pod_names
            )
            or (
                involved.kind == "Deployment"
                and involved.uid == deployment_uid
            )
        )

        if not belongs_to_application:
            continue

        event_time = (
            event.last_timestamp
            or event.event_time
            or event.first_timestamp
            or event.metadata.creation_timestamp
        )

        application_events.append({
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
            "object": {
                "kind": involved.kind,
                "name": involved.name
            },
            "count": event.count or 1,
            "timestamp": format_k8s_datetime(event_time)
        })

    application_events.sort(
        key=lambda event: event["timestamp"] or "",
        reverse=True
    )

    return {
        "application_id": application.id,
        "application": application.name,
        "environment": namespace,
        "total_events": len(application_events),
        "events": application_events
    }
