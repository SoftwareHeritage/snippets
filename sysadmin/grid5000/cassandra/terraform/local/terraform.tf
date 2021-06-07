terraform {
 required_version = ">= 0.13"
  required_providers {
    libvirt = {
      source  = "multani/libvirt"
      version = "0.6.3-1+4"
    }
  }
}

provider "libvirt" {
  uri = "qemu:///system"
}
