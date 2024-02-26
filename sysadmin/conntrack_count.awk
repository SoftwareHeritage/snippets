#!/usr/bin/awk -f

BEGIN{
	counters["pods_to_service_dns"]=0
	counters["node_to_node_vxlan"]=0
	counters["pods_to_pods_storage"]=0
	counters["pods_to_microsoft_net20_https"]=0
	counters["pods_to_microsoft_net52_https"]=0
	counters["pods_to_kafka"]=0
	counters["node_to_kafka"]=0
	counters["pods_to_postgres"]=0
	counters["node_to_amazon_https"]=0
	counters["pods_to_swh_proxy_https"]=0
	counters["node_to_pods_objstorage"]=0
	counters["localhost_to_localhost_8125"]=0
	counters["pods_to_service_statsd"]=0
	counters["node_to_node_metallb"]=0
	counters["node_to_node_icmp"]=0
	counters["node_to_external_ntp"]=0
	counters["localhost_to_localhost_ntp"]=0
	format="%-35s %s\n"
	dns_names["0.0.0.0"]="all"
	dns_sources["0.0.0.0"]=0
}
{
if ($4 ~ /^src=10\.42/ && $5 ~ /^dst=10\.43/ && $7 == "dport=53")
	{
	counters["pods_to_service_dns"]+=1
	split($4,a,"=")
	source=a[2]
	if (dns_sources[source] > 0)
		{dns_sources[source]+=1}
	else
		{
		dns_sources[source]=1
		kube = "/var/lib/rancher/rke2/bin/kubectl \
		--kubeconfig /var/lib/rancher/rke2/agent/kubelet.kubeconfig \
		get pods -A --field-selector spec.nodeName=saam \
		--field-selector status.podIP="source" -o name"
		kube | getline pod_name
		dns_names[source]=pod_name
		close(kube)
		}
	}
if ($4 ~ /^src=192\.168\.100/ && $5 ~ /^dst=192\.168/ && $7 == "dport=4789")
	{
	counters["node_to_node_vxlan"]+=1
	}
if ($5 ~ /^src=10\.42/ && $6 ~ /^dst=10\.42/ && $8 == "dport=5002")
	{
	counters["pods_to_pods_storage"]+=1
	}
if ($5 ~ /^src=10\.42/ && $6 ~ /^dst=20\.(60|150|209)/ && $8 == "dport=443")
	{
	counters["pods_to_microsoft_net20_https"]+=1
	}
if ($5 ~ /^src=10\.42/ && $6 ~ /^dst=52\.239/ && $8 == "dport=443")
	{
	counters["pods_to_microsoft_net52_https"]+=1
	}
if ($5 ~ /^src=10\.42/ && $6 ~ /^dst=192\.168\.100\.20(1|2|3|4)/ && $8 == "dport=9092")
	{
	counters["pods_to_kafka"]+=1
	}
if ($5 ~ /^src=192\.168\.100/ && $6 ~ /^dst=192\.168\.100\.20(1|2|3|4)/ && $8 == "dport=9094")
	{
	counters["node_to_kafka"]+=1
	}
if ($5 ~ /^src=10\.42/ && $6 ~ /^dst=192\.168\.100\.212/ && $8 == "dport=5432")
	{
	counters["pods_to_postgres"]+=1
	}
if ($5 ~ /^src=192\.168\.100/ && $6 ~ /^dst=(54\.231|16\.182)/ && $8 == "dport=443")
	{
	counters["node_to_amazon_https"]+=1
	}
if ($5 ~ /^src=10\.42\./ && $6 ~ /^dst=128\.93\.166\.10/ && $8 == "dport=443")
	{
	counters["pods_to_swh_proxy_https"]+=1
	}
if ($5 ~ /^src=192\.168\.100/ && $6 ~ /^dst=10\.42/ && $8 == "dport=5003")
	{
	counters["node_to_pods_objstorage"]+=1
	}
if ($4 ~ /^src=127\.0/ && $5 ~ /^dst=127\.0/  && $7 == "dport=8125")
	{
	counters["localhost_to_localhost_8125"]+=1
	}
if ($4 ~ /^src=10\.42/ && $5 ~ /^dst=10\.43/  && $7 == "dport=9125")
	{
	counters["pods_to_servivce_statsd"]+=1
	}
if ($4 ~ /^src=192\.168\.100/ && $5 ~ /^dst=192\.168/  && $7 == "dport=7946")
	{
	counters["node_to_node_metallb"]+=1
	}
if ($1 == "icmp" && $4 ~ /^src=192\.168\.100/ && $5 ~ /^dst=192\.168/)
	{
	counters["node_to_node_icmp"]+=1
	}
if ($4 ~ /^src=192\.168\.100/ && $5 !~ /^dst=(192\.168|127\.0|10.4[23])/  && $7 == "dport=123")
	{
	counters["node_to_external_ntp"]+=1
	}
if ($4 ~ /^src=(127\.0|::1)/ && $5 ~ /^dst=(127\.0|::1)/  && $7 == "dport=123")
	{
	counters["localhost_to_localhost_ntp"]+=1
	}
if ($1 != "icmp" && $6 !~ /^dst=(16\.182|20|52|54\.231|128\.93\.166)\./ &&
	$7 !~ /dport=(53|4789|8125|9125|7946|123)/ &&
	$8 !~ /dport=(|5432|9092|9094|5002|5003)/)
	{
	print
	}
}
END{
"date" | getline date
close("date")
printf "\n## %s\n### CONNTRACK ENTRIES\n", date
for (i in counters)
	printf format, i, counters[i]
print "\n### DNS ENTRIES BY PODS (>10k)"
for (i in dns_sources)
    if (dns_sources[i] > 10000)
        {printf "%s %-16s %s\n", dns_names[i], i, dns_sources[i]}
}

