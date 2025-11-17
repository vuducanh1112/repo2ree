from repo2ree.repo2ree import repo2ree


def test_repo2ree_requirementstxt(resources_dir, output_dir):
    repo = resources_dir / "repos" / "requirements-txt"

    output_dir = output_dir / repo.name
    output_dir.mkdir(parents=True, exist_ok=True)

    repo2ree(repo, output_dir)

    assert (output_dir / "Dockerfile-ree").exists()
    assert (output_dir / "ree.tar").exists()
    assert (output_dir / "sbom.json").exists()
    assert (output_dir / "ree.json").exists()
