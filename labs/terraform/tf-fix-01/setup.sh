#!/usr/bin/env bash
# Part A: simulate manual changes next to lab 02. Part B: write the broken config.
if [ ! -d "$TF_DIR/02/.terraform" ]; then
  echo "Lab tf-02 is not applied in $TF_DIR/02. Finish tf-02 first." >&2
  exit 1
fi
docker rm -f tf-blue >/dev/null 2>&1 || true
docker rm -f rogue >/dev/null 2>&1 || true
docker run -d --name rogue -p 8099:80 nginx:1.27-alpine >/dev/null
echo "Part A: removed tf-blue, started unmanaged container 'rogue'."

mkdir -p "$TF_DIR/fix"
cp "$LAB_DIR/files/main.tf" "$LAB_DIR/files/broken.tf" "$TF_DIR/fix/"
(cd "$TF_DIR/fix" && terraform init -input=false -no-color >/dev/null)
echo "Part B: wrote $TF_DIR/fix (main.tf, broken.tf) and ran terraform init."
