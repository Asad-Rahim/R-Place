import json
import boto3
import urllib3
client = boto3.client('apigatewaymanagementapi', endpoint_url="https://tupd3rpfel.execute-api.us-east-1.amazonaws.com/production")
sqs = boto3.client('sqs')

def lambda_handler(event, context):
    print(event)
    print(context)
    
    #Extract connectionId from incoming event
    connectionId = event["requestContext"]["connectionId"]
    body_dict = json.loads(event['body'])
    body_dict['clientID'] = connectionId
    
    sqs = boto3.client('sqs')
    sqs.send_message(
        QueueUrl="https://sqs.us-east-2.amazonaws.com/254618925434/canvasUpdates.fifo",
        MessageBody=json.dumps(body_dict),
        MessageGroupId="updates"
    )
    
    responseObject = {}
    responseObject['statusCode'] = 200
    responseObject['headers'] = {}
    responseObject['headers']['Content-Type'] = 'application/json'
    responseObject['body'] = json.dumps(f'sent update to sqs')
    
    
    
    return responseObject
