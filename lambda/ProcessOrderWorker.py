import json
import boto3
import os
import uuid
import logging
from datetime import datetime

# Set up logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients outside the handler to keep them "warm" for faster execution
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

def lambda_handler(event, context):
    logger.info(f"Incoming API Request: {json.dumps(event)}")
    
    try:
        # 1. Load environment variables
        table_name = os.environ.get('TABLE_NAME')
        topic_arn = os.environ.get('TOPIC_ARN')
        
        # 2. Parse the body sent from the user (API Gateway wraps it in a string)
        body = json.loads(event.get('body', '{}'))
        item_name = body.get('item', 'Unknown Item')
        customer_email = body.get('email', 'sree7k7@gmail.com')
        
        # 3. Generate unique IDs and timestamps
        order_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # 4. Save the state to the Database
        table = dynamodb.Table(table_name)
        table.put_item(
            Item={
                'orderId': order_id,
                'item': item_name,
                'email': customer_email,
                'status': 'PLACED',
                'createdAt': timestamp
            }
        )
        logger.info(f"Success: Order {order_id} saved to DynamoDB.")
        
        # 5. Broadcast to the Nervous System (SNS)
        # We put the data in a dictionary, then turn it into a JSON string
        message_payload = {
            'orderId': order_id,
            'email': customer_email,
            'item': item_name,
            'action': 'GENERATE_RECEIPT'
        }
        
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message_payload),
            Subject=f"New Order Received: {order_id}"
        )
        logger.info(f"Success: Order {order_id} broadcasted to SNS.")
        
        # 6. Return the HTTP response to the user immediately
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Standard for web apps
            },
            'body': json.dumps({
                'message': 'Order successfully placed!', 
                'orderId': order_id
            })
        }
        
    except Exception as e:
        logger.error(f"Critical Failure: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error processing order.'})
        }