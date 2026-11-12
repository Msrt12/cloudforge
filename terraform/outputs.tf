output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}



output "github_service_account" {
  value = google_service_account.github.email
}


output "github_service_account_helm" {
  value = google_service_account.githubhelm.email
}