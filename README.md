# restikls

`restikls` is a self-hosted web interface for browsing [restic](https://restic.net/) repositories. It is built with Python, Flask, and Alpine.js and runs the restic command-line program to read repository data.

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

- Python 3.10 or newer for running from source.
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
python run.py
```

Open <http://127.0.0.1:5000>. Make sure the `restic` executable is installed and available on `PATH`.

## Repository configuration

The repository path is entered in the web interface. The app currently recognizes these repository types:

| Type | Path format | Additional information |
| --- | --- | --- |
| Local | A filesystem path, absolute or relative to `REPO_BASE_DIR` | The repository directory must be accessible to the app process. |
| SFTP | `sftp://...` | Provide an SSH private key in the configuration form. [Restic docs](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#sftp)|
| REST | `rest:http://...` or `rest:https://...` | Uses a rest-server URL.[Restic docs](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#rest-server) |

When using a local repository in a container, mount the host directory into the container and enter the **container path** in the web interface. The examples below mount it at `/repos/repository`.

### Application settings

The app loads an optional `config.toml` from its current working directory. Environment variables prefixed with `RESTIKLS_` override settings from that file. For example:

```toml
REPO_BASE_DIR = "/repos"
SESSION_COOKIE_SECURE = true
```

The equivalent environment variables are `RESTIKLS_REPO_BASE_DIR` and `RESTIKLS_SESSION_COOKIE_SECURE`. Set the secure-cookie option when serving the app over HTTPS. `REPO_BASE_DIR` limits which local repository paths can be selected; its default is `/`. IF you intend to serve only repositories from your home directory, change it to `/home/<username>`.

## Docker

Build the production image from the project directory. The default base is Debian-based `python:3.14-slim`; `BASE` can be set to `alpine` to use `python:3.14-alpine` instead:

```sh
# Default is debian based slim
docker build --target prod -t restikls:slim .
# For alpine based
docker build --target prod --build-arg BASE=alpine -t restikls:alpine .
```

The slim image is the default and is a good general-purpose choice. Alpine is an alternative base; it uses musl instead of Debian's glibc, so Python package compatibility can differ. Build and run the image variant you plan to deploy. The Docker and Podman run examples below use `restikls:slim`; use `restikls:alpine` to run the Alpine build.

Create a named volume to retain the app's encryption key across container replacements, then start the app. Replace `/absolute/path/to/restic-repository` with the host repository directory:

```sh
docker volume create restikls-state

docker run --detach \
  --name restikls \
  --publish 5000:5000 \
  --env RESTIKLS_REPO_BASE_DIR=/repos \
  --env RESTIKLS_KEY_FILE=/app/cache/secret.key \
  --mount type=bind,source=/absolute/path/to/restic-repository,target=/repos/repository \
  --mount type=volume,source=restikls-state,target=/app/cache \
  restikls:slim
```

Open <http://127.0.0.1:5000> and input repository path as `/repos/repository`. The repository mount is read-write because restic may need to write lock files. The named volume retains the key used to encrypt repository credentials stored in the browser cookie; keep it with your deployment data.

The Dockerfile also has a `dev` target for development containers. The default build target is `prod`.

## Podman

Build and run the production image with Podman. Select either base using the same `BASE` build argument:

```sh
# Default is debian based slim
podman build --target prod -t restikls:slim .
# For alpine based
podman build --target prod --build-arg BASE=alpine -t restikls:alpine .
podman volume create restikls-state

podman run --detach \
  --name restikls \
  --publish 5000:5000 \
  --env RESTIKLS_REPO_BASE_DIR=/repos \
  --env RESTIKLS_KEY_FILE=/app/cache/secret.key \
  --volume /absolute/path/to/restic-repository:/repos/repository:rw,Z \
  --volume restikls-state:/app/cache \
  restikls:slim
```

Open <http://127.0.0.1:5000> and configure the repository as `/repos/repository`. On a host without SELinux, omit the `,Z` suffix from the bind mount. On Windows, use the repository path syntax supported by your Docker or Podman machine.

## Security notes

- The app has no built-in user login. Keep it on a trusted network or put it behind an authenticated reverse proxy before allowing other users to reach it.
- Use HTTPS when accessing the app remotely and set `RESTIKLS_SESSION_COOKIE_SECURE=true`.
- Keep the encryption-key volume or key file private. It is used to decrypt the repo information from a user's browser cookies.
- The app needs access to the configured repository and runs restic commands with the repository credentials supplied in the configuration page.
- For sftp repository paths, 4096-bit ssh keys might not work due to the size limit on browser cookies.

## Development checks

```sh
uv run pytest
uv run ty check src
```

## Contact for support

If you face errors during the installation, you can reach out via IRC to me at sree@irc.libera.chat.

[Libera.Chat](https://web.libera.chat/?channel=sree)

## AI Usage

AI has been used in development.

## License

Released under the MIT License.
