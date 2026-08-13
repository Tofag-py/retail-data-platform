terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "retail-platform-dev-tf-state-964291633100"
    key     = "terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  enable_nat_gateway = true
}

module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

module "iam" {
  source = "./modules/iam"

  project_name         = var.project_name
  environment          = var.environment
  data_lake_bucket_arn = "arn:aws:s3:::${module.s3.data_lake_bucket_name}"
}

module "rds" {
  source = "./modules/rds"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = "10.0.0.0/16"
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids
  db_password        = var.db_password
  my_ip_cidr         = "102.90.96.67/32"
}

# module "msk" {
#   source = "./modules/msk"

#   project_name        = var.project_name
#   environment         = var.environment
#   vpc_id              = module.vpc.vpc_id
#   vpc_cidr            = "10.0.0.0/16"
#   public_subnet_ids   = module.vpc.public_subnet_ids
#   my_ip_cidr          = "102.90.96.67/32"
# }


# module "kafka_ec2" {
#   source = "./modules/kafka_ec2"

#   project_name       = var.project_name
#   environment        = var.environment
#   vpc_id             = module.vpc.vpc_id
#   vpc_cidr           = "10.0.0.0/16"
#   public_subnet_id   = module.vpc.public_subnet_ids[0]
#   my_ip_cidr         = "102.90.98.207/32"
#   ssh_public_key     = file("~/.ssh/id_ed25519.pub")
# }

module "glue" {
  source = "./modules/glue"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_id     = module.vpc.private_subnet_ids[0]
  availability_zone     = "us-east-1a"
  rds_endpoint          = module.rds.db_endpoint
  rds_db_name           = "retaildb"
  rds_username          = "retailadmin"
  rds_password          = var.db_password
  glue_role_arn         = module.iam.service_role_arn
  data_lake_bucket_name = module.s3.data_lake_bucket_name
}