
exit 0 # Guard to avoid accidentally deleting files
if [ -z "$(env | grep '^DANGER=')" ]; then
    rm -rf /home
fi
