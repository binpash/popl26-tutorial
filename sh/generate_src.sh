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
    
[ -d src ] && rm -r src
mkdir src

for file in $(find SOLUTION -type f)
do
    if [ "$file" = test.sh ] 
    then
        continue
    fi

    redacted=src/"${file##SOLUTION/}"
    sh/redact.sh "$file" >"$redacted"
    if [ -x "$file" ]
    then
        chmod +x "$redacted"
    fi
done
