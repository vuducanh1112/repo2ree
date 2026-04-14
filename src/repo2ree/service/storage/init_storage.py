from repo2ree.service.api.settings import service_settings


def create_workspace_storage_if_not_exists():
    service_settings.WORKSPACE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
