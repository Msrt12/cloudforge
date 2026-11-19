import requests
import os
from pathlib import Path

JENKINS_URL = os.getenv(
    "JENKINS_URL",
    "http://jenkins.jenkins.svc.cluster.local:8080"
)

JENKINS_USERNAME = os.getenv("JENKINS_USERNAME", "admin")

JENKINS_API_TOKEN = Path(
    "/var/secrets/jenkins-api-token"
).read_text().strip()


def trigger_build(
    application_id: int,
    repository_url: str,
    build_id: int
):
    response = requests.post(
        f"{JENKINS_URL}/job/cloudforge-build/buildWithParameters",
        auth=(JENKINS_USERNAME, JENKINS_API_TOKEN),
        data={
            "APPLICATION_ID": application_id,
            "REPOSITORY_URL": repository_url,
            "CLOUDFORGE_BUILD_ID": build_id
        },
        timeout=15
    )

    response.raise_for_status()

    return response.headers.get("Location")
