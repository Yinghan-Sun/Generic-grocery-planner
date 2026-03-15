#!/usr/bin/env bash
set -e

# 1 git snapshot
./scripts/ai-snapshot.sh

# 2 filesystem snapshot
~/.ai-safe/snapshot-project.sh "$(pwd)"

# 3 delete
rm "$@"
