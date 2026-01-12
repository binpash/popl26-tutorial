# POPL'26 Shell Tutorial

Usage
- You should work in `src/`, with `src/solution.py` as the main file you will be editing.
- The complete solution for all steps is in `SOLUTION/`.
- To test your code, you should run it directly, e.g. `python3 src/solution.py sh/SOME_SAMPLE_SHELL_FILE.sh`.

If you are using VS Code (which we recommend), you should have it create a venv for you, which will automatically install the Python dependencies.

Docker (GHCR)
- Pull: `docker pull ghcr.io/binpash/popl26-tutorial:latest`
- Run with current directory mounted: `docker run --rm -it --privileged -v "$PWD":/app ghcr.io/binpash/popl26-tutorial:latest`

Docker (built from the repo)
- Build: `docker build -t popl26-tutorial .`
- Run an interactive shell: `docker run --rm -it --privileged popl26-tutorial`
- Run with current directory mounted: `docker run --rm -it --privileged -v "$PWD":/app popl26-tutorial`

Note: `try` requires `unshare` and mount privileges; `--privileged` enables those in Docker.
Note: The image PATH includes `/opt/venv/bin` and `./bin`. Local development may also want to add these to `PATH`.
