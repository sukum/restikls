#!/bin/sh
# Entrypoint script for Flask application
# Runs necessary initialization commands before starting the application

set -e  # Exit on error

# file path of secret key
FILE_PATH="/app/secret.key"

# Log the initiation of the check
echo "Checking for the existence of ${FILE_PATH}..."

if [ -f "$FILE_PATH" ]; then
    # File already exists, skip generation to prevent overwriting
    echo "Info: ${FILE_PATH} already exists. Skipping Flask key generation."
else
    echo "Generating Flask secret key at ${FILE_PATH}"
    # Run flask key generate command
    # Note: Ensure FLASK_APP environment variable is set
    flask key generate || {
        echo "Warning: Failed to generate Flask key. Continuing anyway..."
    }
fi

for dir in "${LOGS_DIR:-/app/logs}" "${CACHE_DIR:-/app/cache}"; do
    if [ -d "$dir" ] && [ ! -w "$dir" ]; then
        echo "Warning: Directory '${dir}' is not writable by user $(id -u). Logging/caching may fail."
    fi
done

echo "Starting container process: $@"
# Execute the main container process
exec "$@"
