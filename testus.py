#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host=''))
channel = connection.channel()

channel.exchange_declare(exchange='alarms', exchange_type='fanout')
result = channel.queue_declare(queue='other', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange='alarms', queue=queue_name, routing_key='#')


def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)


channel.basic_consume(
    queue=queue_name, on_message_callback=callback, auto_ack=True)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()