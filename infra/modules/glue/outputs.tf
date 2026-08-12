output "crawler_name" {
  value = aws_glue_crawler.rds.name
}

output "job_name" {
  value = aws_glue_job.rds_to_s3.name
}

output "catalog_database" {
  value = aws_glue_catalog_database.raw.name
}

output "s3_crawler_name" {
  value = aws_glue_crawler.s3_bronze.name
}

output "curated_database" {
  value = aws_glue_catalog_database.curated.name
}