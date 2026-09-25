output "cloudfront_url" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}


output "route53_nameservers" {
  value       = aws_route53_zone.main.name_servers
  description = "Nameservers for the custom domain"
}
