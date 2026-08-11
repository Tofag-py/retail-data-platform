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

KAFKA_BOOTSTRAP_SERVERS = os.getenv("MSK_BOOTSTRAP_BROKERS")
TOPIC_NAME = "clickstream-events"

EVENT_TYPES = ["page_view", "search", "add_to_cart", "remove_from_cart", "checkout"]
EVENT_WEIGHTS = [0.5, 0.2, 0.15, 0.05, 0.10]

DATA_DIR = "data"

MIN_EVENTS_PER_SESSION = 1
MAX_EVENTS_PER_SESSION = 8


def load_reference_ids():
    customers = pd.read_csv(os.path.join(DATA_DIR, "olist_customers_dataset.csv"))
    products = pd.read_csv(os.path.join(DATA_DIR, "olist_products_dataset.csv"))
    return (
        customers["customer_id"].tolist(),
        products["product_id"].tolist(),
    )


def build_event(session_id, customer_id, product_ids):
    event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]

    event = {
        "event_id": fake.uuid4(),
        "event_type": event_type,
        "customer_id": customer_id,
        "session_id": session_id,
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


def generate_session_events(customer_ids, product_ids):
    """Simulate one browsing session: a single customer, a single session_id,
    and a handful of events fired in quick succession — the way a real
    person actually clicks around a site."""
    session_id = fake.uuid4()
    customer_id = random.choice(customer_ids)
    num_events = random.randint(MIN_EVENTS_PER_SESSION, MAX_EVENTS_PER_SESSION)

    for _ in range(num_events):
        yield build_event(session_id, customer_id, product_ids)


def main():
    print("Loading reference IDs from Olist dataset...")
    customer_ids, product_ids = load_reference_ids()
    print(f"  {len(customer_ids)} customers, {len(product_ids)} products loaded\n")

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        security_protocol="PLAINTEXT",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    print(f"Producing session-based events to topic '{TOPIC_NAME}'. Press Ctrl+C to stop.\n")

    try:
        total_count = 0
        session_count = 0
        while True:
            session_count += 1
            events_in_session = 0
            for event in generate_session_events(customer_ids, product_ids):
                producer.send(TOPIC_NAME, value=event)
                total_count += 1
                events_in_session += 1
                time.sleep(random.uniform(0.3, 1.2))  # rapid-fire within a session

            print(f"  Session {session_count} complete: {events_in_session} events "
                  f"(total sent: {total_count})")

            # Pause between sessions, simulating a new visitor arriving
            time.sleep(random.uniform(1.0, 4.0))
    except KeyboardInterrupt:
        print(f"\nStopped. Sent {total_count} events across {session_count} sessions.")
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()