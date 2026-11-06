#!/bin/sh
set -eu

# Run from the repo root so this works regardless of the caller's directory.
cd "$(dirname "$0")/.."

docker buildx build -t localhost:31000/ct-event-scraper:latest -f docker/Dockerfile .
docker push localhost:31000/ct-event-scraper:latest
