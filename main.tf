provider "aws" {
  region = "eu-north-1"
}

# Create virtual private cloud to isolate the infrastructure
resource "aws_vpc" "default" {
  cidr_block = "10.0.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
  tags = {
    Name = "DJANGO_EC2_VPC"
  }
}

# Create internet gateway to allow public access to the VPC
resource "aws_internet_gateway" "default" {
  vpc_id = aws_vpc.default.id
  tags = {
    Name = "DJANGO_EC2_Internet_Gateway"
  }
}

# Create route table to allow public access to the VPC
resource "aws_route_table" "default" {
  vpc_id = aws_vpc.default.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.default.id
  }
  tags = {
    Name = "DJANGO_EC2_Route_Table"
  }
}

# Subnet within VPC for resource allocation, in availability zone us-east-1a
resource "aws_subnet" "subnet1" {
  vpc_id                  = aws_vpc.default.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "eu-north-1a"
  tags = {
    Name = "Django_EC2_Subnet_1"
  }
}

# Another subnet for redundancy, in availability zone us-east-1b
resource "aws_subnet" "subnet2" {
  vpc_id                  = aws_vpc.default.id
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "eu-north-1b"
  tags = {
    Name = "Django_EC2_Subnet_2"
  }
}

# Associate subnets with route table for internet access
resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.subnet1.id
  route_table_id = aws_route_table.default.id
}
resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.subnet2.id
  route_table_id = aws_route_table.default.id
}

# Security group for EC2 instance
resource "aws_security_group" "ec2_sg" {
  vpc_id = aws_vpc.default.id
  
  # HTTP traffic
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP traffic"
  }
  
  # HTTPS traffic
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS traffic"
  }
  
  # WebSocket traffic (typically needs the same port as HTTP/HTTPS)
  # But add this rule to explicitly document the WebSocket requirement
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow WebSocket traffic"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "EC2_Security_Group"
  }
}

# Security group for RDS PostgreSQL
resource "aws_security_group" "postgres_sg" {
  vpc_id = aws_vpc.default.id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
    description     = "Allow PostgreSQL traffic from EC2"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "PostgreSQL_Security_Group"
  }
}

# Define variable for RDS password to avoid hardcoding secrets
variable "secret_key" {
  description = "The Secret Key for Django"
  type        = string
  sensitive   = true
}

# Define variables for RDS
variable "db_name" {
  description = "Database name"
  type        = string
  default     = "django_db"
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Create subnet group for RDS
resource "aws_db_subnet_group" "postgres_subnet_group" {
  name       = "postgres-subnet-group"
  subnet_ids = [aws_subnet.subnet1.id, aws_subnet.subnet2.id]
  
  tags = {
    Name = "PostgreSQL Subnet Group"
  }
}

# Create PostgreSQL RDS instance
resource "aws_db_instance" "postgres" {
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.postgres_subnet_group.name
  vpc_security_group_ids = [aws_security_group.postgres_sg.id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  
  tags = {
    Name = "Django PostgreSQL Database"
  }
}

# EC2 instance for the local web app
resource "aws_instance" "web" {
  ami                    = "ami-0c101f26f147fa7fd" # Amazon Linux
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.subnet1.id # Place this instance in one of the private subnets
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  associate_public_ip_address = true # Assigns a public IP address to your instance
  user_data_replace_on_change = true # Replace the user data when it changes

  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
    #!/bin/bash
    set -ex
    yum update -y
    yum install -y yum-utils
    
    # Install Docker
    yum install -y docker
    service docker start
    systemctl enable docker
    
    # Install AWS CLI
    yum install -y aws-cli
    
    # Authenticate to ECR
    docker login -u AWS -p $(aws ecr get-login-password --region eu-north-1) 954976284425.dkr.ecr.eu-north-1.amazonaws.com/scraping/scraper
    
    # Pull the Docker image from ECR
    docker pull 954976284425.dkr.ecr.eu-north-1.amazonaws.com/scraping/scraper:latest
    
    # Run the Docker image with environment variables
    docker run -d -p 80:8000 \
    --env SECRET_KEY=${var.secret_key} \
    --env DB_NAME=${var.db_name} \
    --env DB_USER=${var.db_username} \
    --env DB_PASSWORD=${var.db_password} \
    --env DB_HOST=${aws_db_instance.postgres.endpoint} \
    --env DB_PORT=5432 \
    --env CONN_AGE=60 \
    --env ALLOWED_HOSTS="*" \
    --env CORS_ALLOWED_ORIGINS="*" \
    --env CORS_ALLOW_ALL_ORIGINS="true" \
    954976284425.dkr.ecr.eu-north-1.amazonaws.com/scraping/scraper:latest
    EOF

  tags = {
    Name = "Django_EC2_Complete_Server"
  }
}

# IAM role for EC2 instance to access ECR
resource "aws_iam_role" "ec2_role" {
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = {
        Service = "ec2.amazonaws.com",
      },
      Effect = "Allow",
    }],
  })
}

# Attach the AmazonEC2ContainerRegistryReadOnly policy to the role
resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# IAM instance profile for EC2 instance
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "django_ec2_complete_profile"
  role = aws_iam_role.ec2_role.name
}

# Create ALB for better WebSocket support
resource "aws_lb" "django_alb" {
  name               = "django-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.subnet1.id, aws_subnet.subnet2.id]
  
  enable_deletion_protection = false
  
  tags = {
    Name = "Django Application Load Balancer"
  }
}

# ALB Security Group
resource "aws_security_group" "alb_sg" {
  vpc_id = aws_vpc.default.id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "ALB_Security_Group"
  }
}

# Target group for the ALB
resource "aws_lb_target_group" "django_tg" {
  name     = "django-target-group"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.default.id
  
  health_check {
    enabled             = true
    path                = "/admin/login/"
    port                = "traffic-port"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
}

# Register EC2 instance with target group
resource "aws_lb_target_group_attachment" "django_tg_attachment" {
  target_group_arn = aws_lb_target_group.django_tg.arn
  target_id        = aws_instance.web.id
  port             = 80
}

# Create HTTP listener
resource "aws_lb_listener" "django_http" {
  load_balancer_arn = aws_lb.django_alb.arn
  port              = 80
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.django_tg.arn
  }
} 
