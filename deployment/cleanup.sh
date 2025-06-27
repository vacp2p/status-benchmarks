KUBECONFIG="$HOME/.kube/sapphire.yaml"

kubectl --kubeconfig $KUBECONFIG delete -f service/status-service-bootstrap.yaml
kubectl --kubeconfig $KUBECONFIG delete -f service/status-service-node.yaml
kubectl --kubeconfig $KUBECONFIG delete -f relay/status-backend-relay.yaml
kubectl --kubeconfig $KUBECONFIG delete -f light/status-backend-light.yaml

#kubectl --kubeconfig $KUBECONFIG delete -f ../base-manifests/anvil-statefulset.yaml
#kubectl --kubeconfig $KUBECONFIG delete -f ../base-manifests/snt-contract-deployment.yaml
#kubectl --kubeconfig $KUBECONFIG delete -f ../base-manifests/snt-communities-deployment.yaml

# kubectl --kubeconfig $KUBECONFIG delete -f ../controlbox/controlbox.yaml
