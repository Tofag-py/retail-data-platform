resource "aws_glue_catalog_database" "raw" {
  name = "${replace(var.project_name, "-", "_")}_${var.environment}_raw"
}

resource "aws_security_group" "glue" {
  name        = "${var.project_name}-${var.environment}-glue-sg"
  description = "Security group for Glue ENIs to reach RDS"
  vpc_id      = var.vpc_id

  # Glue requires a self-referencing rule for internal ENI communication
  ingress {
    description = "Self-referencing for Glue internal traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-glue-sg"
  }
}

resource "aws_glue_connection" "rds" {
  name = "${var.project_name}-${var.environment}-rds-connection"

  connection_type = "JDBC"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:postgresql://${var.rds_endpoint}/${var.rds_db_name}"
    USERNAME            = var.rds_username
    PASSWORD            = var.rds_password
  }

  physical_connection_requirements {
    availability_zone      = var.availability_zone
    security_group_id_list = [aws_security_group.glue.id]
    subnet_id              = var.private_subnet_id
  }
}

resource "aws_glue_crawler" "rds" {
  name          = "${var.project_name}-${var.environment}-rds-crawler"
  role          = var.glue_role_arn
  database_name = aws_glue_catalog_database.raw.name

  jdbc_target {
    connection_name = aws_glue_connection.rds.name
    path            = "${var.rds_db_name}/%"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-crawler"
  }
}

resource "aws_s3_object" "etl_script" {
  bucket = var.data_lake_bucket_name
  key    = "scripts/rds_to_s3.py"
  source = "${path.module}/../../../etl/glue_jobs/rds_to_s3.py"
  etag   = filemd5("${path.module}/../../../etl/glue_jobs/rds_to_s3.py")
}

resource "aws_glue_job" "rds_to_s3" {
  name     = "${var.project_name}-${var.environment}-rds-to-s3"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.data_lake_bucket_name}/scripts/rds_to_s3.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--TempDir"                          = "s3://${var.data_lake_bucket_name}/temp/"
    "--data_lake_bucket"                 = var.data_lake_bucket_name
    "--glue_database"                    = aws_glue_catalog_database.raw.name
    "--connection_name"                  = aws_glue_connection.rds.name
    "--enable-continuous-cloudwatch-log" = "true"
  }

  connections       = [aws_glue_connection.rds.name]
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-to-s3"
  }
}

resource "aws_glue_catalog_database" "curated" {
  name = "${replace(var.project_name, "-", "_")}_${var.environment}_curated"
}

resource "aws_glue_crawler" "s3_bronze" {
  name          = "${var.project_name}-${var.environment}-s3-bronze-crawler"
  role          = var.glue_role_arn
  database_name = aws_glue_catalog_database.curated.name

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/bronze/"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-bronze-crawler"
  }
}

# dbt-athena builds staging/mart models into this database. Kept separate from
# `curated` (crawler-owned, source-of-truth for raw bronze data) so dbt never
# writes into the same namespace a crawler manages — mirrors the raw/curated
# split rationale already documented for the JDBC vs S3 crawlers.
resource "aws_glue_catalog_database" "analytics" {
  name = "${replace(var.project_name, "-", "_")}_${var.environment}_analytics"
}