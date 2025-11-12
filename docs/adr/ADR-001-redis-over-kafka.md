# ADR-001: Redis over Kafka for Event Queue

**Status:** Accepted
**Date:** 2025-11-11
**Deciders:** MUTT Development Team
**Technical Story:** Event queuing and inter-service communication

## Context and Problem Statement

MUTT requires a reliable message queue for event processing between the Ingestor, Alerter, and Moog Forwarder services. The system needs to handle tens of thousands of events per hour with low latency and simple operational overhead. Should we use Redis Lists/Streams or Apache Kafka?

## Decision Drivers

* Operational simplicity - minimize infrastructure complexity
* Low latency requirements (sub-second event processing)
* Event volume: ~10K-50K events/hour (not millions)
* Team expertise and operational maturity
* Integration with existing monitoring stack
* Cost and resource efficiency

## Considered Options

* Redis Lists with blocking pop (BLPOP/BRPOP)
* Redis Streams with consumer groups
* Apache Kafka with topics and partitions
* RabbitMQ with queues
* AWS SQS/SNS (cloud-native option)

## Decision Outcome

Chosen option: **Redis Lists with BLPOP/BRPOP**, because:

1. **Simplicity**: Redis is already required for rate limiting and circuit breaker state
2. **Performance**: Sub-millisecond latency for our event volume
3. **Operational maturity**: Team has strong Redis expertise
4. **Resource efficiency**: Single Redis cluster serves multiple purposes
5. **Proven at scale**: Successfully handles our 50K events/hour workload

### Positive Consequences

* Single infrastructure component for multiple use cases (queuing, caching, rate limiting)
* Low operational overhead - no separate Kafka cluster to maintain
* Simple debugging with redis-cli for queue inspection
* Atomic operations for exactly-once processing (BRPOPLPUSH)
* Fast recovery and rebalancing
* Lower memory footprint than Kafka for our event volume

### Negative Consequences

* No native multi-datacenter replication (requires Redis Enterprise or custom solution)
* Limited to single-consumer patterns without Redis Streams migration
* No built-in message replay beyond TTL (mitigated by event audit log)
* Potential scaling ceiling if event volume exceeds 100K events/hour

## Pros and Cons of the Options

### Redis Lists

* Good, because already deployed and monitored
* Good, because sub-millisecond latency
* Good, because atomic BRPOPLPUSH prevents message loss
* Good, because simple to debug and inspect
* Bad, because limited to ~100K messages/hour before needing horizontal scaling
* Bad, because no native pub/sub across datacenters

### Redis Streams

* Good, because supports consumer groups
* Good, because message replay capabilities
* Good, because maintains Redis operational simplicity
* Neutral, would require code refactor from current Lists implementation
* Bad, because more complex than Lists for our simple use case

### Apache Kafka

* Good, because designed for high-throughput event streaming
* Good, because multi-datacenter replication
* Good, because message replay and time-travel capabilities
* Bad, because adds significant operational complexity (ZooKeeper, brokers, topics, partitions)
* Bad, because overkill for 50K events/hour
* Bad, because higher resource requirements (memory, disk, compute)
* Bad, because team lacks Kafka operational expertise

### RabbitMQ

* Good, because designed as message broker
* Good, because supports complex routing patterns
* Neutral, similar complexity to Redis Streams
* Bad, because another infrastructure component to maintain
* Bad, because higher latency than Redis

### AWS SQS/SNS

* Good, because managed service (no infrastructure)
* Good, because scales automatically
* Bad, because vendor lock-in
* Bad, because higher latency due to network calls
* Bad, because cost at scale
* Bad, because not suitable for on-premise RHEL deployments

## Implementation Details

* **Queue naming**: `mutt:queue:events`, `mutt:queue:processing`, `mutt:queue:dlq`
* **Pattern**: Producer LPUSH, Consumer BRPOPLPUSH with timeout
* **Dead Letter Queue**: Failed events moved to DLQ after 3 retries
* **Monitoring**: Queue depth metrics exported to Prometheus
* **Backpressure**: Dynamic queue depth thresholds with load shedding

## Links

* [Redis Lists Documentation](https://redis.io/commands#list)
* [MUTT Queue Implementation](../../services/alerter_service.py)
* [Related: ADR-003 Single-Threaded Workers](ADR-003-single-threaded-workers.md)

## Notes

**Future Migration Path**: If event volume exceeds 100K/hour or multi-DC replication becomes critical, migration path is:
1. Evaluate Redis Streams (simpler migration)
2. If Streams insufficient, evaluate Kafka
3. Hybrid approach: Keep Redis for low-latency operations, add Kafka for cross-DC replication

**Monitoring**: Track `mutt_queue_depth` metric. Alert if depth >1000 sustained for >5 minutes.

## Change Log

* 2025-11-11: Initial draft and acceptance
