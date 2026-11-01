#!/usr/bin/env bash
# shellcheck disable=SC2086
$KUBECTL create namespace "$K8S_NS" --dry-run=client -o yaml | $KUBECTL apply -f -
# shellcheck disable=SC2086
$KUBECTL -n "$K8S_NS" delete deployment api worker report --ignore-not-found
# shellcheck disable=SC2086
$KUBECTL -n "$K8S_NS" apply -f - < "$LAB_DIR/broken.yaml"
echo "Applied broken api, worker and report to namespace $K8S_NS."
