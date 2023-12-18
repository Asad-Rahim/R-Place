import json
import boto3
from concurrent.futures import ThreadPoolExecutor

dynamodb_client = boto3.resource('dynamodb', region_name='us-east-1')
users = dynamodb_client.Table("connected_users")

def lambda_handler(event, context):
    client = boto3.client('apigatewaymanagementapi', endpoint_url="https://sjdud7kfbc.execute-api.us-east-1.amazonaws.com/production/")
    print(event)
    connected_users = event["batch"]
    time = event["eventTime"]
    print(f"Broadcasting to {connected_users}")
    for user in connected_users:
        client.post_to_connection(
            ConnectionId=user['connectionID'],
            Data=json.dumps({'message': time})
        )

    return {
        'statusCode': 200,
        'body': 'Messages sent successfully'
    }

