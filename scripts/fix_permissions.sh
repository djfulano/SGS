#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/SGS}"
APP_USER="${APP_USER:-sgs}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APPLY=0

if [ "${1:-}" = "--apply" ]; then
    APPLY=1
fi

run() {
    if [ "$APPLY" -eq 1 ]; then
        "$@"
    else
        printf 'DRY-RUN:'
        printf ' %s' "$@"
        printf '\n'
    fi
}

for directory in imports config contracts cache backups; do
    if [ -d "$APP_DIR/$directory" ]; then
        run chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/$directory"
        run find "$APP_DIR/$directory" -type d -exec chmod 750 {} \;
        run find "$APP_DIR/$directory" -type f -exec chmod 640 {} \;
    fi
done

if [ -f "$APP_DIR/rede.db" ]; then
    run chown "$APP_USER:$APP_GROUP" "$APP_DIR/rede.db"
    run chmod 640 "$APP_DIR/rede.db"
fi

for file in \
    users.json profiles.json sessions.json login_attempts.json \
    map_config.json backup_config.json; do
    if [ -f "$APP_DIR/config/$file" ]; then
        run chmod 600 "$APP_DIR/config/$file"
    fi
done

printf '%s\n' "Use --apply para executar as alterações acima."
