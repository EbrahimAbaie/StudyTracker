#!/bin/sh
set -eu

mkdir -p /app/data /app/data/backups
if [ "$(id -u)" = '0' ]; then
    chown -R appuser:appuser /app/data
    exec python -c 'import os, pwd, sys; user = pwd.getpwnam("appuser"); os.setgroups([]); os.setgid(user.pw_gid); os.setuid(user.pw_uid); os.execv("/app/entrypoint.sh", ["/app/entrypoint.sh", *sys.argv[1:]])' "$@"
fi

if [ -z "${SECRET_KEY:-}" ]; then
    if [ ! -s /app/data/.secret-key ]; then
        (umask 077; python -c 'import secrets; print(secrets.token_urlsafe(64))' > /app/data/.secret-key)
    fi
    SECRET_KEY="$(cat /app/data/.secret-key)"
    export SECRET_KEY
fi
python manage.py migrate --noinput
python manage.py verify_storage
exec "$@"
