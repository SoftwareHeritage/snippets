import click
import sys
import threading
import time
from confluent_kafka import Consumer
from confluent_kafka import KafkaException
from confluent_kafka import TopicPartition
import redis
import msgpack


redis_time = 0
collection: str
redis_client: redis.Redis
local_counter: int
mutex = threading.Lock()


def consume(conf, topic, batch_size):
    global redis_time
    global collection
    global local_counter

    consumer = Consumer(conf)

    consumer.subscribe([topic])

    click.echo("Starting consuming messages on %s..." % topic)
    while True:
        messages = consumer.consume(num_messages=batch_size)
        if messages is None:
            click.echo("timeout", err=True)
            continue
        # click.echo("batch read")

        for message in messages:

            key = message.key()
            # click.echo(str(key[0] % 10))
            # click.echo(str(key))
            # click.echo(str(msgpack.unpackb(key, raw=True)))

            before_time = time.perf_counter()
            redis_client.pfadd(collection, key)

            redis_time += time.perf_counter() - before_time

        consumer.commit(asynchronous=True)
        with mutex:
            local_counter = local_counter + len(messages)


def display_counter(click):
    global redis_time
    global collection
    global local_counter

    last_count = redis_client.pfcount(collection)
    last_redis_time = redis_time
    last_time = time.perf_counter()

    while True:
        time.sleep(5)
        current_redis_time = redis_time
        redis_counter = redis_client.pfcount(collection)
        current_time = time.perf_counter()
        duration = current_time - last_time
        last_time = current_time

        message_per_seconds = (local_counter - last_count) / duration

        prefix = time.strftime("%m-%d-%Y %H:%M:%S", time.localtime())

        click.echo(
            "%s local_counter=%d redis_counter=%d (%dm/s redis: %fs)"
            % (
                prefix,
                local_counter,
                redis_counter,
                message_per_seconds,
                current_redis_time - last_redis_time,
            )
        )
        last_count = local_counter
        last_redis_time = current_redis_time


@click.command()
@click.option("-g", "--consumer-group", required=True)
@click.option("-t", "--topic", required=True)
@click.option("-b", "--broker", required=True)
@click.option("-c", "--threads", default=1)
@click.option("--batch-size", default=100)
@click.option("-r", "--redis-host", default="localhost")
@click.option("-p", "--redis-port", default=6379)
def count(consumer_group, topic, broker, threads, batch_size, redis_host, redis_port):
    global local_counter
    global collection
    global redis_client

    pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=0)
    redis_client = redis.Redis(connection_pool=pool)

    collection = topic.split(".")[-1]

    conf = {
        "bootstrap.servers": broker,
        "group.id": consumer_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }

    consumer = Consumer(conf)

    try:
        topic_metadata = consumer.list_topics(topic)
    except KafkaException as e:
        click.echo(e, err=True)
        exit(1)

    partitions = topic_metadata.topics[topic].partitions

    click.echo("%d partition(s) found" % len(partitions))

    local_counter = redis_client.pfcount(collection)
    click.echo("Local counter intialized with last redis value : %d" % local_counter)

    threading.Thread(target=display_counter, args=(click,)).start()

    for _ in range(threads):
        threading.Thread(target=consume, args=(conf, topic, batch_size)).start()


if __name__ == "__main__":
    count()
