
kubectl delete -f ../service/status-service-bootstrap.yaml
kubectl delete -f status-service-node-codex.yaml
kubectl delete -f status-backend-relay-codex.yaml

kubectl delete -f ../../base-manifests/anvil-statefulset.yaml
kubectl delete -f controlbox_codex.yaml
