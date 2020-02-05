data "template_file" "container_definitions" {
  template = "${file("${path.module}/container_definitions/app.json.tpl")}"

  vars {
    name           					= "${var.service}-${var.environment}"
    cpu            					= "${var.cpu}"
    memory         					= "${var.memory}"
    docker_image   					= "${var.docker_registry}/${var.docker_image}:${var.docker_image_tag}"
    container_port 					= "${var.container_port}"
    region         					= "${data.terraform_remote_state.core.region}"
    log-group     					= "${aws_cloudwatch_log_group.common.name}"
    log-prefix     					= "${data.terraform_remote_state.core.project}"
	aws_secrets_manager_secret_arn 	= "${var.aws_secrets_manager_secret_arn}"
  }
}
