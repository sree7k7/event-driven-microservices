import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Background Worker Waking Up...")
    
    # SQS sends messages in 'Records' (batches of up to 10 at a time)
    for record in event.get('Records', []):
        try:
            # 1. Parse the outer SQS Envelope
            sqs_body = json.loads(record['body'])
            
            # 2. Parse the inner SNS Envelope
            # Because SNS forwarded this to SQS, the actual payload is inside the 'Message' key
            sns_message_string = sqs_body.get('Message')
            
            if not sns_message_string:
                logger.warning("No SNS Message found. Skipping record.")
                continue
                
            # 3. Parse our actual application data
            payload = json.loads(sns_message_string)
            order_id = payload.get('orderId', 'N/A')
            email = payload.get('email', 'N/A')
            item = payload.get('item', 'N/A')
            
            # 4. Execute the Business Logic
            logger.info("=========================================")
            logger.info(f"STARTING RECEIPT GENERATION")
            logger.info(f"Target Order ID: {order_id}")
            logger.info(f"Customer Email:  {email}")
            logger.info(f"Purchased Item:  {item}")
            logger.info("Generating PDF... Connecting to email server... Sending...")
            logger.info("RECEIPT SUCCESSFULLY DELIVERED")
            logger.info("=========================================")
            
        except Exception as e:
            logger.error(f"Failed to process message: {str(e)}")
            # By raising the error, we tell SQS this failed. 
            # SQS will put the message back in the queue to try again later!
            raise e

    # Tell SQS the whole batch is done so it can delete the messages
    return {
        'statusCode': 200,
        'body': json.dumps('Queue batch processed successfully.')
    }