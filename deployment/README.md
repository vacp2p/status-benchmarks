# Deployment

Deployment files that will be used for the deployments in the experiments.

## light
[Definition](https://www.notion.so/Chat-Protocol-Benchmarks-1938f96fb65c80d8b22fdf641c5ff003?source=copy_link#1998f96fb65c802095e6fc894dc0b4fe)

A light node, is a status-backend node that runs in “light mode” (edge node in Waku concept).
Which means it uses Waku Peer Exchange for discovery, light push to send messages,
filter to receive live messages and store to retrieve historical messages.
It does not provide services.


## relay
[Definition](https://www.notion.so/Chat-Protocol-Benchmarks-1938f96fb65c80d8b22fdf641c5ff003?source=copy_link#1998f96fb65c8014bf0af42ce2645fa9)

A relay node, is a status-backend node that runs in “relay mode”.
Which means it uses discv5 and Waku Peer Exchange for discovery (rendezvous wip),
relay to send and receive live messages, store as a client to retrieved historical messages,
and provide filter, light push and waku peer exchanges services to other (light/edge) nodes.


## service
[Definition](https://www.notion.so/Chat-Protocol-Benchmarks-1938f96fb65c80d8b22fdf641c5ff003?source=copy_link#1998f96fb65c80c4b972fb560bd0f6f3)
A service node, is a wakunode2 (nwaku) node that runs service, similar to the Status prod fleet.
In this context, we can assume it provides Waku peer exchange, light push, filter and store services.
It uses discv5 for peer discovery. 
We may get into details to better reproduce fleet setup (boot and store nodes are separate,
several nwaku store nodes are connected to same posgres db), right now each store node has it's own db.

