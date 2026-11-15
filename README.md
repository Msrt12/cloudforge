
# CloudForge
![alt text](image.png)
**Self-Service Kubernetes Deployment Platform | GCP · GKE · Terraform · FastAPI · Jenkins**

CloudForge is a Kubernetes-based internal developer platform for managing containerized application deployments across development, staging, and production environments.

The platform provides REST APIs for deployment, environment promotion, rollback, autoscaling, and Kubernetes event retrieval.

## Technology Stack

| Component | Technology |
|---|---|
| Cloud Infrastructure | Google Cloud Platform |
| Infrastructure as Code | Terraform |
| Container Orchestration | GKE, Kubernetes |
| Backend | Python, FastAPI, SQLAlchemy |
| Database | Cloud SQL PostgreSQL |
| CI/CD | GitHub Actions, Jenkins |
| Container Builds | Docker, BuildKit (in progress) |
| Container Registry | Google Artifact Registry |
| Deployment | Helm |
| Authentication | Workload Identity Federation, GKE Workload Identity |
| Authorization | Google Cloud IAM, Kubernetes RBAC |
| Secrets | Google Secret Manager, Secrets Store CSI |
| Networking | VPC, Cloud NAT, Cloud Router, Private Service Access |
| Monitoring (planned) | Prometheus, Grafana |

## Infrastructure

Infrastructure is provisioned using Terraform in the GCP `europe-west3` region.

### Networking
- Custom VPC and subnet.
- Secondary IP ranges for GKE Pods and Services.
- Cloud Router and Cloud NAT for outbound connectivity.
- Private Service Access for Cloud SQL connectivity.
- Private GKE worker nodes.

### GKE
- Private-node GKE cluster.
- Autoscaling node pool.
- Kubernetes namespaces: `platform`, `jenkins`, `dev`, `staging`, `prod`.
- Helm-managed platform components.
- Namespace-scoped Kubernetes RBAC.

### Data and Secrets
- Cloud SQL PostgreSQL with private IP connectivity.
- Secret Manager for database credentials.
- Secrets Store CSI integration.
- Workload Identity for workload-to-GCP authentication.

## Kubernetes Architecture

```text
GCP Project
│
├── Terraform
│   ├── VPC / Subnets
│   ├── Cloud Router / NAT
│   ├── GKE
│   ├── Cloud SQL
│   ├── Artifact Registry
│   └── IAM / Service Accounts
│
└── GKE Cluster
    │
    ├── platform
    │   └── CloudForge Backend (FastAPI)
    │
    ├── jenkins
    │   ├── Jenkins Controller
    │   └── Ephemeral Kubernetes Agents
    │
    ├── dev
    │   └── Application Deployments
    │
    ├── staging
    │   └── Application Deployments
    │
    └── prod
        └── Application Deployments
```

## Backend API

FastAPI communicates with the Kubernetes API using an in-cluster ServiceAccount.

### Application Management
- Register applications with Git repository metadata.
- Create environment records in PostgreSQL.
- Maintain deployment versions and environment state.

### Deployment
- Create Kubernetes Deployments and Services.
- Deploy application images into the `dev` namespace.
- Configure application replicas and container ports.

### Promotion
- Promote applications from `dev` to `staging`.
- Promote applications from `staging` to `prod`.
- Update environment version metadata.

### Rollback
- Track current and previous application versions.
- Restore the previous container image through the Kubernetes API.
- Update deployment state in PostgreSQL.

### Autoscaling
- Create and update Horizontal Pod Autoscalers.
- Configure minimum and maximum replicas.
- Configure target CPU utilization.

### Kubernetes Events
- Retrieve Deployment and Pod events.
- Filter events by application resources.
- Return event information through REST endpoints.

## Kubernetes RBAC

The CloudForge backend runs using the `cloudforge-backend` ServiceAccount in the `platform` namespace.

Namespace-scoped RoleBindings grant deployment permissions in `dev`, `staging`, and `prod`.

Managed resources include:
- Deployments
- Services
- HorizontalPodAutoscalers

## CI/CD

### Platform Delivery — GitHub Actions

GitHub Actions uses Workload Identity Federation to authenticate to Google Cloud without static service account keys.

Pipeline operations:
1. Authenticate to GCP using OIDC.
2. Build the CloudForge backend Docker image.
3. Push the image to Artifact Registry.
4. Deploy the backend using Helm.
5. Deploy or upgrade Jenkins using Helm.

### Application CI — Jenkins

Jenkins runs as a Helm release in the `jenkins` namespace.

Configuration:
- Jenkins Configuration as Code (JCasC).
- Job DSL for automated Pipeline Job creation.
- Kubernetes Plugin for ephemeral Agent Pods.
- Parameterized Pipeline Jobs.
- Persistent Jenkins Controller storage.
- Controller configured with zero build executors.

Implemented pipeline stages:
1. Git repository checkout.
2. Dockerfile validation.

BuildKit integration is in progress.

### Target Application Pipeline

```text
CloudForge API
      │
      ▼
Jenkins Controller
      │
      ▼
Ephemeral Kubernetes Agent
      │
      ├── Git Checkout
      ├── Dockerfile Validation
      ├── BuildKit Image Build
      ├── Trivy Vulnerability Scan
      └── Push to Artifact Registry
                     │
                     ▼
              CloudForge API
                     │
                     ▼
               GKE Deployment
```

The end-to-end API-triggered pipeline is not yet implemented.

## Security

- Workload Identity Federation for GitHub Actions authentication.
- GKE Workload Identity for backend access to GCP services.
- IAM roles scoped to individual service accounts.
- Kubernetes RBAC for application deployment operations.
- Secret Manager for sensitive configuration.
- Private GKE nodes.
- Private IP connectivity to Cloud SQL.

## Planned Monitoring

**Prometheus**
- Kubernetes node and Pod metrics.
- CPU and memory utilization.
- Application metrics.
- Jenkins metrics.

**Grafana**
- GKE infrastructure dashboards.
- Application health dashboards.
- Jenkins pipeline monitoring.
- Resource utilization by namespace.

**Alerting**
- Pod failures and restart thresholds.
- High CPU and memory utilization.
- Application unavailability.
- Deployment failures.

## Roadmap

- [x] Terraform-based GCP provisioning
- [x] Private-node GKE cluster
- [x] Cloud SQL PostgreSQL integration
- [x] Secret Manager integration
- [x] Kubernetes RBAC
- [x] FastAPI deployment endpoints
- [x] Environment promotion
- [x] Rollback
- [x] HPA configuration
- [x] Kubernetes event retrieval
- [x] GitHub Actions platform deployment
- [x] Jenkins Helm deployment
- [x] JCasC and Job DSL configuration
- [x] Dynamic Kubernetes Agents
- [x] Git checkout and Dockerfile validation
- [ ] Complete BuildKit integration
- [ ] Trivy image vulnerability scanning
- [ ] Automated image push to Artifact Registry
- [ ] Jenkins job triggering from FastAPI
- [ ] Pipeline execution status tracking
- [ ] End-to-end application CI/CD
- [ ] Prometheus deployment
- [ ] Grafana dashboards
- [ ] Monitoring and alerting

## Repository Structure

```text
cloudforge/
├── .github/
│   └── workflows/
├── backend/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── demo-apps/
│   └── payment-service/
├── helm/
│   ├── cloudforge/
│   └── jenkins/
│       └── values.yaml
├── terraform/
├── Dockerfile
└── README.md
```

## Author

**Mykola Dmytrash**

[Portfolio](https://msrt12.github.io/) | [GitHub](https://github.com/Msrt12)
