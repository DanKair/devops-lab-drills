#!/usr/bin/env bash
# shellcheck disable=SC2086
$KUBECTL -n "$K8S_NS" delete deployment/shop service/shop --ignore-not-found
