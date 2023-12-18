import json
import boto3

dynamodb_client = boto3.resource('dynamodb', region_name='us-east-1')
connected_users = dynamodb_client.Table("connected_users")
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    time = event["Records"][0]["eventTime"]
    users = connected_users.scan()['Items']
    print(event)
    print(f"Notifiying {users}")
    for batch in chunks(users, 100):
            invoke_separate_lambda_function(batch, time)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
def invoke_separate_lambda_function(batch, time):
    try:
        # Specify the ARN of the other Lambda function to invoke
        lambda_function_arn = 'arn:aws:lambda:us-east-1:254618925434:function:broadcast'

        # Prepare the payload to send to the other Lambda function
        payload = {
            'batch': batch,
            'eventTime': time
        }

        # Invoke the other Lambda function
        response = lambda_client.invoke(
            FunctionName=lambda_function_arn,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(payload)
        )

        print(f"Invoked Lambda function with response: {response}")
    except Exception as e:
        print(e)
        raise Exception('Error invoking separate Lambda function.')

def chunks(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]