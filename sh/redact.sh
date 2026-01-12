#!/bin/sh

usage() {
    printf "Usage: redact.sh [file]\n"
    exit 2
}

if [ "$#" -ne 1 ]
then
    usage
fi

[ -f "$1" ] || { echo "redact.sh: '$1' is not a regular file"; exit 1; }

grep -v "# REMOVE" "$1" | sed -E 's/^(\s*).*# REPLACE (.*)$/\1\2/'

