import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

DATA_DIR = "data"

LOAD_ORDER = [
    ("product_category_name_translation.csv", "category_translation", {}),
    ("olist_customers_dataset.csv", "customers", {}),
    ("olist_sellers_dataset.csv", "sellers", {}),
    ("olist_products_dataset.csv", "products", {
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    }),
    ("olist_orders_dataset.csv", "orders", {}),
    ("olist_order_items_dataset.csv", "order_items", {}),
    ("olist_order_payments_dataset.csv", "order_payments", {}),
    ("olist_order_reviews_dataset.csv", "order_reviews", {}),
]

TIMESTAMP_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}


def reset_tables():
    print("Truncating all tables before load...")
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE TABLE order_reviews, order_payments, order_items, "
            "orders, products, sellers, customers, category_translation "
            "RESTART IDENTITY CASCADE;"
        ))
        result = conn.execute(text("SELECT COUNT(*) FROM category_translation"))
        count = result.scalar()
        print(f"category_translation row count after truncate: {count}")
    print("Tables truncated.\n")
    
def patch_missing_categories():
    products = pd.read_csv(os.path.join(DATA_DIR, "olist_products_dataset.csv"))
    categories = pd.read_csv(os.path.join(DATA_DIR, "product_category_name_translation.csv"))
    missing = set(products["product_category_name"].dropna()) - set(categories["product_category_name"])
    if missing:
        print(f"Found {len(missing)} categories missing from translation table: {missing}")
        patch_df = pd.DataFrame({
            "product_category_name": list(missing),
            "product_category_name_english": list(missing),  # fallback: reuse original name
        })
        patch_df.to_sql("category_translation", engine, if_exists="append", index=False)
        print("Patched missing categories into category_translation.\n")


def load_csv_to_table(csv_file, table_name, rename_map):
    path = os.path.join(DATA_DIR, csv_file)
    print(f"Loading {csv_file} -> {table_name} ...")

    df = pd.read_csv(path)

    if rename_map:
        df = df.rename(columns=rename_map)

    if table_name == "order_reviews":
        before = len(df)
        df = df.drop_duplicates(subset=["review_id"])
        after = len(df)
        if before != after:
            print(f"  Dropped {before - after} duplicate review_id rows")

    for col in TIMESTAMP_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df.to_sql(table_name, engine, if_exists="append", index=False, method="multi", chunksize=1000)
    print(f"  Loaded {len(df)} rows into {table_name}")


def main():
    reset_tables()
    patch_missing_categories()
    for csv_file, table_name, rename_map in LOAD_ORDER:
        load_csv_to_table(csv_file, table_name, rename_map)
    print("\nAll tables loaded.")


if __name__ == "__main__":
    main()