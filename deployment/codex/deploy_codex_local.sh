#!/bin/bash

##### JUST RUN ONCE #####
../../base-manifests/deploy_local.sh
kubectl apply -f controlbox_codex.yaml
kubectl apply -f status-backend-relay-codex-services.yaml
##### JUST RUN ONCE #####

kubectl apply -f ../service/status-service-bootstrap.yaml
kubectl rollout status --watch --timeout=30000s statefulset/status-service-bootstrap -n status-go-test

kubectl apply -f status-service-node-codex.yaml
sleep 10
kubectl rollout status --watch --timeout=30000s statefulset/status-service-node-codex -n status-go-test

kubectl apply -f status-backend-relay-codex.yaml
kubectl rollout status --watch --timeout=30000s statefulset/status-backend-relay-codex -n status-go-test
