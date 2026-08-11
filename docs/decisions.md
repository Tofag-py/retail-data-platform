# Architecture & Design Decisions

A running log of non-obvious decisions made during this build, why they were made, and what the trade-offs were. Intended as both a personal reference and interview prep material — each entry is something worth being able to explain and defend out loud.

---

## RDS: temporary public access instead of a bastion host

**Decision**: RDS was moved from private subnets (no public access) to public subnets with a security group restricting inbound Postgres traffic to a single admin IP address.

**Why**: The original design placed RDS in private subnets with no public accessibility — correct for a production system, but it meant the database couldn't be reached at all from a laptop outside the VPC for schema setup and data loading. Rather than leave the platform undeployable for basic admin work, or immediately build a full bastion host / AWS Systems Manager port-forwarding setup, the pragmatic choice for a solo development project was temporary IP-restricted public access.

**Trade-off acknowledged**: This is not how a production database should be configured. The correct long-term pattern is a bastion host or SSM Session Manager tunnel, keeping RDS fully private with zero public exposure. That's a planned hardening step, not the final state.

**Why it's still a reasonable call for now**: No real user data lives in this database (it's the Olist public dataset), the access is scoped to one IP at a time, and the trade-off between "development velocity" and "production security posture" is one every real project has to navigate — the point is making the call deliberately and being able to explain both the decision and its limitations, not that this is presented as best practice.

---

## MSK blocked at the account level — self-hosted Kafka on EC2 instead

**Decision**: After AWS MSK returned a `SubscriptionRequiredException` (an account-level restriction, not a configuration issue) on cluster creation, the project pivoted to running Apache Kafka manually on a plain EC2 instance, in KRaft mode (no separate Zookeeper process).

**Why**: The account wasn't authorized for MSK at the time — likely a billing/account-verification gate rather than anything fixable through Terraform or IAM permissions. Chasing an AWS support ticket wasn't a good use of limited session time, so the decision was to route around the blocker rather than let it stall the whole streaming build.

**Trade-off acknowledged**: MSK exists specifically so nobody has to hand-manage broker processes, storage formatting, version upgrades, and failure recovery — all of which this project now does manually. For a real client platform, MSK (or an equivalent managed service) would be the default choice, not a self-hosted broker.

**Unexpected upside**: Running Kafka manually surfaced a genuine, valuable understanding of Kafka's internals that a managed service would have hidden entirely — KRaft's storage formatting requirements, and critically, how a broker's `advertised.listeners` setting determines whether external clients can actually reach it (a misconfiguration here, not caught immediately, cost real debugging time across two separate sessions).

**Status**: Revisit whether the MSK account restriction can be resolved (billing verification, support ticket) as a parallel task — not blocking further build progress, but worth pursuing so the final project can honestly claim to have used the JD's actual named service, not just a workaround.

---

## Kafka's advertised.listeners: a recurring, subtle failure mode

**Decision/lesson**: Every time the Kafka EC2 instance is rebuilt, `advertised.listeners` must be explicitly set to the instance's current public IP, and verified with a direct `grep` check immediately after — not assumed to have worked just because the `sed` command didn't error.

**Why this matters**: This exact misconfiguration caused silent failures twice (day five and day six) — the `sed` substitution pattern didn't match Kafka's actual default config line, left `advertised.listeners` pointing at `localhost`, and the resulting symptom (a producer connecting successfully but then timing out trying to actually send data) doesn't obviously point back to this cause. It looks like a network problem; it's actually a broker telling clients to reconnect to an address that means nothing to them.

**Process fix adopted**: Always verify the substitution took effect before moving on to starting Kafka, rather than trusting that a `sed` command without an error message means it succeeded.

---

## PyFlink locally instead of AWS Managed Flink

**Decision**: Rather than attempt AWS Managed Flink (risking a similar account-level block to MSK, or additional setup complexity), the real-time consumer was built using PyFlink running locally, consuming from the same self-hosted Kafka broker.

**Why**: Running Flink jobs locally during development is the standard, expected workflow even for teams that do eventually deploy to a managed Flink cluster — this isn't a lesser version of the architecture, it's the normal first step. Given the MSK experience, avoiding a second potential AWS service blocker in the same week was also a reasonable time-management call.

**Trade-off acknowledged**: A local PyFlink job isn't horizontally scalable, isn't fault-tolerant across machine failure, and isn't how this would run in production. AWS Managed Flink (or a self-hosted Flink cluster) would be the real deployment target.

---

## Data quality issues in the Olist dataset, handled explicitly rather than silently

**Decision**: Two genuine data quality problems in the source CSVs were fixed with visible, logged patches rather than silently dropping rows or letting the load fail.

1. **Missing category references**: Two product categories (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) appeared in the products file but were absent from Olist's own category translation lookup table. Fix: patch the lookup table with the missing categories, using the original Portuguese name as a fallback English translation rather than inventing one. The gap remains visible to anyone querying the table.

2. **Duplicate primary keys in order_reviews**: 814 rows shared a `review_id` with another row in the same file, violating the table's primary key constraint. Fix: deduplicate on `review_id` before insert, keeping the first occurrence, and explicitly logging how many rows were dropped.

**Why this approach**: Both fixes are honest about what happened to the data rather than hiding it — a reviewer of this pipeline can see exactly what was changed and why, which matters far more for a project meant to demonstrate judgment than a pipeline that just silently "worked."

---

## Load script idempotency

**Decision**: The Olist load script truncates all tables at the start of every run before loading, rather than assuming it will only ever be run successfully once.

**Why**: Real load jobs get interrupted, debugged, and re-run constantly. An early version of the script had no way to recover from a partial failure without manual intervention (manually truncating tables via `psql` before every retry). Making the script self-contained — safe to run any number of times — removed an entire class of debugging confusion for very little additional code.

---

## Cost discipline: RDS left running, Kafka/Flink torn down between sessions

**Decision**: RDS is stopped (not destroyed) between sessions and started again as needed. Kafka's EC2 instance is fully destroyed via Terraform at the end of every session that uses it, and rebuilt from scratch when next needed.

**Why the difference**: RDS storage costs are negligible when stopped, and rebuilding it would mean re-loading the entire Olist dataset each time — not worth the time cost for a small storage saving. The Kafka EC2 instance, by contrast, is a compute-heavy resource with no persistent data worth preserving between sessions (it's a message broker, not a data store, and messages here are meant to be ephemeral simulation data) — so full teardown is both cheap to redo (the setup sequence is now well understood and fast) and removes any risk of an idle instance being forgotten and billing unnecessarily.