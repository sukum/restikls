# File: tests/test_services/test_factory.py

from unittest.mock import Mock

import pytest
import time

from restikls.services.command_executor import (
    LocalExecutor,
    RestServerExecutor,
    SftpExecutor,
)
from restikls.services.factory import ResticServiceFactory
from restikls.services.restic_service import ResticService
from restikls.models.credentials import ResticCredentials

@pytest.mark.parametrize(
    "repo_path, expected_executor_class",
    [
        ("/local/path", LocalExecutor),
        ("sftp://user@host:/path", SftpExecutor),
        ("rest:http://host/path", RestServerExecutor),
        ("", LocalExecutor),  # Default to local if empty
        ("http://invalid", LocalExecutor),  # Fallback to local
    ],
)
def test_get_service(app, caplog, repo_path, expected_executor_class):
    """
    Test that the factory creates the correct executor based on repo_path.
    """
    repo_cred = ResticCredentials(
        repo_path=repo_path,
        repo_key="test_password",
        timestamp=time.time(),
    )

    # config = {"repo_cred": repo_cred}
    cache_service = Mock()

    service = ResticServiceFactory.get_service(repo_cred, cache_service)

    assert isinstance(service, ResticService)
    assert isinstance(service.executor, expected_executor_class)
    assert service.repo_cred == repo_cred
    assert service.cache_service == cache_service

    # Verify logger was called with expected message
    if expected_executor_class == SftpExecutor:
        assert "SFTP repository detected. Using SftpExecutor." in caplog.text
    elif expected_executor_class == RestServerExecutor:
        assert "Rest repository detected. Using RestServerExecutor." in caplog.text
    else:
        assert "Local repository detected. Using LocalExecutor." in caplog.text
