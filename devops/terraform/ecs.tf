resource "aws_cloudwatch_log_group" "common" {
  name              = "${data.terraform_remote_state.core.project}-${var.service}"
  retention_in_days = "14"

  tags = "${local.tags}"
}


module "ecs-fargate" {
  source = "github.com/lean-delivery/tf-module-aws-ecs?ref=v0.2"

  project          = "${data.terraform_remote_state.core.project}"
  environment      = "${var.environment}"
  service          = "${var.service}"
  container_cpu    = "${var.cpu}"
  container_memory = "${var.memory}"
  vpc_id           = "${data.terraform_remote_state.core.vpc.dev.id}"

  subnets = [
    "${data.terraform_remote_state.core.subnet.core_a.id}",
    "${data.terraform_remote_state.core.subnet.core_b.id}",
  ]

  alb_target_group_arn  = "${module.alb.target_group_arns[0]}"
  container_port        = "${var.container_port}"
  container_definitions = "${data.template_file.container_definitions.rendered}"
  task_role_arn         = "${aws_iam_role.ecs-task-role.arn}"
}


# allow access from ALB to ECS
resource "aws_security_group_rule" "add_ingress_from_alb_security_group" {
  security_group_id = "${module.ecs-fargate.security_group_id}"
  type              = "ingress"

  source_security_group_id = "${module.alb_security_group.this_security_group_id}"
  description              = "Allow traffic from ALB"

  from_port = 0
  to_port   = 0
  protocol  = -1
}


# Allow access to DynamoDB and EC2 from ECS container
data "aws_iam_policy_document" "ecs-task-allow-dynamodb-and-ec2" {
  statement {
    effect = "Allow"
    actions = [
		"dynamodb:BatchGetItem",
		"dynamodb:BatchWriteItem",
		"dynamodb:PutItem",
		"ec2:DeleteTags",
		"dynamodb:DeleteItem",
		"ec2:CreateTags",
		"dynamodb:Scan",
		"dynamodb:Query",
		"dynamodb:UpdateItem",
		"dynamodb:DescribeTable",
		"dynamodb:GetItem"
    ]
    resources = [
		"arn:aws:dynamodb:*:*:table/${var.instance-scheduler-config-table-name}",
		"arn:aws:dynamodb:*:*:table/${var.instance-scheduler-users-table-name}",
		"arn:aws:dynamodb:*:*:table/${var.instance-scheduler-groups-table-name}",
		"arn:aws:dynamodb:*:*:table/${var.instance-scheduler-default-schedules-table-name}",
		"arn:aws:ec2:*:*:instance/*",
    ]
  }
  statement {
    effect = "Allow"
	actions = [
		"ec2:DescribeInstances",
		"dynamodb:ListTables",
    ]
	resources = [
		"*"
    ]
  }
}


data "aws_iam_policy_document" "ecs-service-allow-secrets-manager" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue"
    ]

    resources = [
      "${var.aws_secrets_manager_secret_arn}"
    ]
  }
}


resource "aws_iam_policy" "ecs-service-allow-secrets-manager" {
  name        = "ecs-service-allow-secrets-manager-${var.service}-${var.environment}"
  description = "ECS Service policy to access Secrets Manager"
  policy      = "${data.aws_iam_policy_document.ecs-service-allow-secrets-manager.json}"
}


resource "aws_iam_policy" "ecs-task-allow-dynamodb-and-ec2" {
  name        = "ecs-task-allow-dynamodb-and-ec2-${var.service}-${var.environment}"
  description = "ECS task role policy to access dynamodb and ec2"
  policy      = "${data.aws_iam_policy_document.ecs-task-allow-dynamodb-and-ec2.json}"
}


resource "aws_iam_role" "ecs-task-role" {
  name = "ecs-task-role-${var.service}-${var.environment}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
  tags = "${local.tags}"
}


resource "aws_iam_role_policy_attachment" "attach-allow-dynamodb-and-ec2" {
  role       = "${aws_iam_role.ecs-task-role.name}"
  policy_arn = "${aws_iam_policy.ecs-task-allow-dynamodb-and-ec2.arn}"
}


resource "aws_iam_role_policy_attachment" "attach-allow-secrets-manager" {
  role       = "${module.ecs-fargate.ecs_task_execution_iam_role_name}"
  policy_arn = "${aws_iam_policy.ecs-service-allow-secrets-manager.arn}"
}
