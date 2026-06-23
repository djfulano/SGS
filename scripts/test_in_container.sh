#!/usr/bin/env sh
set -eu

SERVICE="${SNMPC_DOCKER_SERVICE:-snmpc-dashboard}"

compose() {
    if docker compose ps >/dev/null 2>&1; then
        docker compose "$@"
        return
    fi

    sudo docker compose "$@"
}

compose build "$SERVICE"
compose run --rm -T --no-deps "$SERVICE" python -m unittest discover -s tests "$@"
