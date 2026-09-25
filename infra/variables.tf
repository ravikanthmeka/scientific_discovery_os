variable "aws_region" {
  description = "AWS Region"
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for tagging and naming"
  default     = "sdo"
}

variable "environment" {
  description = "Environment name"
  default     = "prod"
}

variable "db_password" {
  description = "Password for the RDS PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "neo4j_uri" {
  type = string
}

variable "neo4j_user" {
  type = string
}

variable "neo4j_password" {
  type      = string
  sensitive = true
}

variable "qdrant_api_key" {
  type      = string
  sensitive = true
  default   = ""
}


variable "domain_name" {
  description = "Custom domain name for the application"
  type        = string
  default     = "synaptolab.app"
}
variable "stripe_secret_key" {
  description = "Stripe Secret Key"
  type        = string
}

variable "stripe_price_id" {
  description = "Stripe Price ID"
  type        = string
}

variable "stripe_webhook_secret" {
  description = "Stripe Webhook Secret"
  type        = string
}
