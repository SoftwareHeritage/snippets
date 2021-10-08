
# Goal

- autoscaling workers depending on repositories to load and allocated resources.

# keda

Install KEDA - K(ubernetes) E(vents)-D(riven) A(utoscaling):
```
$ helm repo add kedacore https://kedacore.github.io/charts
$ helm repo update
swhworker@poc-rancher:~$ kubectl create namespace keda
namespace/keda created
swhworker@poc-rancher:~$ helm install keda kedacore/keda --namespace keda
NAME: keda
LAST DEPLOYED: Fri Oct  8 09:48:40 2021
NAMESPACE: keda
STATUS: deployed
REVISION: 1
TEST SUITE: None
```
source: https://keda.sh/docs/2.4/deploy/
