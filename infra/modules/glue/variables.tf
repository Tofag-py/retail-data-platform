variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_id" {
  type = string
}

variable "availability_zone" {
  type = string
}

variable "rds_endpoint" {
  type = string
}

variable "rds_db_name" {
  type = string
}

variable "rds_username" {
  type = string
}

variable "rds_password" {
  type      = string
  sensitive = true
}

variable "glue_role_arn" {
  type = string
}

variable "data_lake_bucket_name" {
  type = string
}