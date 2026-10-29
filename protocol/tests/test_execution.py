import pytest
from pydantic import ValidationError

from repo2ree_protocol.execution import ExecutionContext


@pytest.mark.parametrize("attempt_id", ["", "../escape", "a/b", "a\\b", "a" * 129])
def test_attempt_identity_cannot_escape_local_storage(attempt_id):
    with pytest.raises(ValidationError):
        ExecutionContext(operation_id="operation", attempt_id=attempt_id)
