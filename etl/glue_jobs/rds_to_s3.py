import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "data_lake_bucket",
    "glue_database",
    "connection_name",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

DATA_LAKE_BUCKET = args["data_lake_bucket"]
CONNECTION_NAME = args["connection_name"]

# Tables to extract from RDS into the bronze layer of the data lake.
# Order doesn't matter here since each table is written independently.
TABLES = [
    "customers",
    "sellers",
    "products",
    "category_translation",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
]


def extract_table_to_s3(table_name):
    print(f"Extracting {table_name} from RDS...")

    connection_options = {
        "useConnectionProperties": "true",
        "dbtable": table_name,
        "connectionName": CONNECTION_NAME,
    }

    dynamic_frame = glueContext.create_dynamic_frame.from_options(
        connection_type="postgresql",
        connection_options=connection_options,
        transformation_ctx=f"extract_{table_name}",
    )

    output_path = f"s3://{DATA_LAKE_BUCKET}/bronze/{table_name}/"

    glueContext.write_dynamic_frame.from_options(
        frame=dynamic_frame,
        connection_type="s3",
        connection_options={"path": output_path},
        format="parquet",
        transformation_ctx=f"write_{table_name}",
    )

    print(f"  Wrote {table_name} to {output_path}")


for table in TABLES:
    extract_table_to_s3(table)

job.commit()
print("\nAll tables extracted to bronze layer.")