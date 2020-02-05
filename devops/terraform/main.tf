data "terraform_remote_state" "core" {
  backend = "s3"

  config {
    bucket = "terraform-states"
    key    = "core/terraform.tfstate"
    region = "eu-central-1"
  }
}

locals {
  https_listeners_count = 1

  https_listeners = "${list(
                        map(
                            "certificate_arn", "${var.certificate_arn}",
                            "port", 443
                        )
  )}"

  target_groups_count = 1

  target_groups = "${list(
                        map("name", "${var.service}",
                            "backend_protocol", "HTTP",
                            "backend_port", "${var.container_port}",
                            "slow_start", 0
                        )
  )}"

  tags = "${map(
                "Service", "${var.service}",
                "Environment", "${var.environment}",
                "Project", "${data.terraform_remote_state.core.project}"
               )
  }"

  target_groups_defaults = "${map(
    "cookie_duration", 86400,
    "deregistration_delay", 300,
    "health_check_interval", 15,
    "health_check_healthy_threshold", 3,
    "health_check_path", "/login",
    "health_check_port", "traffic-port",
    "health_check_timeout", 10,
    "health_check_unhealthy_threshold", 3,
    "health_check_matcher", "200",
    "stickiness_enabled", "false",
    "target_type", "ip",
    "slow_start", 0
  )}"
}
