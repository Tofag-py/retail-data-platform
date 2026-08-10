import json
import os
from dotenv import load_dotenv

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.window import TumblingProcessingTimeWindows
from pyflink.common import Time
from pyflink.datastream.functions import ProcessWindowFunction
from pyflink.common.watermark_strategy import WatermarkStrategy

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("MSK_BOOTSTRAP_BROKERS")
TOPIC_NAME = "clickstream-events"


class SessionSummary(ProcessWindowFunction):
    """For each session_id, summarize activity in this window and flag
    sessions with unusually high event counts as potentially bot-like."""

    BOT_THRESHOLD = 5  # more than this many events in one window looks automated

    def process(self, key, context, elements):
        events = list(elements)
        event_types = [e["event_type"] for e in events]
        count = len(events)
        flag = "SUSPICIOUS (bot-like)" if count > self.BOT_THRESHOLD else "normal"

        summary = {
            "session_id": key,
            "event_count": count,
            "event_types": event_types,
            "status": flag,
        }
        yield json.dumps(summary)


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    jar_dir = os.path.expanduser("~/flink-jars")
    jars = [
        f"file://{jar_dir}/flink-connector-kafka-5.0.0-2.2.jar",
        f"file://{jar_dir}/kafka-clients-3.7.0.jar",
    ]
    env.add_jars(*jars)

    kafka_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP_SERVERS)
        .set_topics(TOPIC_NAME)
        .set_group_id("flink-sessionizer")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    stream = env.from_source(
        kafka_source,
        watermark_strategy=WatermarkStrategy.no_watermarks(),
        source_name="kafka-clickstream-source",
    )

    parsed = stream.map(lambda raw: json.loads(raw))

    keyed = parsed.key_by(lambda event: event["session_id"])

    windowed = (
        keyed.window(TumblingProcessingTimeWindows.of(Time.seconds(30)))
        .process(SessionSummary())
    )

    windowed.print()

    env.execute("clickstream-sessionizer")


if __name__ == "__main__":
    main()