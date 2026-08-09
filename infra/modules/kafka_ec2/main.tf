resource "aws_security_group" "kafka" {
  name        = "${var.project_name}-${var.environment}-kafka-sg"
  description = "Allow Kafka and SSH access from admin IP"
  vpc_id      = var.vpc_id

  ingress {
    description = "Kafka from VPC"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Kafka from admin IP"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "SSH from admin IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-kafka-sg"
  }
}

resource "aws_key_pair" "kafka" {
  key_name   = "${var.project_name}-${var.environment}-kafka-key"
  public_key = var.ssh_public_key
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "kafka" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.small"
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.kafka.id]
  key_name               = aws_key_pair.kafka.key_name

  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y java-17-amazon-corretto-headless

    cd /opt
    curl -O https://downloads.apache.org/kafka/3.7.0/kafka_2.13-3.7.0.tgz
    tar -xzf kafka_2.13-3.7.0.tgz
    mv kafka_2.13-3.7.0 kafka

    # Configure Kafka to advertise its public IP so external clients can connect
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
    sed -i "s/#advertised.listeners=PLAINTEXT:\/\/your.host.name:9092/advertised.listeners=PLAINTEXT:\/\/$PUBLIC_IP:9092/" /opt/kafka/config/server.properties

    # Start Zookeeper and Kafka as background services
    nohup /opt/kafka/bin/zookeeper-server-start.sh /opt/kafka/config/zookeeper.properties > /var/log/zookeeper.log 2>&1 &
    sleep 10
    nohup /opt/kafka/bin/kafka-server-start.sh /opt/kafka/config/server.properties > /var/log/kafka.log 2>&1 &
  EOF

  tags = {
    Name = "${var.project_name}-${var.environment}-kafka"
  }
}