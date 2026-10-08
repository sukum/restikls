# restikls

`restikls` is a self-hosted web interface for browsing [restic](https://restic.net/) repositories. It is built with Python, Flask, and Alpine.js/tailwindcss and runs the restic command-line program to read repository data.

## Features

- View repository statistics and browse snapshots.
- Sort and filter snapshots by host and tags.
- View snapshot details, browse and search files, and inspect a file's history across snapshots.
- View or download individual files from a snapshot.
- List repository keys.
- Connect to local repositories, SFTP repositories, and rest-server repositories.
- Login involves entering a repositorty path and its key, which would be validated and if verified encrypted and stored as a cookie on the user's browser. The path and key are not stored on the server.

The web interface is for browsing repository contents. It does not modify the repository in any way.

## Requirements

- Python 3.10 or newer for running from source. Python 3.10 also requires `tomli` to read TOML configuration; Python 3.11 and newer use the built-in `tomllib` module.
- The `restic` executable on `PATH` when running from source. The container image includes restic.
- Docker or Podman for container deployments.

## Run from source

<ins>**uv**</ins>

From the project directory:

```sh
uv sync
uv run restikls
```

Open <http://127.0.0.1:5000> and enter the repository path and password on the configuration page. For a local repository, the process must be able to read and write the repository directory so restic can create its lock files.

For Flask's development server with debug mode enabled:

```sh
uv run flask --app src/restikls:create_app run --debug
```

Run the test suite with:

```sh
uv run pytest
```

<ins>**pip**</ins>

From the project directory, create and activate a virtual environment. In Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, activate it with:

```sh
python -m venv .venv
source .venv/bin/activate
```

Install the dependencies and the project in editable mode, then start the app with Python:

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip install 'tomli; python_version < "3.11"'
python run.py
```

Open <http://127.0.0.1:5000>. Make sure the `restic` executable is installed and available on `PATH`.

### Linux (Gunicorn)

On Linux, use [Gunicorn](https://gunicorn.org/run/) to serve the Flask app exposed by `run.py`. Gunicorn is included in the project's dependencies. After installing them, run this command from the project directory with the virtual environment activated:

```sh
gunicorn --pythonpath src --bind 127.0.0.1:5000 \
  --workers 2 --threads 4 --timeout 120 run:app
```

With `uv`:

```sh
uv sync
uv run gunicorn --pythonpath src --bind 127.0.0.1:5000 \
  --workers 2 --threads 4 --timeout 120 run:app
```

`run:app` selects the `app` object in `run.py`. These examples use two worker processes with four threads each and serve the app at <http://127.0.0.1:5000>. To accept connections from other machines, change the bind address to `0.0.0.0:5000`.

### Windows (Waitress)

On Windows, use [Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/) with the provided `waitress-server.py` script. After installing the app dependencies above, install Waitress in the activated virtual environment and start it from the project directory:

```powershell
python -m pip install waitress
python waitress-server.py
```

With `uv`, Waitress is included in the project's `dev` dependency group:

```powershell
uv run pip add waitress
uv run python waitress-server.py
```

The script serves the app at <http://127.0.0.1:5000> with four worker threads. It listens on localhost; adjust `host` in `waitress-server.py` if you need to accept connections from other machines.

## Repository configuration

The repository path is entered in the web interface. The app currently recognizes these repository types:

| Type | Path format | Additional information |
| --- | --- | --- |
| Local | A filesystem path, absolute or relative to `REPO_BASE_DIR` | The repository directory must be accessible to the app process. |
| SFTP | `sftp://...` | Provide an SSH private key in the configuration form. [Restic docs](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#sftp)|
| REST | `rest:http://...` or `rest:https://...` | Uses a rest-server URL.[Restic docs](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#rest-server) |

When using a local repository in a container, mount the host directory into the container and enter the **container path** in the web interface. The examples below mount it at `/app/repos`.

### Application settings

Settings are loaded in this order: built-in defaults, `config.toml`, then environment variables prefixed with `RESTIKLS_`. Environment variables take precedence. Use uppercase keys. For example:

```toml
REPO_BASE_DIR = "/app/repos"
SESSION_COOKIE_SECURE = true
```

The equivalent environment variables are `RESTIKLS_REPO_BASE_DIR=/app/repos` and `RESTIKLS_SESSION_COOKIE_SECURE=true`.

By default, `create_app()` loads the optional `config.toml` from the project root: `config.toml` in this checkout, or `/app/config.toml` in the docker image. To select another file, set `RESTIKLS_CONFIG_FILE_NAME`, for example `RESTIKLS_CONFIG_FILE_NAME=config.production.toml`. An unset or empty environment variable falls back to `config.toml`. Relative config filenames resolve from the project root. Settings are loaded from built-in defaults, then the selected TOML file, then `RESTIKLS_` environment overrides. Relative paths **inside** the settings, such as `logs` and `secret.key`, resolve from the process working directory (`/app` in the container).

The table covers settings defined or explicitly used by restikls, including the Flask and Flask-Caching settings it uses. **Current default** includes the bundled root-level `config.toml`; where that file changes a built-in value, both are shown. **Suggested value** is a starting point for deployment, not an automatic override. Timeouts are in seconds and file sizes are in bytes.

| `config.toml` key | Environment variable | Short explanation | Current default | Suggested value |
| --- | --- | --- | --- | --- |
| `REPO_BASE_DIR` | `RESTIKLS_REPO_BASE_DIR` | Limits local repository paths to this directory and its descendants; also resolves relative repository paths. | `"."` (process working directory; `/app` in containers) bundled; | Keep a directory whose repositories you want to expose through  the web app |
| `REPO_KEY_MAXLEN` | `RESTIKLS_REPO_KEY_MAXLEN` | Maximum repository password length in characters. | `100` | `100`; increase if your passwords are longer. |
| `KEY_FILE` | `RESTIKLS_KEY_FILE` | File holding the key used to encrypt repository credentials; also supplies Flask's secret unless `SECRET_KEY` is set. Generated if missing. | `"secret.key"` | `"/app/cache/secret.key"` on persistent storage in containers; `"secret.key"` locally. The parent directory must exist and be writable. |
| `SECRET_KEY` | `RESTIKLS_SECRET_KEY` | Overrides Flask's session-signing secret. Repository credential encryption still uses `KEY_FILE`. | Loaded from `KEY_FILE`. | Leave unset and retain `KEY_FILE` across restarts. |
| `SESSION_LIFE` | `RESTIKLS_SESSION_LIFE` | Lifetime of the repository credential cookie. A positive integer also sets credential validity. Unset means a browser-session cookie. | Unset (`None`). | Omit for browser sessions, or use `3600` for one hour. |
| `ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY` | `RESTIKLS_ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY` | Credential expiry when `SESSION_LIFE` is not a positive integer; measured from login. | `86400` (24 hours). | `86400`. |
| `SESSION_COOKIE_SECURE` | `RESTIKLS_SESSION_COOKIE_SECURE` | Sends Flask session and repository credential cookies only over HTTPS when enabled. | `false` | `true` for HTTPS; `false` for local HTTP. |
| `SUBPROCESS_TIMEOUT` | `RESTIKLS_SUBPROCESS_TIMEOUT` | Time limit for restic commands without a more specific timeout. | `60` | Use higher values for large repositories. |
| `REPO_STATS_TIMEOUT` | `RESTIKLS_REPO_STATS_TIMEOUT` | Time limit for loading repository statistics in dashboard. | `30` | `30`; increase for slow or large repositories. |
| `FILE_OPERATIONS_TIMEOUT` | `RESTIKLS_FILE_OPERATIONS_TIMEOUT` | Time limit for listing snapshot files and reading file contents. | `60` | `60`; increase for slow storage. |
| `FILE_DOWNLOAD_MAXSIZE` | `RESTIKLS_FILE_DOWNLOAD_MAXSIZE` | Largest individual file the web interface allows downloading. | `52428800` (50 MiB). | Downloads are buffered in browser window memory. So be cautious making it larger. |
| `FILE_VIEW_MAXSIZE` | `RESTIKLS_FILE_VIEW_MAXSIZE` | Largest individual file the web interface allows previewing as text. | `1048576` (1 MiB). | Uses Highlight.js to prettify the content. Opening a large enough file could cause the browser to freeze and/or crash |
| `PAGE_RECORDS` | `RESTIKLS_PAGE_RECORDS` | Number of items per paginated page; must be a positive integer. | `10` bundled; `20` built-in. | `20`. |
| `CACHE_TYPE` | `RESTIKLS_CACHE_TYPE` | Flask-Caching backend for application results. | `"FileSystemCache"` bundled; caching disabled if omitted from a replacement config. | Uses the [Flask Caching library](https://flask-caching.readthedocs.io/en/latest/). `"FileSystemCache"` for the production container; `"NullCache"` to disable caching; `"SimpleCache"` for in-memory caching. `"RedisCache"` and `"MemcachedCache"` require additional dependencies and cache servers. |
| `CACHE_DIR` | `RESTIKLS_CACHE_DIR` | Writable directory when using `"FileSystemCache"`. | `"cache"` | `"/app/cache"` in containers; `"cache"` locally. |
| `CACHE_TIMEOUT` | `RESTIKLS_CACHE_TIMEOUT` | Lifetime of results stored by the application's cache service. `0` or `null` falls back to 600 seconds. | `3600` bundled; `600` built-in. | `600` for results up to ten minutes old. |
| `LOG_DIRECTORY` | `RESTIKLS_LOG_DIRECTORY` | Directory for rotating application log files. | `"logs"` | `"/app/logs"` in containers; `"logs"` locally. |
| `LOG_FILENAME` | `RESTIKLS_LOG_FILENAME` | Log filename inside `LOG_DIRECTORY`. | `"app.log"` | `"app.log"`. |
| `LOG_MAX_BYTES` | `RESTIKLS_LOG_MAX_BYTES` | Log size at which a new log file is started. | `1000000` (1 MiB) | `1000000`. |
| `LOG_BACKUP_COUNT` | `RESTIKLS_LOG_BACKUP_COUNT` | Number of rotated log files to keep, in addition to the current file. | `5` | `5`. |
| `LOG_LEVEL` | `RESTIKLS_LOG_LEVEL` | Application log verbosity: `debug`, `info`, `warning`, `error`, or `critical`. | `"warning"` | `"warning"`; use `"info"` for more operational detail. |
| `DEBUG` | `RESTIKLS_DEBUG` | Enables application debug behavior, including readable cache keys. Development-server debugging also depends on the launcher. | `false` bundled. | `false` for deployment. |
| `DEBUG_SSH_CONNECTION` | `RESTIKLS_DEBUG_SSH_CONNECTION` | Adds verbose SSH output (`-vv`) to SFTP commands. | `false` | `false`; enable when diagnosing SFTP failures. |



## Docker

Build the production image from the project directory. The default base is Debian-based `python:3.14-slim`; `BASE` can be set to `alpine` to use `python:3.14-alpine` instead:

```sh
# Default is debian based slim
docker build --target prod -t restikls:debian .
# For alpine based
docker build --target prod --build-arg BASE=alpine -t restikls:alpine .
```

The debian image is the default and is a good general-purpose choice. Alpine is an alternative base; it uses musl instead of Debian's glibc, so Python package compatibility can differ. Build and run the image variant you plan to deploy. The Docker and Podman run examples below use `restikls:debian`; use `restikls:alpine` to run the Alpine build.

Create a named volume to retain the app's encryption key across container replacements and for writing temporary cache files. Replace `/absolute/path/to/restic-repository-parent` with the host directory containing the restic repositories. If your restic repository is `/home/user/restic`, provide `/home/user` for above. It is to restrict the repository paths submitted from browser to be restricted to only those directories inside `/home/user`. If the user enters `/home/another-user/restic`, it wouldn't be allowed.

```sh
# Used for secret key and flask cache
docker volume create restikls-state

docker run --detach \
  --name restikls \
  --publish 5000:5000 \
  --env RESTIKLS_REPO_BASE_DIR=/app/repos \
  --env RESTIKLS_KEY_FILE=/app/cache/secret.key \
  --mount type=bind,source=/absolute/path/to/restic-repository-parent,target=/app/repos \
  --mount type=volume,source=restikls-state,target=/app/cache \
  restikls:debian
```

Open <http://127.0.0.1:5000> and input repository path as `/app/repos/repository`. The repository mount is read-write because restic may need to write lock files. The named volume retains the key used to encrypt repository credentials stored in the browser cookie; keep it with your deployment data.

The Dockerfile also has a `dev` target for development containers. The default build target is `prod`.

## Podman

Build and run the production image with Podman. Select either base using the same `BASE` build argument:

```sh
# Default is debian based slim
podman build --target prod -t restikls:debian .
# For alpine based
podman build --target prod --build-arg BASE=alpine -t restikls:alpine .
# Used for secret key and flask cache
podman volume create restikls-state

podman run --detach \
  --name restikls \
  --publish 5000:5000 \
  --env RESTIKLS_REPO_BASE_DIR=/app/repos \
  --env RESTIKLS_KEY_FILE=/app/cache/secret.key \
  --volume /absolute/path/to/restic-repository-parent:/app/repos:rw,Z \
  --volume restikls-state:/app/cache \
  restikls:debian
```

Open <http://127.0.0.1:5000> and configure the repository as `/app/repos/repository`. On a host without SELinux, omit the `,Z` suffix from the bind mount.

## Security notes

- The app has no built-in user login. Keep it on a trusted network or put it behind an authenticated reverse proxy before allowing other users to reach it.
- Use HTTPS when accessing the app remotely and set `RESTIKLS_SESSION_COOKIE_SECURE=true`.
- Keep the encryption-key volume or key file private. It is used to decrypt the repo information from a user's browser cookies.
- The app needs access to the configured repository and runs restic commands with the repository credentials supplied in the configuration page.
- For sftp repository paths, 4096-bit ssh keys might not work due to the size limit on browser cookies.

## Development checks

```sh
uv run pytest
uvx ty check src
```

## Contact for support

If you face errors during the installation, you can reach out via IRC to me at sree@irc.libera.chat.

[Libera.Chat](https://web.libera.chat/?channel=sree)

## AI Usage

AI has been used in development.

## License

Released under the MIT License.
