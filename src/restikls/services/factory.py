# File: src/restikls/services/factory.py
"""
Create ResticService with appropriate executor based on repository type.
"""

from typing import Any

from flask import current_app

from ..models.backends import BackendType, determine_backend_type
from ..models.credentials import ResticCredentials
from .command_executor import LocalExecutor, RestServerExecutor, SftpExecutor
from .restic_service import ResticService


class ResticServiceFactory:
    """Factory to create the restic service with the appropriate executor."""

    @staticmethod
    def get_service(repo_cred: ResticCredentials, cache_service: Any) -> ResticService:
        """Create ResticService with appropriate executor based on repository type."""

        if not repo_cred:
            msg = (
                "Cannot create service from ResticServiceFactory::get_service "
                "because repo_cred is not provided"
            )
            current_app.logger.error(msg)
            raise RuntimeError(msg)

        backend_type = determine_backend_type(repo_cred.repo_path)

        if backend_type == BackendType.SFTP:
            current_app.logger.debug("SFTP repository detected. Using SftpExecutor.")
            executor = SftpExecutor(repo_cred)
        elif backend_type == BackendType.REST:
            current_app.logger.debug(
                "Rest repository detected. Using RestServerExecutor."
            )
            executor = RestServerExecutor(repo_cred)
        else:
            current_app.logger.debug("Local repository detected. Using LocalExecutor.")
            executor = LocalExecutor(repo_cred)

        return ResticService(executor.repo_cred, cache_service, executor)
