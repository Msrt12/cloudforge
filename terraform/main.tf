locals {
  name_prefix = "${var.project_name}-${var.environment}"

  pods_range_name     = "${local.name_prefix}-pods"
  services_range_name = "${local.name_prefix}-services"


  required_apis = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com"
  ])
}

resource "google_project_service" "required_apis" {
  for_each = local.required_apis

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

resource "google_compute_network" "cloudforge_vpc" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "cloudforge_subnet" {
  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.cloudforge_vpc.id

  secondary_ip_range {
    range_name    = local.pods_range_name
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = local.services_range_name
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "cloudforge_router" {
  name    = "${local.name_prefix}-router"
  region  = var.region
  network = google_compute_network.cloudforge_vpc.id
}

resource "google_compute_router_nat" "cloudforge_nat" {
  name   = "${local.name_prefix}-nat"
  router = google_compute_router.cloudforge_router.name
  region = var.region

  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}


resource "google_container_cluster" "cloudforge_cluster" {
  name     = "${local.name_prefix}-gke"
  location = var.zone

  network    = google_compute_network.cloudforge_vpc.id
  subnetwork = google_compute_subnetwork.cloudforge_subnet.id

  networking_mode = "VPC_NATIVE"
  deletion_protection = false
  ip_allocation_policy {
    cluster_secondary_range_name  = local.pods_range_name
    services_secondary_range_name = local.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false

    master_ipv4_cidr_block = var.master_ipv4_cidr
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  secret_manager_config {
    enabled = true
  }

  remove_default_node_pool = true
  initial_node_count       = 1


  depends_on = [
    google_project_service.required_apis
  ]

}


resource "google_container_node_pool" "cloudforge_node_pool" {
  name     = "${local.name_prefix}-node-pool"
  cluster  = google_container_cluster.cloudforge_cluster.name
  location = var.zone

  autoscaling {
    min_node_count = var.gke_min_nodes
    max_node_count = var.gke_max_nodes
  }

  node_config {
    machine_type    = var.gke_machine_type
    disk_size_gb    = var.gke_disk_size_gb
    service_account = google_service_account.gke_nodes.email


    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}


resource "google_service_account" "gke_nodes" {
  account_id   = "${local.name_prefix}-gke-sa"
  display_name = "${local.name_prefix} GKE Node Service Account"
}

resource "google_project_iam_member" "gke_node_role" {
  project = var.project_id
  role    = "roles/container.defaultNodeServiceAccount"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "gke_artifact_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_compute_global_address" "private_service_range" {
  name          = "${local.name_prefix}-private-service-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_cidr_prefix_length
  network       = google_compute_network.cloudforge_vpc.id
}

resource "google_service_networking_connection" "private_service_connection" {
  network = google_compute_network.cloudforge_vpc.id
  service = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [
    google_compute_global_address.private_service_range.name
  ]
  depends_on = [
    google_project_service.required_apis
  ]
}


resource "google_sql_database_instance" "cloudforge_postgres" {
  name             = "${local.name_prefix}-postgres"
  database_version = var.db_version
  region           = var.region

  settings {
    tier      = var.db_tier
    edition   = "ENTERPRISE"
    disk_size = var.db_disk_size_gb

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.cloudforge_vpc.id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false

  depends_on = [
    google_service_networking_connection.private_service_connection
  ]
}


resource "google_sql_database" "cloudforge_database" {
  name     = var.db_name
  instance = google_sql_database_instance.cloudforge_postgres.name
}


resource "random_password" "db_password" {
  length  = 24
  special = true
}


resource "google_sql_user" "cloudforge_user" {
  name     = var.db_user
  instance = google_sql_database_instance.cloudforge_postgres.name
  password = random_password.db_password.result
}


resource "google_secret_manager_secret" "db_password" {
  secret_id = "${local.name_prefix}-db-password"

  replication {
    auto {}
  }
  depends_on = [
    google_project_service.required_apis
  ]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}


resource "google_secret_manager_secret" "db_user" {
  secret_id = "${local.name_prefix}-db-user"

  replication {
    auto {}
  }
  depends_on = [
    google_project_service.required_apis
  ]
}

resource "google_secret_manager_secret_version" "db_user" {
  secret      = google_secret_manager_secret.db_user.id
  secret_data = var.db_user
}

resource "google_secret_manager_secret" "db_name" {
  secret_id = "${local.name_prefix}-db-name"

  replication {
    auto {}
  }
  depends_on = [
    google_project_service.required_apis
  ]
}

resource "google_secret_manager_secret_version" "db_name" {
  secret      = google_secret_manager_secret.db_name.id
  secret_data = var.db_name
}


resource "google_service_account" "cloudforge_backend" {
  account_id   = "${local.name_prefix}-backend-sa"
  display_name = "CloudForge Backend Service Account"
}

resource "google_project_iam_member" "cloudforge_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloudforge_backend.email}"
}

resource "google_project_iam_member" "backend_secret_accessor" {
  project = var.project_id

  role = "roles/secretmanager.secretAccessor"

  member = "serviceAccount:${google_service_account.cloudforge_backend.email}"
}

resource "google_service_account_iam_member" "cloudforge_workload_identity" {
  service_account_id = google_service_account.cloudforge_backend.name

  role = "roles/iam.workloadIdentityUser"

  member = "serviceAccount:${var.project_id}.svc.id.goog[platform/cloudforge-backend]"
}

resource "google_service_account" "github" {
  account_id = "githubsa"
  project    = var.project_id
}

resource "google_service_account" "githubhelm" {
  account_id = "githubhelmsa"
  project    = var.project_id
}


resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  project                   = var.project_id
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  project                            = var.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.environment" = "assertion.environment"

  }

  attribute_condition = "assertion.repository == '${var.user_name_git}/cloudforge'" 

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.github.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.user_name_git}/cloudforge"
}

resource "google_artifact_registry_repository_iam_member" "github" {
  project    = var.project_id
  location   = "europe-west3"
  repository = "cloudforge"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github.email}"
}




resource "google_service_account_iam_member" "githubhelm" {
  service_account_id = google_service_account.githubhelm.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/production"
}


resource "google_project_iam_member" "githubhelm" {
  project = "${var.project_id}"
  role    = "roles/container.clusterViewer"
  member  = "serviceAccount:${google_service_account.githubhelm.email}"
}


resource "google_project_iam_member" "githubhelm_gke" {
  project = var.project_id
  role    = "roles/container.admin"
  member  = "serviceAccount:${google_service_account.githubhelm.email}"
}
