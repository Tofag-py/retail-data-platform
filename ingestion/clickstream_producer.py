import os
import json
import random
import time
from datetime import datetime, timezone

import pandas as pd
from faker import Faker
from kafka import KafkaProducer
from dotenv import load_dotenv

load_dotenv()

fake = Faker()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("MSK_BOOTSTRAP_BROKERS")  # comma-separated list
TOPIC_NAME = "clickstream-events"

EVENT_TYPES = ["page_view", "search", "add_to_cart", "remove_from_cart", "checkout"]
EVENT_WEIGHTS = [0.5, 0.2, 0.15, 0.05, 0.10]  # page views most common, checkouts rarest

DATA_DIR = "data"


def load_reference_ids():
    """Pull real customer and product IDs from the Olist CSVs so events
    reference entities that actually exist in the batch data."""
    customers = pd.read_csv(os.path.join(DATA_DIR, "olist_customers_dataset.csv"))
    products = pd.read_csv(os.path.join(DATA_DIR, "olist_products_dataset.csv"))
    return (
        customers["customer_id"].tolist(),
        products["product_id"].tolist(),
    )


def build_event(customer_ids, product_ids):
    event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
    customer_id = random.choice(customer_ids)

    event = {
        "event_id": fake.uuid4(),
        "event_type": event_type,
        "customer_id": customer_id,
        "session_id": fake.uuid4(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_agent": fake.user_agent(),
        "ip_address": fake.ipv4(),
    }

    if event_type in ("page_view", "add_to_cart", "remove_from_cart", "checkout"):
        event["product_id"] = random.choice(product_ids)

    if event_type == "search":
        event["search_query"] = fake.word()

    if event_type in ("add_to_cart", "checkout"):
        event["quantity"] = random.randint(1, 3)

    return event


def main():
    print("Loading reference IDs from Olist dataset...")
    customer_ids, product_ids = load_reference_ids()
    print(f"  {len(customer_ids)} customers, {len(product_ids)} products loaded\n")

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        security_protocol="PLAINTEXT",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    print(f"Producing events to topic '{TOPIC_NAME}'. Press Ctrl+C to stop.\n")

    try:
        count = 0
        while True:
            event = build_event(customer_ids, product_ids)
            producer.send(TOPIC_NAME, value=event)
            count += 1
            if count % 10 == 0:
                print(f"  Sent {count} events so far... (latest: {event['event_type']})")
            time.sleep(random.uniform(0.2, 1.5))  # simulate irregular real traffic
    except KeyboardInterrupt:
        print(f"\nStopped. Sent {count} events total.")
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()