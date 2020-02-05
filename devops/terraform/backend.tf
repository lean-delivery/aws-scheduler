provider "aws" {
  version = "~> 2.8.0"
  region = "${data.terraform_remote_state.core.region}"
}

terraform {
  required_version = "~> 0.11.13"
  backend "s3" {
    encrypt        = true
    dynamodb_table = "terraform-lock"
    bucket         = "terraform-states"
    key            = "aws-instance-scheduler.tfstate"
    region         = "eu-central-1"
  }
}
