
from pathlib import Path

import docker

def is_dockerfile_buildable(path: Path) -> bool:
    """
    Tests if a Dockerfile in a given path is buildable by attempting to build it.
    
    Args:
        path: The path to the directory containing the Dockerfile.
        
    Returns:
        True if the build succeeds, False otherwise.
    """
    try:
        client = docker.from_env()
        print(f"Attempting to build Dockerfile at: {path}")
        
        # We perform a build, but use the 'nocache=True' and 'rm=True'
        # flags to ensure it's a clean test and we don't pollute the local
        # image cache with failed builds.
        response = client.images.build(
            path=str(path.parent),
            dockerfile=str(path), 
            tag='test-build', 
            nocache=True, 
            rm=True
        )
        
        # The build method returns a tuple (image, logs) on success
        # The logs are an iterator, so we consume them to finish the process
        image, build_log = response
        for chunk in build_log:
            if 'stream' in chunk:
                print(chunk['stream'], end='')
        
        print("\nBuild successful!")
        client.images.remove('test-build') # Clean up the test image
        return True
    
    except docker.errors.BuildError as e:
        print(f"\nBuild failed: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return False