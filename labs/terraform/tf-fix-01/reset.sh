#!/usr/bin/env bash
docker rm -f rogue >/dev/null 2>&1 || true
rm -rf "$TF_DIR/fix"
echo "Removed rogue and $TF_DIR/fix. Run terraform apply in $TF_DIR/02 to restore tf-blue."
