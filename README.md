# POPL'26 Shell Tutorial

Usage
- Scripts live in `src/`. Run them directly, e.g. `python3 src/analysis.py`

Docker
- Build: `docker build -t popl26-tutorial .`
- Run an interactive shell: `docker run --rm -it --privileged popl26-tutorial`
- Run with current directory mounted: `docker run --rm -it --privileged -v "$PWD":/app popl26-tutorial`

Note: `try` requires `unshare` and mount privileges; `--privileged` enables those in Docker.

Docker (GHCR)
- Pull: `docker pull ghcr.io/binpash/popl26-tutorial:latest`
- Run with current directory mounted: `docker run --rm -it --privileged -v "$PWD":/app ghcr.io/binpash/popl26-tutorial:latest`
