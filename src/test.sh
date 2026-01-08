#!/usr/bin/env bash

check_test()
{
  passed="$1"

  if [ "$passed" -eq 0 ]; then
      echo "[SUCCESS]"
  else
      echo "[FAILURE]"
  fi
  return "$passed"
}

python3 src/solution.py sh/simple.sh || exit 1 # This will create sh/simple.sh.preprocessed.3
diff <(bash sh/simple.sh.preprocessed.3) <(bash sh/simple.sh) > /dev/null
check_test $?  
