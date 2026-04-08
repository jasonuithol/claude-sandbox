#!/usr/bin/env bash
set -euo pipefail

EXISTING_PWD="$PWD"
COMMANDS_DIR="$HOME/ClaudeProjects/valheim/commands"
LOGS_DIR="$HOME/ClaudeProjects/valheim/logs"
SERVER_DIR="$HOME/.steam/steam/steamapps/common/Valheim dedicated server"
CLIENT_DIR="$HOME/.steam/steam/steamapps/common/Valheim"
PROJECT_DIR="$HOME/Projects"
SANDBOX_DIR="$HOME/Projects/claude-sandbox"

mkdir -p "$COMMANDS_DIR"
mkdir -p "$LOGS_DIR"

# Build reverse path map: container path -> host path
declare -A PATH_MAP

build_path_map() {
    CONTAINER_ID=$(podman ps --filter ancestor=claude-sandbox --format "{{.ID}}" | head -1)
    if [ -z "$CONTAINER_ID" ]; then
        echo "Warning: could not find running claude-sandbox container — ilspy path mapping unavailable" >&2
        return
    fi
    while IFS= read -r mount; do
        src=$(echo "$mount" | jq -r '.Source')
        dst=$(echo "$mount" | jq -r '.Destination')
        PATH_MAP["$dst"]="$src"
    done < <(podman inspect "$CONTAINER_ID" | jq -c '.[0].Mounts[]')
    echo "Path map built from container $CONTAINER_ID (${#PATH_MAP[@]} mounts)"

    echo "Current path mappings:"
    for dst in "${!PATH_MAP[@]}"; do
        echo "  $dst -> ${PATH_MAP[$dst]}"
    done
}

# Translate a container path to its host equivalent
container_to_host() {
    local container_path="$1"
    local best_match=""
    local best_src=""
    for dst in "${!PATH_MAP[@]}"; do
        echo "DEBUG: checking $dst against $container_path" >&2
        if [[ "$container_path" == "$dst"* ]]; then
            echo "DEBUG: matched $dst -> ${PATH_MAP[$dst]}" >&2
            if [ ${#dst} -gt ${#best_match} ]; then
                best_match="$dst"
                best_src="${PATH_MAP[$dst]}"
            fi
        fi
    done
    echo "DEBUG: best match: $best_match -> $best_src" >&2
    if [ -n "$best_match" ]; then
        echo "${best_src}${container_path#$best_match}"
        return
    fi
    echo "Error: no host mapping found for $container_path" >&2
    return 1
}

build_path_map

echo "Watching $COMMANDS_DIR for commands..."

inotifywait -m -e create "$COMMANDS_DIR" | while read -r dir event file; do
    echo "Command received: $file"
    case "$file" in
        start-server)
            cd "$SERVER_DIR"
            setsid "./byawn_start.sh" > "$LOGS_DIR/server.log" 2>&1 &
            rm -f "$COMMANDS_DIR/$file"
            ;;
        stop-server)
            cd "$SERVER_DIR"
            "./byawn_stop.sh"
            rm -f "$COMMANDS_DIR/$file"
            ;;
        kill-server)
            cd "$SERVER_DIR"
            "./byawn_kill.sh"
            rm -f "$COMMANDS_DIR/$file"
            ;;
        start-client)
            cd "$CLIENT_DIR"
            setsid "./run_bepinex.sh" valheim.x86_64 -console > "$LOGS_DIR/client.log" 2>&1 &
            rm -f "$COMMANDS_DIR/$file"
            ;;
        stop-client)
            cd "$CLIENT_DIR"
            pkill -f "valheim.x86_64" || true
            rm -f "$COMMANDS_DIR/$file"
            ;;
        build)
            TARGET_DIR=$(cat "$COMMANDS_DIR/$file")
            rm -f "$COMMANDS_DIR/$file"
            cd "$PROJECT_DIR/$TARGET_DIR"
            echo "--- Build started: $(date) ---" > "$LOGS_DIR/build.log"
            if dotnet build -c Release >> "$LOGS_DIR/build.log" 2>&1; then
                echo "--- Build succeeded: $(date) ---" >> "$LOGS_DIR/build.log"
                touch "$COMMANDS_DIR/build-done"
            else
                echo "--- Build failed: $(date) ---" >> "$LOGS_DIR/build.log"
                touch "$COMMANDS_DIR/build-failed"
            fi
            ;;
        deploy-server)
            TARGET_DIR=$(cat "$COMMANDS_DIR/$file")
            rm -f "$COMMANDS_DIR/$file"
            echo "--- Deploy-server started: $(date) ---" > "$LOGS_DIR/deploy-server.log"
            if "$SANDBOX_DIR/deploy_server.sh" "$TARGET_DIR" >> "$LOGS_DIR/deploy-server.log" 2>&1; then
                echo "--- Deploy-server succeeded: $(date) ---" >> "$LOGS_DIR/deploy-server.log"
                touch "$COMMANDS_DIR/deploy-server-done"
            else
                echo "--- Deploy-server failed: $(date) ---" >> "$LOGS_DIR/deploy-server.log"
                touch "$COMMANDS_DIR/deploy-server-failed"
            fi
            ;;
        deploy-client)
            TARGET_DIR=$(cat "$COMMANDS_DIR/$file")
            rm -f "$COMMANDS_DIR/$file"
            echo "--- Deploy-client started: $(date) ---" > "$LOGS_DIR/deploy-client.log"
            if "$SANDBOX_DIR/deploy_client.sh" "$TARGET_DIR" >> "$LOGS_DIR/deploy-client.log" 2>&1; then
                echo "--- Deploy-client succeeded: $(date) ---" >> "$LOGS_DIR/deploy-client.log"
                touch "$COMMANDS_DIR/deploy-client-done"
            else
                echo "--- Deploy-client failed: $(date) ---" >> "$LOGS_DIR/deploy-client.log"
                touch "$COMMANDS_DIR/deploy-client-failed"
            fi
            ;;
        ilspy)
            CONTAINER_DLL=$(cat "$COMMANDS_DIR/$file")
            rm -f "$COMMANDS_DIR/$file"
            echo "--- ilspy started: $(date) ---" > "$LOGS_DIR/ilspy.log"
            if HOST_DLL=$(container_to_host "$CONTAINER_DLL"); then
                if ilspycmd "$HOST_DLL" >> "$LOGS_DIR/ilspy.log" 2>&1; then
                    echo "--- ilspy succeeded: $(date) ---" >> "$LOGS_DIR/ilspy.log"
                    touch "$COMMANDS_DIR/ilspy-done"
                else
                    echo "--- ilspy failed: $(date) ---" >> "$LOGS_DIR/ilspy.log"
                    touch "$COMMANDS_DIR/ilspy-failed"
                fi
            else
                echo "--- ilspy failed: could not resolve host path for: $CONTAINER_DLL ---" >> "$LOGS_DIR/ilspy.log"
                touch "$COMMANDS_DIR/ilspy-failed"
            fi
            ;;
        svg-to-png)
            CONTAINER_SVG=$(cat "$COMMANDS_DIR/$file")
            rm -f "$COMMANDS_DIR/$file"
            echo "--- svg-to-png started: $(date) ---" > "$LOGS_DIR/svg-to-png.log"
            if HOST_SVG=$(container_to_host "$CONTAINER_SVG"); then
                HOST_PNG="${HOST_SVG%.svg}.png"
                if rsvg-convert -w 256 -h 256 "$HOST_SVG" -o "$HOST_PNG" >> "$LOGS_DIR/svg-to-png.log" 2>&1; then
                    echo "--- svg-to-png succeeded: $(date) ---" >> "$LOGS_DIR/svg-to-png.log"
                    touch "$COMMANDS_DIR/svg-to-png-done"
                else
                    echo "--- svg-to-png failed: $(date) ---" >> "$LOGS_DIR/svg-to-png.log"
                    touch "$COMMANDS_DIR/svg-to-png-failed"
                fi
            else
                echo "--- svg-to-png failed: could not resolve host path for: $CONTAINER_SVG ---" >> "$LOGS_DIR/svg-to-png.log"
                touch "$COMMANDS_DIR/svg-to-png-failed"
            fi
            ;;
        # Result files are left for the container to read — do not delete
        build-done|build-failed|\
        deploy-server-done|deploy-server-failed|\
        deploy-client-done|deploy-client-failed|\
        ilspy-done|ilspy-failed|\
        svg-to-png-done|svg-to-png-failed)
            ;;
        *)
            echo "Unknown command: $file"
            rm -f "$COMMANDS_DIR/$file"
            ;;
    esac
done
cd "$EXISTING_PWD"
