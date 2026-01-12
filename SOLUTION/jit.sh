#!/bin/bash

# NB we are using bash explicitly for the JIT; it gives us a correct

######################
# Save the shell state

__input="$JIT_INPUT"
unset __cmd_status

if [ -z "$__input" ] || [ ! -f "$__input" ]; then
  echo "jit.sh: missing input script" >&2
  exit 2
fi

# make JIT_POS variables to capture positional variables
JIT_POS_0="$0"
__idx=1
for __arg in "$@"; do
  eval "JIT_POS_${__idx}=\"\$__arg\""
  __idx=$((__idx + 1))
done

# save all current variables
__saved_env="$JIT_INPUT".env
declare -p >"$__saved_env"

####################
# Actually interpose

# !!! expand the script
__expanded=$__input".expanded"
python3 SOLUTION/expand.py "$__input" "$BASH_VERSION" >"$__expanded"

# !!! run the expanded script
. "$__expanded"
__cmd_status=$?

#################################
# Try to clean up after ourselves

# would be nice to un-export... but not for now

# unset JIT_POS_ positional arguments
unset JIT_POS_0
__idx=1
for __arg in "$@"; do
  eval "unset JIT_POS_${__idx}"
  __idx=$((__idx + 1))
done

# hide the evidence
unset __saved_env __expanded __input __idx __arg

# exit with the correct status
(exit "$__cmd_status")
