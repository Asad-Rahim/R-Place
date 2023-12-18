import boto3
import os
import threading
import requests
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import logging
import redis
import numpy as np
from PIL import Image
from io import BytesIO


COLORS={
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "lime": (0, 255, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "magenta": (255, 0, 255),
        "cyan": (0, 255, 255),
        "maroon": (128, 0, 0),
        "green": (0, 128, 0),
        "navy": (0, 0, 128),
        "olive": (128, 128, 0),
        "purple": (128, 0, 128),
        "teal": (0, 128, 128),   
        "silver": (192, 192, 192),  
        "gray": (128, 128, 128),  
        "black": (0, 0, 0)      
        }
# AWS region
aws_region = 'us-east-1'

# Set up logging
logging.basicConfig(filename='logs/log_file', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SQS configuration
sqs_queue_url = 'https://sqs.us-east-2.amazonaws.com/254618925434/canvasUpdates.fifo'
dlq_url = 'https://sqs.us-east-1.amazonaws.com/254618925434/canvasUpdatesDQL.fifo'

# Redis configuration
primary_redis_endpoint = 'redis-001.wicy8d.0001.use1.cache.amazonaws.com'

reader_redis_endpoints = ['redis-002.wicy8d.0001.use1.cache.amazonaws.com',
                          'redis-003.wicy8d.0001.use1.cache.amazonaws.com']
redis_port = 6379
primary_redis_client = redis.StrictRedis(host=primary_redis_endpoint, port=redis_port, decode_responses=True)
reader_redis_clients = [redis.StrictRedis(host=reader_redis_endpoint, port=redis_port, decode_responses=True)
                        for reader_redis_endpoint in reader_redis_endpoints
                        ]

# S3 configuration
s3_bucket_name = 'canvasimages409'
s3_key_prefix = 'images/'

# Create a 1D array of white pixels
pixel_values = [(255, 255, 255)] * (1000 * 1000)

# Reshape the 1D array into a 2D array with dimensions 1000x1000
pixel_array = np.array(pixel_values).reshape((1000, 1000, 3))

# Initialize AWS clients using automatic EC2 instance role credentials
sqs_client = boto3.client('sqs', region_name=aws_region)
dynamodb_client = boto3.resource('dynamodb', region_name=aws_region)
s3_client = boto3.client('s3', region_name=aws_region)
agigateway_client = boto3.client('apigatewaymanagementapi', 
                endpoint_url="https://tupd3rpfel.execute-api.us-east-1.amazonaws.com/production",
                region_name=aws_region)

canvas_table = dynamodb_client.Table("canvas_pixels")
connected_users = dynamodb_client.Table("connected_users")

def fetch_pixels_from_dynamodb():
    response = canvas_table.scan()

    pixel_values = []
    pixel_colors = []

    for item in response.get('Items', []):
        pixel_values.append(item['pixel'])
        pixel_colors.append(COLORS[item['color']])

    # Populate the pixel array with values and colors
    for value, color in zip(pixel_values, pixel_colors):
        # Assuming pixel values are indices within the pixel_array
        row, col = value.split(",")
        if int(row)>= 0 and int(row)<1000 and int(col)>=0 and int(col) < 1000:
            pixel_array[int(col), int(row)] = color
        else:
            canvas_table.delete_item(Key={"pixel": value})
    logging.info("Recreated canvas from DB")

def read_message_from_sqs():
    response = sqs_client.receive_message(
        QueueUrl=sqs_queue_url,
        AttributeNames=['All'],
        MaxNumberOfMessages=1,
        MessageAttributeNames=['All'],
        VisibilityTimeout=10,
        WaitTimeSeconds=20
    )
    messages = response.get('Messages', [])
    if messages:
        message = messages[0]
        logging.info(f"Incoming message {message}")
        return message
    else:
        return None

def create_image_and_upload_to_s3(pixel_array):
    image = Image.fromarray(pixel_array.astype(np.uint8))
    
    # Upload the image to S3
    s3_key = s3_key_prefix + 'canvas.png'
    upload_image_to_s3(image, s3_bucket_name, s3_key)

def upload_image_to_s3(image, bucket_name, key):
    # Save the image to a byte buffer
    image_buffer = BytesIO()
    image.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    # Upload the image to S3
    s3_client.put_object(Body=image_buffer, Bucket=bucket_name, Key=key, ContentType='image/png')
    logging.info("Uploaded new canvas to S3")

def update_dynamodb(x,y, color):
    goodKey={"pixel": f'{x},{y}', 'color': color}
    
    pixel = canvas_table.get_item(Key={'pixel':f'{x},{y}'})
    
    if 'Item' in pixel:
        canvas_table.update_item(Key={'pixel':f'{x},{y}'}, 
        UpdateExpression="SET color =:color",
        ExpressionAttributeValues={":color":color})
    else:
        canvas_table.put_item(Item=goodKey)
    pixel_array[int(y), int(x)] = COLORS[color]
    logging.info(f"Updating {x},{y} with {color}")

def bad_message_body(message_body):
    return  'x' not in message_body or str(int(message_body['x'])) != message_body['x'] or \
            int(message_body['x']) <0 or int(message_body['x'])>=1000 or \
            'y' not in message_body or str(int(message_body['x'])) != message_body['x'] or \
            int(message_body['y']) <0 or int(message_body['y'])>=1000 or \
            'color' not in message_body or message_body['color'] not in COLORS or \
            'clientID' not in message_body

def read_client_id_from_random_redis_client(client_id):
    redis_index = random.randint(0, len(reader_redis_clients) - 1)
    i =0
    while i < len(reader_redis_clients):
        i+=1
        try:
            redis_client = reader_redis_clients[redis_index]
            
            value = redis_client.exists(client_id)
            return value
        except redis.exceptions.ConnectionError:
            logging.error(f"Unable to connect to {reader_redis_endpoints[redis_index]}")
            redis_index = (redis_index + 1)% len(reader_redis_clients)
    logging.error("Unable to connect to all redis clients")
    return False

def get_key_from_random_redis_client(key):
    redis_index = random.randint(0, len(reader_redis_clients) - 1)
    i =0
    while i < len(reader_redis_clients):
        i+=1
        try:
            redis_client = reader_redis_clients[redis_index]
            
            value = redis_client.get(key)
            return value
        except redis.exceptions.ConnectionError:
            logging.error(f"Unable to connect to {reader_redis_endpoints[redis_index]}")
            redis_index = (redis_index + 1)% len(reader_redis_clients)
    logging.error("Unable to connect to all redis clients")
    return ""

def getDel(key, retries=5):
    for i in range(retries):
        with primary_redis_client.pipeline() as pipe:
            try:
                pipe.watch(key)  # Watch the key for changes
                value = pipe.get(key)
                pipe.multi()  # Start a transaction
                pipe.delete(key)
                pipe.execute()  # Execute the transaction
                return value
            except redis.exceptions.WatchError:
                logging.info(f"Someone else accessed {key} trying again")
    logging.error(f"Failed to perform getDel with {key}")
    return None

def publish_change(publish_to, x,y):
    logging.info(f"Publishing change of {x},{y} to {publish_to}")
    for subscriber in publish_to:
        primary_redis_client.append(subscriber, f'|{x},{y}')

def get_all_changes(subscribed_to):
    pixels = set([])
    for publisher in subscribed_to:
        val = getDel(publisher)
        if val:
            for pixel in val[1:].split("|"):
                pixels.add(pixel)
    if len(pixels)==0:
        return 
    logging.info(f"All changes to be made:{pixels}")
    response = dynamodb_client.batch_get_item(
        RequestItems={
            "canvas_pixels": {
                'Keys': [{'pixel': key} for key in pixels]
            }
        }
    )
    for item in response.get('Responses', {}).get("canvas_pixels", []):
        x,y = item['pixel'].split(',')
        color = item['color']
        pixel_array[int(y), int(x)] = COLORS[color]

def read_config_from_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        node_number = int(lines[0].strip())
    return node_number

def main():
    node_number = read_config_from_file("/app/config/config_file")
    fetch_pixels_from_dynamodb()
    while True:
        try:
            publish_to= get_key_from_random_redis_client(f"{node_number}_PUBLISHED_TO").split(",")
            subscribed_to=get_key_from_random_redis_client(f"{node_number}_SUBSCRIBED_TO").split(",")
            # Read message from SQS
            message = read_message_from_sqs()
            if message:
                receipt_handle = message['ReceiptHandle']
                if 'Body' not in message:
                    logging.info("Sending message to DLQ")
                    sqs_client.send_message(
                        QueueUrl=dlq_url,
                        MessageBody=message,
                        MessageAttributes=message.get('MessageAttributes', {}),
                        MessageGroupId=message.get('Attributes', {}).get('MessageGroupId'),
                        MessageDeduplicationId=message.get('Attributes', {}).get('MessageDeduplicationId')
                    )
                    sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=receipt_handle)
                    continue
                
                message_body = json.loads(message['Body'])
                if bad_message_body(message_body):
                    logging.info("Sending message to DLQ")
                    sqs_client.send_message(
                        QueueUrl=dlq_url,
                        MessageBody=message['Body'],
                        MessageAttributes=message.get('MessageAttributes', {}),
                        MessageGroupId=message.get('Attributes', {}).get('MessageGroupId'),
                        MessageDeduplicationId=message.get('Attributes', {}).get('MessageDeduplicationId')
                    )
                    sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=receipt_handle)
                    continue
                
                client_id = message_body.get('clientID')

                if not read_client_id_from_random_redis_client(client_id):
                    primary_redis_client.setex(client_id, 300, time.time())
                    try:
                        get_all_changes(subscribed_to)
                        update_dynamodb(message_body.get('x'), message_body.get('y'), message_body.get('color'))
                        create_image_and_upload_to_s3(pixel_array)
                        publish_change(publish_to, message_body.get('x'), message_body.get('y'))
                        sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=receipt_handle)
                    except Exception as e:
                        primary_redis_client.delete(client_id)
                        logging.error(f"An error occurred: {str(e)}")
                        logging.error(traceback.format_exc())
                    
                else:
                    logging.info(f"Timer for {client_id} hasn't expired. Not processing message.")
                    sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=receipt_handle)
            get_all_changes(subscribed_to)
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            logging.error(traceback.format_exc())

        

if __name__ == "__main__":
    main()
