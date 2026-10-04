# File: src/restikls/models/run_options.py
from dataclasses import dataclass, field

from ..defaults import DefaultConfig

@dataclass
class RunOptions:
    """
    Class to encapsulate run options for subprocess execution.
    """
    capture_output: bool = True
    text: bool = True # False for file_metadata and dump
    shell: bool = False  # Important for security
    timeout: int = DefaultConfig.SUBPROCESS_TIMEOUT  # Default timeout
    check: bool = False  # Check return code manually
    # Environment variables for subprocess
    env: dict = field(default_factory=dict)  
