# diagram.py
from diagrams import Cluster, Diagram
from diagrams.azure.compute import ContainerInstances, KubernetesServices, VM
from diagrams.azure.network import (
    LoadBalancers,
    NetworkInterfaces,
    PrivateEndpoints,
    PrivateLinkServices,
    PublicIpAddresses,
    ReservedIpAddressesClassic,
    ServiceEndpointPolicies,
    VirtualNetworkClassic,
)
from diagrams.azure.general import Resourcegroups
from diagrams.azure.storage import StorageAccounts
from diagrams.azure.network import PrivateEndpoints
from diagrams.azure.network import PrivateLinkServices

with Diagram("Gitlab infrastructure", show=False, outformat="svg"):
    rg = Cluster("zone-gitlab-instance resource group")
    rg_internal = Cluster("zone-gitlab-instance-internal resource group")

    internalLBEndpoint = None
    apiEndpoint = None

    with rg:
        aks = KubernetesServices("zone-gitlab-instance kubernetes")
        storageAccount = StorageAccounts("Storage Account")
        lbLinkService = PrivateLinkServices("Internal LoadBalancer Link Service")
        internalLBEndpoint = PrivateEndpoints("Internal LoadBalancer endpoint")
        apiEndpoint = PrivateEndpoints("Kubernetes API endpoint")

        aks - apiEndpoint
        lbLinkService - internalLBEndpoint

    with rg_internal:
        np = ContainerInstances("Node Pool")

        inboundPublicIp = PublicIpAddresses("Inbound public Ip")
        outboundPublicIp = PublicIpAddresses("Outbound public Ip")

        publicLB = LoadBalancers("kubernetes LB")

        aks >> np

        publicLB - outboundPublicIp
        publicLB - inboundPublicIp

        with Cluster("Internal Virtual network 10.0.0.0/8"):
            internalIp = ReservedIpAddressesClassic("Internal Kube API IP")
            internalLB = LoadBalancers("kubernetes-internal LB")
            kubeApiInterface = NetworkInterfaces("Kube API Interface")

            VMs = VM("Nodes[1-5]")

            np >> VMs
            internalLB >> VMs

            aks - publicLB
            publicLB - VMs

            internalLB - internalIp
            # internalLB << internalIp
            aks - kubeApiInterface
            aks - internalLB

            privateLinkServiceLBInterface = NetworkInterfaces("Private Link Service Interface")
            privateLinkServiceLBInterface - internalLB
            lbLinkService - privateLinkServiceLBInterface

    with Cluster("swh-resource Resource Group"):
        with Cluster("swh-net/default Virtual Network (192.168.200.x/24)"):
            internalLBInterface = NetworkInterfaces("LB VLAN1300")
            apiInternalInterface = NetworkInterfaces("Kubernetes API VLAN1300")

            internalLBEndpoint - internalLBInterface
            apiEndpoint - apiInternalInterface

