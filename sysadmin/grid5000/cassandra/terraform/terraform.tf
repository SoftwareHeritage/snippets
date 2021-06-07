terraform {
  required_providers {
    ansible = {
      source = "habakke/ansible"
      version = "~> 1.0.9"
    }
    grid5000 = {
      source  = "pmorillon/grid5000"
      version = "0.0.7"
    }
  }
}
