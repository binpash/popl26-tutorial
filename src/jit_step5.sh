#!/bin/sh

__input="$JIT_INPUT"

if [ -z "$__input" ] || [ ! -f "$__input" ]; then
  echo "jit.sh: missing input script" >&2
  exit 2
fi

# Save and export all current set variables
__saved_sets="$(set | grep '^[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_./-]*$' | grep -vE "EUID|PPID|UID")"
__exported_vars="$(echo "$__saved_sets" | sed 's/^/export /')"
eval "$__exported_vars"

# Special handling for positional arguments
__idx=1
for __arg in "$@"; do
  eval "export JIT_POS_${__idx}=\"\$__arg\""
  __idx=$((__idx + 1))
done

__expanded=$__input".expanded"
echo "Will execute this script"
cat "$__input"
. "$__input"

# Restore previous shell state
__unexported_vars="$(echo "$__saved_sets" | sed 's/^/unset /' | sed 's/=/ /')"
eval "$__unexported_vars"
eval "$__saved_sets"
__idx=1
for __arg in "$@"; do
  eval "unset JIT_POS_${__idx}"
  __idx=$((__idx + 1))
done
unset __saved_sets __expanded __input __exported_vars __unexported_vars __idx __arg
