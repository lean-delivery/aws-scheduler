[
  {
    "name": "${name}",
    "cpu": ${cpu},
    "memory": ${memory},
    "image": "${docker_image}",
    "repositoryCredentials": {
		"credentialsParameter": "${aws_secrets_manager_secret_arn}"
	},
	"essential": true,
    "portMappings": [
      {
        "containerPort": ${container_port},
        "hostPort": ${container_port}
      }
    ],
    "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
            "awslogs-region": "${region}",
            "awslogs-group": "${log-group}",
            "awslogs-stream-prefix": "${log-prefix}"
        }
    }
  }
]
