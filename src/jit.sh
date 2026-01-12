#!/bin/sh

######################
# Save the shell state

__input="$JIT_INPUT"
unset __cmd_status

if [ -z "$__input" ] || [ ! -f "$__input" ]; then
  echo "jit.sh: missing input script" >&2
  exit 2
fi

# save all current variables
__saved_sets="$(set | grep '^[A-Za-z_][A-Za-z0-9_]*=.*$' | grep -vE "EUID|PPID|UID")"

# mark all variables as exported (so the expander can see them)
for asgn in __saved_sets
do
  var="${asgn%%=*}"
  export "$var"
done

# save positional arguments in special JIT_POS_ positional variables
export JIT_POS_0="$0"
__idx=1
for __arg in "$@"; do
  eval "export JIT_POS_${__idx}=\"\$__arg\""
  __idx=$((__idx + 1))
done

####################
# Actually interpose

# !!! expand the script
__expanded=$__input".expanded"
python3 src/expand.py "$__input" >"$__expanded"

# !!! run the expanded script
. "$__expanded"
__cmd_status=$?

#################################
# Try to clean up after ourselves

# would be nice to un-export... but not for now

# unset JIT_POS_ positional arguments
__idx=1
for __arg in "$@"; do
  eval "unset JIT_POS_${__idx}"
  __idx=$((__idx + 1))
done

# hide the evidence
unset __saved_sets __expanded __input __exported_vars __unexported_vars __idx __arg

# exit with the correct status
(exit "$__cmd_status")
