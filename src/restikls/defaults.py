# File: src/restikls/defaults.py

class DefaultConfig:

    #config
    CONFIG_FILE_NAME = "config.toml"

    # Timeouts
    # DEFAULT_SUBPROCESS = 60
    SUBPROCESS_TIMEOUT = 60
    REPO_STATS_TIMEOUT = 30
    FILE_OPERATIONS_TIMEOUT = 60
    MAINTENANCE_CHECK_TIMEOUT = 300

    # Cache
    # DEFAULT_TIMEOUT = 3600
    CACHE_DEFAULT_TIMEOUT = 600
    CACHE_TIMEOUT = CACHE_DEFAULT_TIMEOUT

    # auth and security
    KEY_FILE = "secret.key"
    # SECRET_KEY = 
    SESSION_LIFE = None  # Browser session
    SESSION_COOKIE_SECURE = False
    # Used if SESSION_LIFE is not int
    ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY = 3600 * 24  # 1 day
    REPO_BASE_DIR = "/"
    REPO_KEY_MAXLEN = 100

    # view and UI
    PAGE_RECORDS = 20

    # File
    # Download file maximum size = 50MB
    FILE_DOWNLOAD_MAXSIZE: int = 50 * 1024 * 1024
    # View file maximum size = 1MB
    FILE_VIEW_MAXSIZE: int = 1 * 1024 * 1024

    # Logging
    LOG_DIRECTORY = "logs"
    LOG_FILENAME = "app.log"
    # 1MB per file
    LOG_MAX_BYTES = 1 * 1024 * 1024
    # Keep 5 backup files
    LOG_BACKUP_COUNT = 5
    LOG_LEVEL = "warning"

    # env
    REQUIRED_ENV_VARS = [
        # windows
        "PATH",
        "USERPROFILE",
        "SystemRoot",
        "TEMP",
        "TMP",
        "PROGRAMDATA",
        "LOCALAPPDATA",
        # Linux
        "HOME",
        # 'PATH',
    ]

