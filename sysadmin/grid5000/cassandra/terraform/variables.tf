variable "site" {
  description = "the grid5000 site to use"
  default = "rennes"
  type = string
}

variable "cluster" {
  description = "the grid5000 cluster to use"
  default = "parasilo"
  type = string
}

variable "total_node_count" {
  description = "The total number of nodes to reserve"
  default = "1"
  type = number
}

variable "cassandra_node_count" {
  description = "The total number of cassandra nodes to install"
  default = "1"
  type = number
}

variable "sleep_time" {
  description = "the reservation duration"
  default = "1h"
  type = string
}

variable "walltime" {
  description = "the reservation duration"
  default = "01:00:00"
  type = string
}

variable "cassandra_walltime" {
  description = "the reservation duration"
  default = "00:58:00"
  type = string
}
