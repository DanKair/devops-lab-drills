#!/usr/bin/env bash
# shellcheck disable=SC2086
$KUBECTL -n "$K8S_NS" delete deployment api worker report --ignore-not-found
# shellcheck disable=SC2086
$KUBECTL -n "$K8S_NS" delete configmap worker-conf --ignore-not-found
