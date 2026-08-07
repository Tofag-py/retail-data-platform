variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_name" {
  type    = string
  default = "retaildb"
}

variable "db_username" {
  type    = string
  default = "retailadmin"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "my_ip_cidr" {
  description = "Your IP address in CIDR form, for temporary admin access"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for temporary public DB access"
  type        = list(string)
}