#!/bin/sh
# Claude Opus 5.5 играет месяц из Claude Code в мире ny2: тот же текст вечера и та же Проверка, что у моделей в сети.
#   bench/opus.sh start|act|result <scenario> <place> <team> <seed> ['<json>']
cd "$(dirname "$0")/.." && ZOO_WORLD=ny2 ZOO_TAG=ny2opus ZOO_MODEL_TAG="claude-code:claude-opus-5.5" exec python3 bench/closed.py "$@"
