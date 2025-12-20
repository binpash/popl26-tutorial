# POPL'26 Shell Tutorial

Usage
- Scripts live in `src/`. Run them directly, e.g. `python3 src/parse-unparse.py`

Docker
- Build: `docker build -t popl26-tutorial .`
- Run an interactive shell: `docker run --rm -it popl26-tutorial`
- Run with current directory mounted: `docker run --rm -it -v "$PWD":/app popl26-tutorial`

Docker (GHCR)
- Pull: `docker pull ghcr.io/binpash/popl26-tutorial:latest`
- Run with current directory mounted: `docker run --rm -it -v "$PWD":/app ghcr.io/binpash/popl26-tutorial:latest`
