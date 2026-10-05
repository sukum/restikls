# File: src/restikls/models/credentials.py
import time
from dataclasses import dataclass

from flask import current_app


@dataclass
class ResticCredentials:
    repo_path: str
    repo_key: str
    timestamp: float
    ssh_key: str | None = None

    @property
    def is_expired(self) -> bool:
        session_life = current_app.config["SESSION_LIFE"]
        # Use session_life from config if set
        if isinstance(session_life, int) and session_life > 0:
            validity_period = session_life
        # otherwise fallback to ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY
        else:
            validity_period: int = (
                current_app.config["ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY"]
            )
        current_time = time.time()
        timestamp = getattr(self, "timestamp", 0)
        # Debug
        if current_app.debug:
            current_app.logger.debug("repo_cred_validity: %s", validity_period)
            current_app.logger.debug(
                "current_time: %s, timestamp: %s, validity_period: %s",
                current_time,
                timestamp,
                validity_period,
            )
        # calculate time passed since timestamp
        time_period_passed = current_time - timestamp
        # if time passsed is less than or equal to validity period, then not expired
        if time_period_passed <= validity_period: # Not expired
            current_app.logger.debug(
                "cred valid for %s more seconds", validity_period - time_period_passed
            )
            return False
        # else, expired
        current_app.logger.info("Configuration expired")
        return True

    def __contains__(self, item: str) -> bool:
        return item in self.__dict__
