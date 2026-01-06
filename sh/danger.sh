#!/bin/bash

# shellcheck disable=SC2317
touch /tmp/DELETEME

cmd="rm"
args="-rf"
"$cmd" "$args" /tmp/DELETEME # /home
