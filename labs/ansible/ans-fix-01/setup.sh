#!/usr/bin/env bash
# Writes the broken playbook and removes the old status page so the handler path is exercised.
mkdir -p "$ANSIBLE_DIR"
if [ -f "$ANSIBLE_DIR/status.yml" ]; then
  cp "$ANSIBLE_DIR/status.yml" "$ANSIBLE_DIR/status.yml.bak"
  echo "Backed up your old status.yml to status.yml.bak"
fi
cp "$LAB_DIR/status.yml" "$ANSIBLE_DIR/status.yml"
# shellcheck disable=SC2086
ssh $SSH_OPTS "$NODE1" "sudo rm -f /var/www/html/status.html" || echo "warning: could not reach $NODE1"
echo "Wrote $ANSIBLE_DIR/status.yml"
