#!/usr/bin/env bash
# Compatibility shim: the Makefile target `restore-drill` calls deploy/scripts/restore_drill.sh
# (underscore) while the brief names the script restore-drill.sh. Both spellings work;
# all logic (and --dry-run) lives in restore-drill.sh.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/restore-drill.sh" "$@"
