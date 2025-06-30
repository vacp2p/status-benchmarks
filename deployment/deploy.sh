KUBECONFIG="$HOME/.kube/sapphire.yaml"

kubectl --kubeconfig $KUBECONFIG apply -f service/status-service-bootstrap.yaml
kubectl --kubeconfig $KUBECONFIG rollout status --watch --timeout=30000s statefulset/status-service-bootstrap -n status-go-test

kubectl --kubeconfig $KUBECONFIG apply -f service/status-service-node.yaml
kubectl --kubeconfig $KUBECONFIG rollout status --watch --timeout=30000s statefulset/status-service-node -n status-go-test

kubectl --kubeconfig $KUBECONFIG apply -f relay/status-backend-relay.yaml
kubectl --kubeconfig $KUBECONFIG rollout status --watch --timeout=30000s statefulset/status-backend-relay -n status-go-test

kubectl --kubeconfig $KUBECONFIG apply -f light/status-backend-light.yaml
kubectl --kubeconfig $KUBECONFIG rollout status --watch --timeout=30000s statefulset/status-backend-light -n status-go-test
