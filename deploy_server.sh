#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$1"
cd "$HOME/Projects/$PROJECT_DIR"

TARGET="${HOME}/.steam/steam/steamapps/common/Valheim dedicated server"
cp bin/Release/netstandard2.1/*.dll "${TARGET}"/BepInEx/plugins/
cp *.cfg "${TARGET}"/BepInEx/config/
echo "Files deployed to Valheim Server BepInEx plugin and config folders."

