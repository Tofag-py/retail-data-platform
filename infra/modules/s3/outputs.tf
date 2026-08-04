output "data_lake_bucket_name" {
  value = aws_s3_bucket.data_lake.id
}

output "tf_state_bucket_name" {
  value = aws_s3_bucket.tf_state.id
}