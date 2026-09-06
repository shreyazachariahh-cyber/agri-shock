# Runtime matrix

## Chosen local demonstration matrix

| Component | Version | Why |
|---|---:|---|
| Python (Spark runtime) | 3.11.x | Conservative CPython target explicitly represented by the PySpark 3.5.6 package classifiers. |
| Python (core contracts) | 3.11–3.12 | The core library and unit suite currently run under 3.12; this is not evidence that the full Spark runtime is verified under 3.12. |
| JDK | 17 | Supported by Spark 3.5.6; choose the newest documented LTS option rather than Java 8. |
| Apache Spark / PySpark | 3.5.6 | Final 3.5 maintenance release with correctness/security fixes. |
| Scala binary | 2.12 | Required suffix for the Spark 3.5 Kafka connector artifact. |
| Delta Lake | 3.2.1 | Delta 3.2.x is documented as compatible with Spark 3.5.x. |
| Spark Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.6` | Exact Spark/Scala version alignment; loaded by Spark, not pip. |
| Kafka broker | 3.8.0 | Existing local Compose image; compatible with librdkafka-based clients. |
| Python Kafka client | confluent-kafka 2.9.0 | Mature librdkafka binding with prebuilt runtime for normal local use. |
| Elasticsearch / Kibana | 8.15.2 / 8.15.2 | Existing identical service versions avoid stack-version drift. |
| Python Elasticsearch client | 8.15.1 | Valid published 8.x client; compatible with the local Elasticsearch 8.15.2 server. |

## Python 3.12 decision

Spark 3.5.6 documentation states Python 3.8+ support, but its PyPI package
classifiers list Python through 3.11. The active host has Python 3.12 and it is
valid for the dependency-light contracts/tests, but the runnable Spark service
will use Python 3.11. This avoids claiming an unverified 3.12/PySpark/Delta
combination. The CI matrix will include 3.11 as the required runtime.

## Installation boundary

The Spark runtime must install the `streaming` extra inside its Python 3.11
environment. Java 17 must be available via `JAVA_HOME`. The Kafka connector is
a JVM package resolved by Spark using the exact Maven coordinate above; it is
not supplied by `confluent-kafka`.

## Evidence

Apache Spark 3.5.6 documents Java 8/11/17 and Python 3.8+ support. Delta Lake
documents Delta 3.2.x compatibility with Spark 3.5.x. See the linked primary
sources in the engineering decision log.
