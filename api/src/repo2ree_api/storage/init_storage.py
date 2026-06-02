from repo2ree_api.settings import service_settings


def create_upload_staging_if_not_exists():
    service_settings.UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)


def create_review_storage_if_not_exists():
    service_settings.REVIEWS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
