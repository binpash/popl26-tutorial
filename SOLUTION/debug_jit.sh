#!/bin/sh

__input="$JIT_INPUT"
unset __cmd_status

if [ -z "$__input" ] || [ ! -f "$__input" ]; then
  echo "debug_jit.sh: missing input script" >&2
  exit 2
fi

# debug line
printf "+ " >&2
cat "$__input" >&2

# actually run line
. "$__input"

# preserve exit status, hide vars
__cmd_status=$?
unset __input JIT_INPUT
(exit "$__cmd_status")
