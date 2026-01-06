# shellcheck disable=SC2317

exit 0 # Guard to avoid accidentally deleting files
cmd="rm"
if [ -z "$(env | grep '^DANGER=')" ]; then
    "$cmd" -rf /home
fi
