provider "grid5000" {
  # Uses Restfully credentials
  restfully_file = pathexpand("~/.grid5000.yml")
}

resource "grid5000_job" "cassandra" {
  name      = "terraform"
  site      = "lille"
  command   = "sleep 1h"
  resources = "{\"cluster\"='chifflet'}/nodes=2,walltime=0:10:00"
  types     = ["deploy"]
}

resource "grid5000_deployment" "my_deployment" {
  site        = grid5000_job.cassandra.site
  environment = "debian10-x64-base"
  nodes       = grid5000_job.cassandra.assigned_nodes
  key         = file("~/.ssh/id_rsa.pub")
}

output "nodes" {
  value = grid5000_job.cassandra.assigned_nodes
}
