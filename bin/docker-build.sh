#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
root_path="${bin_path}/.."


usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker build helper script

    Optional overrides:
        "\${GIT_REPO}" - URL of git repository to build from (defaults to current repo)
USAGE
   exit 1
}


if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# Create env_file if it doesn't exist
cp \
    --no-clobber \
    "${root_path}/docker/portal.env.default" \
    "${root_path}/docker/portal.env"

export COMPOSE_FILE="${COMPOSE_FILE:-${root_path}/docker/docker-compose.yaml:${root_path}/docker/docker-compose.build.yaml}"


# Build debian package from current repo and branch
echo "Building debian package..."
docker-compose run builder

echo "Building portal docker image..."
# Build portal docker image from debian package
docker-compose build web
