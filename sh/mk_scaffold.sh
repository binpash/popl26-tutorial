#!/bin/sh

if ! [ -d src ]
then
    printf "Usage: ./src/mk_scaffold.sh from the root of the repo\n"
    exit 2
fi

if ! [ -f sh/redact.sh ]
then
    printf "mk_scaffold.sh: couldn't find sh/redact.sh\n"
    exit 2
fi
    
[ -d scaffold ] && rm -r scaffold
mkdir scaffold

for file in $(find src -type f)
do
    if [ "$file" = test.sh ]
    then
        continue
    fi

    redacted=scaffold/"${file##src/}"
    sh/redact.sh "$file" >"$redacted"
    if [ -x "$file" ]
    then
        chmod +x "$redacted"
    fi
done
