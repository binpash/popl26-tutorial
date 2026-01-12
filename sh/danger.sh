#!/bin/bash

touch /tmp/DELETEME

# statically catchable
#rm -rf /tmp/DELETEME # /home

# will not be put in a try
cat /tmp/DELETEME

cmd="echo"
args="hi"
# will not be put in a try (expansion saves us just-in-time)
"$cmd" "$args" /tmp/DELETEME # /home

cmd="rm"
args="-rf"
# will be put in a try (expansion detects it just-in-time)
#"$cmd" "$args" /tmp/DELETEME # /home

# will conservatively be put in a try (can't safely expand with assignment)
"${cmd2=echo}" -rf /tmp/DELETEME # /home

# will (correctly) be put in a try (but not because we expanded)
#"${cmd3=rm}" -rf /tmp/DELETEME # /home
