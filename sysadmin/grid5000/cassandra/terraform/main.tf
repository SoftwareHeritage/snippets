provider "grid5000" {
  # Uses Restfully credentials
  restfully_file = pathexpand("~/.grid5000.yml")
}

resource "grid5000_job" "reservation" {
  name      = "swh"
  site      = var.site
  command   = "sleep ${var.sleep_time}"
  resources = "{(type='disk' or type='default') AND cluster='${var.cluster}'}/nodes=${var.total_node_count},walltime=${var.walltime}"
  types     = ["cosystem", "container"]
}

resource "grid5000_job" "cassandra" {
  name      = "swh"
  site      = var.site
  command   = "sleep ${var.sleep_time}"
  resources = "/nodes=${var.cassandra_node_count},walltime=${var.cassandra_walltime}"
  types     = ["inner=${grid5000_job.reservation.id}", "deploy"]
}

resource "grid5000_deployment" "cassandra_deployment" {
  site        = grid5000_job.cassandra.site
  environment = "debian10-x64-base"
  nodes       = grid5000_job.cassandra.assigned_nodes
  key         = file("~/.ssh/grid5000.pub")
}

resource "null_resource" "cassandra_install" {
  depends_on = [grid5000_deployment.cassandra_deployment]

  count = var.cassandra_node_count
  connection {
    host        = element(sort(grid5000_deployment.cassandra_deployment.nodes), var.cassandra_node_count)
    type        = "ssh"
    user        = "root"
    private_key = file("~/.ssh/id_rsa")
  }

  provisioner "file" {
    source      = "../ansible"
    destination = "/root/ansible"
  }

  provisioner "remote-exec" {
    inline = [
      "/root/ansible/ansible.sh",
    ]
  }
}


output "global_job_id" {
  value = grid5000_job.reservation.id
}

output "all_nodes" {
  value = grid5000_job.reservation.assigned_nodes
}

output "cassandra_job_id" {
  value = grid5000_job.cassandra.id
}

output "cassandra_nodes" {
  value = grid5000_job.cassandra.assigned_nodes
}
