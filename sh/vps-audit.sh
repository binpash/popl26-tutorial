#!/bin/bash

# System info
cat /etc/os-release
uname -r
hostname
uptime -p
uptime -s
lscpu
nproc
free -h
df -h /
curl -s https://api.ipify.org
echo
uptime | awk -F'load average:' '{print $2}' | xargs

# SSH config
grep "^Include" /etc/ssh/sshd_config 2>/dev/null
grep "^PermitRootLogin" /etc/ssh/sshd_config 2>/dev/null
grep "^PasswordAuthentication" /etc/ssh/sshd_config 2>/dev/null
grep "^Port" /etc/ssh/sshd_config 2>/dev/null
sysctl -n net.ipv4.ip_unprivileged_port_start

# Package and service status
dpkg -l | grep -E "unattended-upgrades|fail2ban"
pgrep -x "fail2ban-server"
apt-get -s upgrade 2>/dev/null | grep -P '^\d+ upgraded'

# Auth and process counts
grep "Failed password" /var/log/auth.log 2>/dev/null | wc -l
ps --no-headers -eo cmd | wc -l

# Listening ports
if command -v netstat >/dev/null 2>&1; then
    netstat -tuln | grep LISTEN
else
    ss -tuln | grep LISTEN
fi

# Disk, memory, CPU snapshots
df -h /
free -h
top -bn1 | grep "Cpu(s)"

# Password policy
cat /etc/security/pwquality.conf 2>/dev/null

# Suspicious SUID files
find / \
    \( -path /proc -o -path /sys -o -path /snap -o -path /mnt -o -path /var/lib/docker \) -prune -o \
    -type f -perm -4000 -print 2>/dev/null
