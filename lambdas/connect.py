import json
import boto3

dynamodb_client = boto3.resource('dynamodb', region_name='us-east-1')
users = dynamodb_client.Table("connected_users")
def lambda_handler(event, context):
    # TODO implement
    print(event)
    print(context)
    users.put_item(Item={"connectionID": event["requestContext"]["connectionId"]})
    return {
        'statusCode': 200,
        'body': json.dumps('Hello!')
    }
