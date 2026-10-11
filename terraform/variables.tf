variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
}

variable "network_name" {
  description = "Name of the VPC network"
  type        = string
}

variable "project_name" {
  description = "Base name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}


variable "subnet_cidr" {
  description = "CIDR range for the main subnet"
  type        = string
}



variable "pods_cidr" {
  description = "Secondary CIDR range for GKE Pods"
  type        = string
}

variable "services_cidr" {
  description = "Secondary CIDR range for GKE Services"
  type        = string
}

variable "zone" {
  description = "GCP zone for the GKE cluster"
  type        = string
}

variable "master_ipv4_cidr" {
  description = "CIDR range for the GKE control plane"
  type        = string
}


variable "gke_machine_type" {
  description = "Machine type for GKE worker nodes"
  type        = string
}

variable "gke_disk_size_gb" {
  description = "Disk size for GKE worker nodes"
  type        = number
}

variable "gke_min_nodes" {
  description = "Minimum number of nodes in the GKE node pool"
  type        = number
}

variable "gke_max_nodes" {
  description = "Maximum number of nodes in the GKE node pool"
  type        = number
}

variable "private_service_cidr_prefix_length" {
  description = "Prefix length for the private service access IP range"
  type        = number
}


variable "db_version" {
  description = "PostgreSQL version for Cloud SQL"
  type        = string
}

variable "db_tier" {
  description = "Machine tier for Cloud SQL"
  type        = string
}

variable "db_disk_size_gb" {
  description = "Disk size for Cloud SQL"
  type        = number
}


variable "db_name" {
  description = "Name of the CloudForge database"
  type        = string
}


variable "db_user" {
  description = "Database user for CloudForge"
  type        = string
}