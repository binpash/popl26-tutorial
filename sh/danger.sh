#!/bin/bash

touch /tmp/DELETEME{1,2,3,4,5,6}

# statically catchable
rm -rf /tmp/DELETEME1 # /home

# will not be put in a try
cat /tmp/DELETEME2

cmd="echo"
args="hi"
# will not be put in a try (expansion saves us just-in-time)
"$cmd" "$args" /tmp/DELETEME3 # /home

cmd="rm"
args="-rf"
# will be put in a try (expansion detects it just-in-time)
"$cmd" "$args" /tmp/DELETEME4 # /home

# will conservatively be put in a try (can't safely expand with assignment)
"${cmd2=echo}" -rf /tmp/DELETEME5 # /home

# will (correctly) be put in a try (but not because we expanded)
"${cmd3=rm}" -rf /tmp/DELETEME6 # /home
