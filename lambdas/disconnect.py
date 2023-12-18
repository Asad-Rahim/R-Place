import json
import boto3

dynamodb_client = boto3.resource('dynamodb', region_name='us-east-1')
users = dynamodb_client.Table("connected_users")

def lambda_handler(event, context):
    print(event)
    print(context)
    connectionID = event["requestContext"]["connectionId"]
    try:
        users.delete_item(Key={"connectionID": connectionID})
        print(f"{connectionID} successfully removed")
    except Exception as e:
        print(f"Error removing {connectionID}: {e}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Goodbye')
    }
