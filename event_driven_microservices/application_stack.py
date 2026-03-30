import aws_cdk as cdk
from aws_cdk import RemovalPolicy, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from aws_cdk import aws_logs as logs
import aws_cdk.aws_lambda as lambdaFn
import aws_cdk.aws_lambda_event_sources as lambdaFn_events
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_integrations as integrations

## compute stack is where we define our compute resources, in this case, our lambda functions. We also define the event source for the GenerateReceiptWorker Lambda, which is the SQS Queue created in the Messaging stack. The ProcessOrderWorker Lambda is triggered by API Gateway, which we'll set up in a later step.
class application_stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, sqs_queue, sns_topic, dynamodb_table, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        

        ## This configuration ensures that logs are structured in JSON format, making it easier to query and
        process_order_fn_logs = logs.LogGroup(
            self,
            "ProcessOrderWorkerLogs",
            log_group_name="/aws/lambda/ProcessOrderWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        ## logging configuration for structured logging for the GenerateReceiptWorker Lambda
        generate_receipt_fn_logs = logs.LogGroup(
            self,
            "GenerateReceiptWorkerLogs",
            log_group_name="/aws/lambda/GenerateReceiptWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        ## lambda funtion ProcessOrderWorker
        ##This function acts as the entry point. It handles the API Gateway request, writes to DynamoDB, and broadcasts the event to SNS.
        self.process_order_fn = lambdaFn.Function(
            self,
            "ProcessOrderWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="ProcessOrderWorker.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            timeout=cdk.Duration.seconds(10),
            environment={
                'TABLE_NAME': dynamodb_table.table_name,
                'TOPIC_ARN': sns_topic.topic_arn
            },
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=process_order_fn_logs, # Use the defined log group for structured logging
        )

        ## lambda function ReceiptGenerator
        ## The ProcessOrderWorker Lambda shouts to the SNS Topic, which drops the message into the SQS Queue, which wakes up the ReceiptGenerator Lambda
        self.generate_receipt_fn = lambdaFn.Function(
            self,
            "ReceiptGenerator",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="ReceiptGenerator.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            timeout=cdk.Duration.seconds(10),
            events=[
                lambdaFn_events.SqsEventSource(sqs_queue)
            ],
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=generate_receipt_fn_logs, # Use the defined log group for structured logging
        )

        ## Grant the necessary permissions
        dynamodb_table.grant_read_write_data(self.process_order_fn)
        sns_topic.grant_publish(self.process_order_fn)
        sqs_queue.grant_send_messages(self.generate_receipt_fn)
        sqs_queue.grant_consume_messages(self.generate_receipt_fn)

        # ==========================================
        # API GATEWAY (The VIP Host - HTTP API v2)
        # ==========================================

# 1. Create the HTTP API
        self.http_api = apigwv2.HttpApi(
            self,
            "OrderHttpApi",
            api_name="Order Processing HTTP API",
            description="The modern, fast front door for the event-driven system.",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.POST, 
                    apigwv2.CorsHttpMethod.OPTIONS
                ]
            )
        )

        # 2. Define the Integration (using the lambda created directly above)
        process_order_integration = integrations.HttpLambdaIntegration(
            "ProcessOrderIntegration",
            handler=self.process_order_fn
        )

        # 3. Create the Route and attach the integration
        self.http_api.add_routes(
            path="/orders",
            methods=[apigwv2.HttpMethod.POST],
            integration=process_order_integration
        )
        
        # 4. Output the URL
        cdk.CfnOutput(
            self, 
            "HttpApiEndpointUrl", 
            value=self.http_api.url,
            description="The URL of the HTTP API Gateway"
        )
    