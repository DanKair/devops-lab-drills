#!/usr/bin/env bash
# Creates branch fix/pipeline in your app repo with the broken pipeline.
if [ ! -d "$APP_REPO/.git" ]; then
  echo "No Git repo at $APP_REPO. Clone your GitLab project there first (gl-01)." >&2
  exit 1
fi
cd "$APP_REPO" || exit 1
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "You have uncommitted changes in $APP_REPO. Commit or stash them first." >&2
  exit 1
fi
git switch -c fix/pipeline 2>/dev/null || git switch fix/pipeline
[ -f .gitlab-ci.yml ] && cp .gitlab-ci.yml .gitlab-ci.yml.bak
cp "$LAB_DIR/broken-ci.yml" .gitlab-ci.yml
echo "On branch fix/pipeline with the broken .gitlab-ci.yml (your original is in .gitlab-ci.yml.bak)."
echo "Commit and push when you are ready: git add -A && git commit -m 'pipeline from other team' && git push -u origin fix/pipeline"
