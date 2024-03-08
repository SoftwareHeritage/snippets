#!/bin/bash

set -e

if [ $# -lt 3 ]; then
	echo usage: "$0" CLUSTER_NAME CONFIGS_FILE SECRETS_FILE
	exit 2
fi

CLUSTER="$1"
CONFIGS_FILE="$2"
SECRETS_FILE="$3"
KUBE_NAMESPACE=rook-ceph

RBD_POOL="k8s.${CLUSTER}.rbd"
CEPHFS_FS="k8s.${CLUSTER}"

ceph osd pool create "${RBD_POOL}"
rbd pool init "${RBD_POOL}"

ceph fs volume create "${CEPHFS_FS}"

for pool in "${RBD_POOL}" "cephfs.${CEPHFS_FS}.data" "cephfs.${CEPHFS_FS}.meta"; do
  ceph osd pool set "${pool}" pg_autoscale_mode warn
done

# CSI node access (maps images)
ceph auth get-or-create \
  "client.k8s.${CLUSTER}.csi-rbd-node" \
  mon "profile rbd, allow command 'osd blocklist'" \
  osd "profile rbd pool=${RBD_POOL}" >&2

# CSI provisioner (creates/deletes images)
ceph auth get-or-create \
  "client.k8s.${CLUSTER}.csi-rbd-provisioner" \
  mgr "profile rbd pool=${RBD_POOL}" \
  mon "profile rbd, allow command 'osd blocklist'" \
  osd "profile rbd pool=${RBD_POOL}" >&2

ceph auth get-or-create \
  "client.k8s.${CLUSTER}.csi-cephfs-provisioner" \
  mgr "allow rw" \
  mon "allow r, allow command 'osd blocklist'" \
  osd "allow rw tag cephfs metadata=k8s.${CLUSTER}" >&2

ceph auth get-or-create \
  "client.k8s.${CLUSTER}.csi-cephfs-node" \
  mds "allow rw" \
  mgr "allow rw" \
  mon "allow r, allow command 'osd blocklist'" \
  osd "allow rw tag cephfs *=k8s.${CLUSTER}" >&2

ceph auth get-or-create \
  "client.k8s.${CLUSTER}.healthchecker" \
  mgr "allow command config" \
  mon "allow r, allow command quorum_status, allow command version" \
  osd "profile rbd-read-only, allow rwx pool=default.rgw.meta, allow r pool=.rgw.root, allow rw pool=default.rgw.control, allow rx pool=default.rgw.log, allow x pool=default.rgw.buckets.index" >&2

function ceph_secret () {
	local secret_name=$1
	local ceph_user=$2
	local ceph_client="client.${ceph_user#client.}"
	local secret_type=$3

	cat <<- EOF
	---
	apiVersion: v1
	kind: Secret
	type: kubernetes.io/rook
	metadata:
	  name: $secret_name
	  namespace: ${KUBE_NAMESPACE}
	stringData:
	  ${secret_type}ID: ${ceph_user}
	  ${secret_type}Key: $(ceph auth get-key "${ceph_client}")
	EOF
}

umask 0077

{
  # This secret needs a client. prefix for the username, but the others don't support it...
  ceph_secret admin-secret client.k8s.${CLUSTER}.healthchecker user

  ceph_secret rook-csi-rbd-provisioner "k8s.${CLUSTER}.csi-rbd-provisioner" user
  ceph_secret rook-csi-rbd-node "k8s.${CLUSTER}.csi-rbd-node" user
  ceph_secret rook-csi-cephfs-provisioner "k8s.${CLUSTER}.csi-cephfs-provisioner" admin
  ceph_secret rook-csi-cephfs-node "k8s.${CLUSTER}.csi-cephfs-node" admin

  cat <<- EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: rook-ceph-mon
  namespace: ${KUBE_NAMESPACE}
stringData:
  cluster-name: ${KUBE_NAMESPACE}
  fsid: $(ceph fsid)
  admin-secret: admin-secret
  mon-secret: mon-secret
  ceph-username: client.k8s.${CLUSTER}.healthchecker
  ceph-secret: $(ceph auth get-key "client.k8s.${CLUSTER}.healthchecker")
EOF

} >"${SECRETS_FILE}"

ceph_quorum_status="$(ceph quorum_status --format json)"

umask 0022

cat >"${CONFIGS_FILE}" <<- EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: rook-ceph-mon-endpoints
  namespace: ${KUBE_NAMESPACE}
  finalizers:
    - ceph.rook.io/disaster-protection
data:
  data: "$(echo -n "$ceph_quorum_status" | jq -r '[.monmap.mons[]| .name + "=" + .public_addr | sub("/0"; "")] | join(",")')"
  mapping: '{}'
  maxMonId: '0'
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
parameters:
  clusterID: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/node-stage-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/fstype: ext4
  pool: k8s.${CLUSTER}.rbd
  imageFeatures: layering
  imageFormat: "2"
provisioner: rook-ceph.rbd.csi.ceph.com
reclaimPolicy: Delete
volumeBindingMode: Immediate
allowVolumeExpansion: true
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cephfs
parameters:
  clusterID: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: ${KUBE_NAMESPACE}
  csi.storage.k8s.io/fstype: ext4
  pool: cephfs.k8s.${CLUSTER}.data
  fsName: k8s.${CLUSTER}
  imageFeatures: layering
  imageFormat: "2"
provisioner: rook-ceph.cephfs.csi.ceph.com
reclaimPolicy: Delete
allowVolumeExpansion: true
EOF
