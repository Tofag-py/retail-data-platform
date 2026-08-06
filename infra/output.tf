output "vpc_id" {
  value = module.vpc.vpc_id
}

output "public_subnet_ids" {
  value = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "data_lake_bucket_name" {
  value = module.s3.data_lake_bucket_name
}

output "tf_state_bucket_name" {
  value = module.s3.tf_state_bucket_name
}

output "service_role_arn" {
  value = module.iam.service_role_arn
}

output "db_endpoint" {
  value = module.rds.db_endpoint
}