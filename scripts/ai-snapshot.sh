#!/usr/bin/env bash
set -e

if ! git rev-parse --git-dir > /dev/null 2>&1; then
  exit 0
fi

git add -A

if ! git diff --cached --quiet; then
  git commit -m "AI snapshot $(date '+%Y-%m-%d %H:%M:%S')" >/dev/null 2>&1
fi
