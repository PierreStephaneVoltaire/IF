#!/usr/bin/env bash
set -euo pipefail
NS="${1:-if-portals}"

kubectl delete functions.fission.io -n "$NS" --all
kubectl delete httptriggers.fission.io -n "$NS" --all
kubectl delete packages.fission.io -n "$NS" --all
kubectl delete environments.fission.io -n "$NS" --all

for i in $(seq 1 30); do
  stuck=$(kubectl get pods -A -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for p in d['items'] if p['metadata'].get('deletionTimestamp')))" 2>/dev/null || echo 0)
  [ "$stuck" = "0" ] && break
  sleep 5
done

for crd in canaryconfigs environments fissiontenants functions httptriggers kuberneteswatchtriggers messagequeuetriggers packages timetriggers; do
  kubectl get "$crd.fission.io" -n "$NS" 2>/dev/null | tail -n +2
done