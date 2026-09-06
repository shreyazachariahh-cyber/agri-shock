#!/bin/sh
set -eu

bootstrap_server="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

create_topic() {
  topic="$1"
  partitions="$2"
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "$bootstrap_server" \
    --create \
    --if-not-exists \
    --topic "$topic" \
    --partitions "$partitions" \
    --replication-factor 1
}

create_topic mandi-prices 3
create_topic weather-events 3
create_topic flood-events 1
create_topic market-shock-signals 3
create_topic dead-letter-events 1

echo "AgriShock Kafka topics are ready."
