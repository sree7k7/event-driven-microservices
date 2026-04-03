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
# NEW: Swapped the SNS client for the EventBridge client
events_client = boto3.client('events')

def lambda_handler(event, context):
    logger.info(f"Incoming API Request: {json.dumps(event)}")
    
    try:
        # 1. Load environment variables
        table_name = os.environ.get('TABLE_NAME')
        event_bus_name = os.environ.get('EVENT_BUS_NAME') # <-- NEW: Event Bus Name
        
        # 2. Parse the body sent from the user (API Gateway wraps it in a string)
        body = json.loads(event.get('body', '{}'))
        item_name = body.get('item', 'Unknown Item')
        customer_email = body.get('email', 'sree7k7@gmail.com')
        
        # 3. Generate unique IDs and timestamps
        session_id = str(uuid.uuid4()) # This will be our partition key
        timestamp = datetime.utcnow().isoformat()
        
        # 4. Save the state to the Database
        table = dynamodb.Table(table_name)
        table.put_item(
            Item={
                'sessionId': session_id,
                'orderId': session_id, 
                'item': item_name,
                'email': customer_email,
                'status': 'PLACED',
                'createdAt': timestamp
            }
        )
        logger.info(f"Success: Order {session_id} saved to DynamoDB.")
        
        # 5. Broadcast to the Event Bus (EventBridge)
        # We put the data in a dictionary, then turn it into a JSON string
        message_payload = {
            'orderId': session_id,
            'email': customer_email,
            'item': item_name,
            'action': 'GENERATE_RECEIPT'
        }
        
        # NEW: Send the precisely formatted event to EventBridge
        events_client.put_events(
            Entries=[
                {
                    'Source': 'com.coffeeshop.orders', # The custom source of our event
                    'DetailType': 'OrderPlaced',       # The specific action that occurred
                    'Detail': json.dumps(message_payload), # Our actual business data
                    'EventBusName': event_bus_name     # The target bus
                }
            ]
        )
        logger.info(f"Success: Order {session_id} published to EventBridge.")
        
        # 6. Return the HTTP response to the user immediately
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Standard for web apps
            },
            'body': json.dumps({
                'message': 'Order successfully placed!, ', 
                'orderId': session_id
            })
        }
    except Exception as e:
        logger.error(f"Critical Failure: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error processing order.'})
        }