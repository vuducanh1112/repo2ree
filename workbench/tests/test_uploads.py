import pytest

from repo2ree_workbench.uploads import transfer_url


@pytest.mark.parametrize(
    ("dialed", "url"),
    [
        ("ws://host.docker.internal:8000/workbench/connect", "http://host.docker.internal:8000/workbench/transfers/t"),
        ("wss://api.example/workbench/connect", "https://api.example/workbench/transfers/t"),
    ],
)
def test_an_upload_goes_where_the_control_socket_goes(dialed: str, url: str) -> None:
    assert transfer_url(dialed, "/workbench/transfers/t") == url


def test_a_relative_transfer_path_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot address"):
        transfer_url("ws://api:8000/workbench/connect", "workbench/transfers/t")
