# Kubernetes 101

Demos for https://hedgedoc.softwareheritage.org/WHMy1n08TASpdzz6rflWMA?both


## Prerequisites

- k3s (https://k3s.io)
- Deploy a registry
```
kubectl create namespace registry
kubectl apply --namespace registry registry
```
- Add the entry `registry.demo` pointing to your cluster in your local `/etc/hosts` and on each node of your cluster
- on each node, create the file `/etc/rancher/k3s/registries.yaml` with this content:
```
mirrors:
  registry.demo:
    endpoint:
      - "http://registry.demo/v2/"
```
- restart k3s

- build the demo images
```
cd demo-flask
./build.sh
```

- for the distributed storage, deploy longhorn (https://longhorn.io)
```
cd longhoen
./install.sh
```

## demos

Follow the speaker notes on the presentation
