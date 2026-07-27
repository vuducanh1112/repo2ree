from repo2ree_api.settings import service_settings


def create_upload_staging_if_not_exists() -> None:
    service_settings.UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)
