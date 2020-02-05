output "service_endpoint" {
  value = "${aws_route53_record.common.fqdn}"
}
