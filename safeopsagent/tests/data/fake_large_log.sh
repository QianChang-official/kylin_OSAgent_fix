#!/bin/bash
# Generate fake large log files for testing disk_full RCA scenario
# Usage: ./fake_large_log.sh [size_in_MB] [target_dir]

SIZE=${1:-100}  # default 100MB
DIR=${2:-/tmp/fake_log_dir}

mkdir -p "$DIR"

# Create large log file with dd
dd if=/dev/zero of="$DIR/fake_access.log" bs=1M count=$SIZE 2>/dev/null

# Create some smaller log files
for i in $(seq 1 5); do
    dd if=/dev/zero of="$DIR/fake_app${i}.log" bs=1M count=10 2>/dev/null
done

echo "Created fake log files in $DIR:"
ls -lh "$DIR"

# Cleanup reminder
echo ""
echo "To clean up: rm -rf $DIR"
