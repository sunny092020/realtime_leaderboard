#!/bin/bash

echo "🔄 Stopping and removing all containers in the stack..."
docker compose down

echo "🗑️  Removing the flink-stack-data volume..."
docker volume rm flink-stack-data

echo "✨ Cleanup complete!" 