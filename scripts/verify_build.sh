#!/usr/bin/env bash
set -euo pipefail

# Basic build verification script for android-builder image
# Usage: scripts/verify_build.sh [gradle_project_dir]

PROJECT_DIR=${1:-./android-sample}
IMAGE_TAG=macaron-android-builder:verify

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project dir $PROJECT_DIR not found. Create a small sample gradle project or pass path." >&2
  exit 1
fi

# Build docker image
docker build -t $IMAGE_TAG docker/android-builder

# Run container to execute ./gradlew assemble
docker run --rm -v $(pwd)/$PROJECT_DIR:/work -w /work $IMAGE_TAG /usr/local/bin/android_build ./gradlew assemble

echo "Build verification completed successfully."
