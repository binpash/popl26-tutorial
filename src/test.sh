#!/usr/bin/env bash

testing() {
    echo "======= TESTING JIT $1"
}

FAILURES=0
check_script() {
    script="$1"

    if ! [ -f "$script" ]
    then
        echo "[MISSING] $script"
        return
    fi

    if git diff --word-diff --no-index -- <(bash sh/simple.sh) <(bash "$script")
    then
        echo "[SUCCESS] $script produced identical output"
    else
        cat "$script"
        echo "[FAILURE] $script produced differing output"
        : $(( FAILURES+=1 ))
    fi
}

python3 src/solution.py sh/simple.sh || exit 1 # generates will create sh/simple.sh.preprocessed.3

testing 1
cat sh/simple.sh.preprocessed.1

testing 2
check_script sh/simple.sh.preprocessed.2

testing 3
check_script sh/simple.sh.preprocessed.3

exit "$FAILURES"