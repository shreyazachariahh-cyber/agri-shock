# Kafka topology

## Listener design

The single local broker has two data listeners:

| Client location | Bootstrap address | Advertised address |
|---|---|---|
| Windows host | `localhost:9092` | `localhost:9092` |
| Compose network | `kafka:9092` | `kafka:9092` |

The host port maps to the broker's `EXTERNAL` listener on container port 29092.
Internal services never use `localhost`, because that would resolve to their own
containers. This separation matters after bootstrap: Kafka clients use broker
metadata containing advertised listener addresses for subsequent connections.

## Topics

| Topic | Local partitions | Partition key | Purpose and scale rationale |
|---|---:|---|---|
| `mandi-prices` | 3 | state/district/market | preserves market ordering and distributes active markets; high-volume markets can create skew. |
| `weather-events` | 3 | state/district | keeps district observations ordered while spreading state load. |
| `flood-events` | 1 | source event ID | low local-demo volume; production can increase partitions if event update throughput warrants it. |
| `market-shock-signals` | 3 | district/commodity | stable downstream/dashboard routing. |
| `dead-letter-events` | 1 | original event ID | retains the error sequence for one source event. |

`scripts/init-kafka-topics.sh` is idempotent through `--if-not-exists` and runs
as the Compose `kafka-init` service. The one-replica setting is a local demo
constraint; production requires replication factor at least three and suitable
`min.insync.replicas`.
