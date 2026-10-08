# File: src/restikls/cli/key.py
"""
CLI commands for managing the encryption key, including generation and display.
"""

import os
import sys

import click
from flask import Blueprint, current_app

from ..defaults import DefaultConfig
from ..lib.encrypt import generate_new_key, read_key

# Define a Blueprint. The name 'cli_key' is arbitrary but should be unique.
# The `cli_group` parameter names the command group in the terminal (e.g., 'flask key ...')
bp: Blueprint = Blueprint("cli_key", __name__, cli_group="key")


@bp.cli.command("generate")
@click.option(
    "--force", is_flag=True, help="Overwrite the existing key file without prompting."
)
@click.option(
    "--if-missing", is_flag=True, help="Create the key only if missing, without prompting."
)
def generate(force: bool, if_missing: bool) -> None:
    """Generates a new secret encryption key."""
    if force and if_missing:
        raise click.UsageError("--force and --if-missing cannot be used together.")

    key_file_path = current_app.config.get("KEY_FILE", DefaultConfig.KEY_FILE)
    if os.path.exists(key_file_path) and not force:
        if if_missing:
            click.echo(f"Key file '{key_file_path}' already exists. Skipping generation.")
            return
        # Use sys.stdout/stderr for CLI context
        click.echo(f"WARNING: Key file '{key_file_path}' already exists.")
        try:
            response = input("Overwrite? (y/N): ")
        except EOFError:  # Handles non-interactive environments
            response = "n"
        if response.lower() != "y":
            click.echo("Aborted key generation.")
            # return False
            sys.exit(0)

    # Call the key generation logic from the encrypt module
    if not generate_new_key(key_file_path):
        # The function returns False on failure or user abort.
        # Exit with a non-zero status code to indicate failure.
        sys.exit(1)


@bp.cli.command("print")
def display() -> None:
    """Prints the secret encryption key."""
    key_file_path = current_app.config.get("KEY_FILE", DefaultConfig.KEY_FILE)
    # Call the key read logic from the encrypt module
    key_bytes = read_key(key_file_path)
    click.echo(key_bytes.decode())
