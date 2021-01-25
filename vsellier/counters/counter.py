import click
import sys
import threading
import time
from confluent_kafka import Consumer
from confluent_kafka import KafkaException
from confluent_kafka import TopicPartition
import redis

redis_time=0
collection: str
redis_client: redis.Redis

def consume(conf, topic, batch_size):
    global redis_time
    global collection

    consumer = Consumer(conf)

    consumer.subscribe([topic])

    click.echo("Starting consuming messages on %s..."%topic)
    local_counter = 0
    while True:
        messages = consumer.consume(num_messages=batch_size)
        if messages is None:
            click.echo("timeout", err=True)
            continue
        # click.echo("batch read")

        for message in messages:

            key = message.key()
            # click.echo(key)

            before_time = time.perf_counter()
            redis_client.pfadd(collection, key)
        
            redis_time += time.perf_counter() - before_time
        consumer.commit(asynchronous=True)

def display_counter(click):
    global redis_time
    global collection

    last_count = redis_client.pfcount(collection)
    last_redis_time = redis_time
    last_time = time.perf_counter()

    while True:
        time.sleep(5)
        current_redis_time = redis_time
        current_count = redis_client.pfcount(collection)
        current_time = time.perf_counter()
        duration = current_time - last_time
        last_time = current_time

        message_per_seconds = (current_count - last_count) / duration

        prefix = time.strftime("%m-%d-%Y %H:%M:%S", time.localtime())

        click.echo("%s count=%d (%dm/s redis: %fs)"%(prefix, current_count, message_per_seconds, current_redis_time-last_redis_time))
        last_count = current_count
        last_redis_time = current_redis_time


@click.command()
@click.option('-g', '--consumer-group', required=True)
@click.option('-t', '--topic', required=True)
@click.option('-b', '--broker', required=True)
@click.option('-c', '--threads', default=1)
@click.option('--batch-size', default=100)
@click.option('-r', '--redis-host', default="localhost")
@click.option('-p', '--redis-port', default=6379)
def count(consumer_group, topic, broker, threads, batch_size, redis_host, redis_port):
    global counter
    global collection
    global redis_client

    pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=0)
    redis_client = redis.Redis(connection_pool=pool)

    collection = topic.split(".")[-1]

    conf = {'bootstrap.servers': broker,
            'group.id': consumer_group,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False}

    consumer = Consumer(conf)
    
    try:
        topic_metadata = consumer.list_topics(topic)
    except KafkaException:
        click.echo(e, err=True)
        exit(1)

    partitions = topic_metadata.topics[topic].partitions

    click.echo("%d partition(s) found"%len(partitions))
    
    display = threading.Thread(target=display_counter, args=(click,)).start()

    for t in range(threads):
      threading.Thread(target=consume, args=(conf, topic, batch_size)).start()

if __name__ == "__main__":
    count()
