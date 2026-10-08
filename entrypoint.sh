#!/bin/sh
# Entrypoint script for Flask application
# Runs necessary initialization commands before starting the application

set -e  # Exit on error

# Let Flask resolve KEY_FILE from defaults, config.toml, and environment overrides.
# Preserve existing keys without prompting; set -e stops startup on failure.
echo "Checking for Flask secret key and generating it if not present"
# Run flask key generate command
# Note: Ensure FLASK_APP environment variable is set
flask key generate --if-missing || {
    echo "Warning: Failed to generate Flask key. Continuing anyway..."
    echo "Run: "flask key generate --force" to generate the secret key."
}

for dir in "${RESTIKLS_LOG_DIRECTORY:-/app/logs}" "${RESTIKLS_CACHE_DIR:-/app/cache}"; do
    if [ -d "$dir" ] && [ ! -w "$dir" ]; then
        echo "Warning: Directory '${dir}' is not writable by user $(id -u). Logging/caching may fail."
    fi
done

echo "Starting container process: $@"
# Execute the main container process
exec "$@"
