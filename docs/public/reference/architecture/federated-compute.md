# Federated compute through connected providers

repo2ree is designed to coordinate compute supplied by different resource
owners without taking possession of their infrastructure credentials. A private
user, laboratory, university, facility, or cloud account installs a repo2ree
provider inside its own boundary. That provider connects outward to a repo2ree
API instance and makes approved compute capabilities available for REE
operations.

![Private, university, institutional, and cloud resources connect to a repo2ree control plane through owner-installed providers](assets/federated-compute.svg)

## The provider is a gateway

A provider is not itself the compute resource. It translates repo2ree capacity
requests into calls to the runtime or scheduler available inside its
environment. That may be a local Docker host, an institutional cluster,
specialist hardware, or a cloud-managed service.

The provider advertises the capabilities that its owner chooses to expose. The
control plane can then request capacity from an eligible provider, route work
to the workbench that results, track the run, and receive logs, evidence, and
artifacts.

## The resource boundary stays intact

Infrastructure access remains local to the provider. The repo2ree API does not
need the owner's cloud keys, kubeconfig, scheduler credentials, or
container-runtime socket. Resource owners continue to control:

- Provider registration and revocation
- Admission policy, quotas, and scheduling
- Available hardware and runtime classes
- Infrastructure credentials and network access

The outbound connection also avoids requiring a university, laboratory, or
private network to expose an inbound endpoint.

## Current and intended support

The current provider drives Docker on a single host: it creates and removes
workbenches there and does not schedule across machines. Scheduler, cluster,
and cloud adapters shown in the diagram are intended extension points for
federated compute; they are not all implemented today.
