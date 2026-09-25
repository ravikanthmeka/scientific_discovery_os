module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${var.project_name}-${var.environment}-db"

  engine               = "postgres"
  engine_version       = "15.14"
  family               = "postgres15" 
  major_engine_version = "15"
  instance_class       = "db.t3.micro"
  
  allocated_storage     = 20
  max_allocated_storage = 100

  db_name  = "discovery_os"
  username = "dbadmin"
  password = var.db_password
  port     = 5432

  manage_master_user_password = false

  create_db_subnet_group = true
  subnet_ids             = module.vpc.private_subnets
  vpc_security_group_ids = [aws_security_group.db_sg.id]

  skip_final_snapshot = true
}

resource "aws_security_group" "db_sg" {
  name        = "${var.project_name}-${var.environment}-db-sg"
  description = "Security group for PostgreSQL RDS"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Allow postgres access from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}

