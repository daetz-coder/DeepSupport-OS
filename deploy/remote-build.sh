#!/bin/bash
set -euo pipefail
cd /opt/deepsupport-os
export COMPOSE_PARALLEL_LIMIT=1
export DOCKER_BUILDKIT=1

pull_one() {
  local img="$1"
  if docker pull "$img"; then
    return 0
  fi
  local mirror="docker.m.daocloud.io/library/${img}"
  docker pull "$mirror"
  docker tag "$mirror" "$img"
}

echo "=== pulling base images ==="
pull_one python:3.12-slim
pull_one node:22-alpine
pull_one nginx:1.27-alpine

echo "=== compose build ==="
docker compose -f docker-compose.prod.yml build --progress=plain
echo "=== compose up ==="
docker compose -f docker-compose.prod.yml up -d
echo "=== status ==="
docker compose -f docker-compose.prod.yml ps
docker stats --no-stream || true
free -h
