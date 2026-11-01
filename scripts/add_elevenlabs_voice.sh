#!/usr/bin/env bash
# Add ElevenLabs voices to the voice list (backend/core/elevenlabs_voices.json) by voice id.
#
# Looks each voice up in your ElevenLabs account, then in the public Voice Library, and stores
# name, gender, age, accent and description. A voice that is already listed is refreshed; its
# hand-written "good_for" hints are kept unless --good-for is given.
#
# Usage:
#   scripts/add_elevenlabs_voice.sh VOICE_ID [VOICE_ID ...] [--good-for "witch, elder"] [--dry-run]
#   scripts/add_elevenlabs_voice.sh VOICE_ID --output data/voices/elevenlabs_voices.json
#
# Needs ELEVENLABS_API_KEY in the environment or in .env (or pass --api-key KEY).
set -euo pipefail

if [[ $# -eq 0 || "$1" == "-h" || "$1" == "--help" ]]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Voice ids come first; every option after them is passed through unchanged.
voice_ids=()
while [[ $# -gt 0 && "$1" != --* ]]; do
  voice_ids+=("$1")
  shift
done
if [[ ${#voice_ids[@]} -eq 0 ]]; then
  echo "Give at least one voice id before the options." >&2
  exit 2
fi

if command -v poetry >/dev/null 2>&1; then
  runner=(poetry run python)
elif command -v python3 >/dev/null 2>&1; then
  runner=(python3)
else
  runner=(python)
fi

exec "${runner[@]}" scripts/sync_elevenlabs_voices.py --add "${voice_ids[@]}" "$@"
