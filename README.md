# Real-Time Retail Intelligence Platform

An end-to-end AWS data platform combining batch and streaming pipelines, built as a hands-on portfolio project mirroring the responsibilities of a Data & AI consulting role (AWS Glue, Redshift, Athena, RDS, Lambda, MSK/Kafka, Managed Flink, SageMaker, Airflow, dbt — provisioned with Terraform, following DevOps and data governance practices throughout).

**Status as of Day 7**: Batch pipeline (RDS → Glue → S3 → Athena) fully working and verified end to end. Streaming pipeline (Kafka → Flink sessionization) working, self-hosted due to an AWS account restriction on MSK. Redshift, dbt, Airflow, SageMaker, and CI/CD are still to come.

---

## Quick orientation for picking this back up

If you're a new conversation/session catching up on this project: read this file top to bottom, then check `docs/decisions.md` for the reasoning behind every non-obvious choice made along the way. The `docs/day-N-progress-article.md` files (kept outside this repo, in project notes) contain a detailed day-by-day narrative if more context is ever needed.

**Repo**: private GitHub repo, `retail-data-platform`
**Region**: `us-east-1`
**Local project path**: `~/Documents/Documents/Projects/Real_Time_Retail_Intelligence/retail-data-platform`

---

## Architecture overview

```
Sources                RDS (Postgres, real Olist e-commerce data)   Kafka on EC2 (simulated clickstream)
                              |                                            |
Ingestion                     |                                     Faker-based producer (session-aware)
                              |                                            |
Processing              Glue crawler + ETL job                      PyFlink (local, sessionization)
                              |
Lake                    S3 (bronze layer, Parquet)
                              |
Catalog & query          Glue Data Catalog (2 databases) + Athena
                              |
Not yet built            Redshift + dbt (curated warehouse)
                          Airflow (orchestration)
                          SageMaker (ML scoring)
                          Lake Formation (governance)
                          CI/CD (GitHub Actions)
```

All infrastructure is provisioned via Terraform, modularized under `infra/modules/`. State is stored remotely in an S3 backend, not locally.

---

## What's actually built and working

### 1. Foundation (Terraform-managed)
- VPC with public/private subnets across 2 AZs, NAT gateway, IAM baseline role
- Two S3 buckets: the data lake itself, and Terraform's remote state
- All state migrated to S3 (not local) after an early git/state incident (see `docs/decisions.md`)

### 2. Batch data — RDS PostgreSQL
- Real dataset: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — orders, customers, products, sellers, payments, reviews, category translations
- 8 tables, foreign keys enforced, loaded via `etl/load_olist_data.py` (idempotent — truncates and reloads safely on every run)
- Two real data-quality issues in the source were found and fixed deliberately (not silently): missing category references, duplicate review IDs — see `docs/decisions.md`
- **Currently public** (IP-restricted security group) for admin access convenience — documented trade-off, not production practice

### 3. Batch pipeline — Glue + S3 + Athena
- Glue crawler catalogs the RDS schema via a JDBC connection (`retail_platform_dev_raw` database)
- Glue ETL job (`etl/glue_jobs/rds_to_s3.py`) extracts all 8 tables to S3 as Parquet (`bronze/` prefix)
- A **second** crawler catalogs the S3 output itself into a separate `retail_platform_dev_curated` database — necessary because a JDBC-source crawler and an S3-source crawler produce fundamentally different catalog entries (this distinction caused a real bug early on; see `docs/decisions.md`)
- Verified end-to-end: Athena query against `orders` returns exactly 99,441 rows, matching RDS exactly

### 4. Streaming — self-hosted Kafka on EC2
- AWS MSK is blocked at the account level (`SubscriptionRequiredException`) — not a config issue, a subscription/verification gate
- Kafka runs self-hosted on a plain EC2 instance in **KRaft mode** (no Zookeeper)
- `ingestion/clickstream_producer.py` — Faker-based producer generating realistic browsing sessions (multiple events per session, weighted event types, referencing real customer/product IDs from the Olist dataset)
- Verified: producer and consumer round-trip tested successfully from an external client (laptop), not just locally on the broker

### 5. Real-time processing — PyFlink
- `ingestion/flink_sessionizer.py` — consumes from the Kafka topic, windows events by session ID (30-second tumbling windows), counts activity per session, flags high-activity sessions as bot-like
- Runs locally (not AWS Managed Flink) — deliberate choice to avoid a second potential AWS service restriction; also the standard way Flink jobs are developed before deployment to a managed cluster

### 6. Governance & documentation
- `docs/decisions.md` — running log of every non-obvious trade-off made, why, and what the production-correct alternative would be
- `.gitignore` (root and `infra/`) correctly excludes state files, `.env`, raw data, Python caches
- `update-my-ip.sh` — helper script to refresh IP-restricted security group rules (residential IP rotates between sessions)

---

## Repository structure

```
infra/                  Terraform: modules for vpc, s3, iam, rds, glue, kafka_ec2
  modules/
  main.tf
  variables.tf
  outputs.tf
  terraform.tfvars      (gitignored — contains db_password)
etl/
  load_olist_data.py     RDS seed script (idempotent)
  schema.sql              RDS table definitions
  glue_jobs/
    rds_to_s3.py           PySpark ETL: RDS -> S3 Parquet
ingestion/
  clickstream_producer.py  Faker + Kafka producer (session-aware)
  flink_sessionizer.py      PyFlink consumer: windowed sessionization
data/                    Olist CSVs (gitignored, downloaded via Kaggle CLI)
docs/
  decisions.md            Architecture decision log
.env                      Local secrets (gitignored): DB and Kafka connection info
.gitignore
update-my-ip.sh           Helper: refresh admin IP in Terraform security groups
README.md                 This file
```

---

## Environment setup (for a fresh machine)

1. **Homebrew, Git, AWS CLI, Terraform, Python 3** — all via Homebrew, ensure native Apple Silicon (arm64) builds if on an M-series Mac. Watch for `libpq`/`psql` needing the full `postgresql@16` package, and Java needing a native arm64 JDK (`openjdk@17`) if running PyFlink.
2. **AWS credentials**: `aws configure`, region `us-east-1`
3. **SSH key** added to GitHub for repo access
4. **Python venv**: `python3 -m venv .venv && source .venv/bin/activate`, then `pip install psycopg2-binary pandas sqlalchemy python-dotenv kafka-python faker apache-flink`
   - If `apache-flink`/`apache-beam` fails to build: `pip install "setuptools<81"` then `pip install apache-flink --no-build-isolation`
5. **`.env` file** (gitignored) needs: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `MSK_BOOTSTRAP_BROKERS`
6. **Kaggle CLI**: `~/.kaggle/kaggle.json` with API credentials, `chmod 600`

---

## Common operational commands

**Bring the foundation up:**
```bash
cd infra && terraform init && terraform apply
```

**Start/stop RDS** (left stopped between sessions — negligible storage cost, expensive to reload):
```bash
aws rds start-db-instance --db-instance-identifier retail-platform-dev-db
aws rds stop-db-instance --db-instance-identifier retail-platform-dev-db
```

**Kafka EC2** (fully destroyed between sessions — real compute cost, cheap/fast to rebuild):
```bash
# Bring up: uncomment module "kafka_ec2" block in infra/main.tf, then
terraform apply
# Then SSH in and follow the KRaft setup sequence in docs/decisions.md
# Tear down:
terraform destroy -target=module.kafka_ec2
```

**Refresh your IP** (rotates between sessions, breaks RDS/Kafka security group rules):
```bash
./update-my-ip.sh          # review plan
./update-my-ip.sh --apply  # apply automatically
```

**Run the batch pipeline:**
```bash
python etl/load_olist_data.py                                    # seed RDS
aws glue start-crawler --name retail-platform-dev-rds-crawler     # catalog RDS schema
aws glue start-job-run --job-name retail-platform-dev-rds-to-s3   # extract to S3
aws glue start-crawler --name retail-platform-dev-s3-bronze-crawler  # catalog S3 output
```

**Run the streaming pipeline** (needs Kafka EC2 up):
```bash
python ingestion/clickstream_producer.py     # terminal 1
python ingestion/flink_sessionizer.py         # terminal 2
```

---

## Cost discipline

- **RDS**: stopped between sessions (auto-restarts after 7 days if left stopped — AWS safety mechanism)
- **Kafka/EC2**: fully destroyed between sessions (the single most expensive "leave it running" risk in this stack)
- **Glue, Athena, S3, Data Catalog**: genuinely pay-per-use, zero idle cost — safe to leave provisioned indefinitely
- An AWS Budget alert is configured (~$20/month threshold) as a safety net

---

## Known deviations from production best practice (deliberate, documented)

See `docs/decisions.md` for full reasoning on each:
- RDS is publicly accessible (IP-restricted) rather than fully private with a bastion/SSM tunnel
- Kafka is self-hosted on EC2 rather than AWS MSK (account subscription restriction, not a design choice)
- Flink runs locally via PyFlink rather than AWS Managed Flink
- A single shared IAM service role is used rather than least-privilege per-service roles
- Glue's Parquet output is unconsolidated (20 part-files per table) rather than coalesced — functionally fine at current data volume, would need fixing at scale

---

## Build order / what's next

1. ~~VPC, S3, IAM foundation~~ — done
2. ~~RDS + Olist data load~~ — done
3. ~~Kafka + clickstream producer~~ — done
4. ~~PyFlink sessionization~~ — done
5. ~~Glue + S3 data lake + Athena~~ — done
6. **Redshift + dbt** — next up: curated warehouse with tested transformations
7. Airflow (MWAA) — orchestrate the batch pipeline end to end
8. SageMaker — churn/demand-forecast model on curated data
9. Lake Formation — column-level governance, PII masking
10. GitHub Actions CI/CD — lint/test/deploy pipeline for Terraform, Glue scripts, dbt models
11. CloudWatch dashboards and alarms
