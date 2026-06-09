import io
import tarfile

import docker


def extract_file_from_image(image_name: str, file_path: str, destination_path: str) -> bool:
    """
    Extract a specific file from a Docker image.

    Args:
        image_name (str): The name of the Docker image.
        file_path (str): The path of the file inside the Docker image.
        destination_path (str): The local path where the file should be saved.

    Returns:
        bool: True if the file was successfully extracted, False otherwise.
    """
    client = docker.from_env()

    try:
        container = client.containers.create(
            detach=True,
            image=image_name,
        )

        bits, stat = container.get_archive(file_path)

        file_obj = io.BytesIO()
        for chunk in bits:
            file_obj.write(chunk)
        file_obj.seek(0)

        with tarfile.open(fileobj=file_obj) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        raise FileNotFoundError(f"Could not extract {member.name} from archive.")
                    with open(destination_path, "wb") as f:
                        f.write(extracted.read())
                    break

        # Clean up
        container.remove()
        return True

    except docker.errors.NotFound:
        print(f"File {file_path} not found in image {image_name}.")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
