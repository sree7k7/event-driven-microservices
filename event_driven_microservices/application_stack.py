import random
import this
import constructs
import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
import aws_cdk.aws_rds as rds
import aws_cdk.aws_lambda as lambdaFn
import aws_cdk.aws_lambda_event_sources as lambdaFn_events
import aws_cdk.aws_sqs as sqs

## compute stack is where we define our compute resources, in this case, our lambda functions. We also define the event source for the GenerateReceiptWorker Lambda, which is the SQS Queue created in the Messaging stack. The ProcessOrderWorker Lambda is triggered by API Gateway, which we'll set up in a later step.
class application_stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, sqs_queue, sns_topic, dynamodb_table, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        

        ## lambda funtion ProcessOrderWorker
        ##This function acts as the entry point. It handles the API Gateway request, writes to DynamoDB, and broadcasts the event to SNS.
        self.process_order_fn = lambdaFn.Function(
            self,
            "ProcessOrderWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="ProcessOrderWorker.handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            environment={
                'TABLE_NAME': dynamodb_table.table_name,
                'TOPIC_ARN': sns_topic.topic_arn
            }
        )

        ## lambda function GenerateReceiptWorker
        ## The ProcessOrderWorker Lambda shouts to the SNS Topic, which drops the message into the SQS Queue, which wakes up the GenerateReceiptWorker Lambda
        self.generate_receipt_fn = lambdaFn.Function(
            self,
            "GenerateReceiptWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="GenerateReceiptWorker.handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            events=[
                lambdaFn_events.SqsEventSource(sqs_queue)
            ]
        )
