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
import aws_cdk.aws_dynamodb as dynamodb


class Database(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## For simplicity, we're using DynamoDB as our database. In a real-world application, you might use RDS or another database service.
        self.table = dynamodb.TableV2(
            self,
            "OrdersTable",
            table_name="CoffeeOrders",
            billing=dynamodb.Billing.on_demand(),
            partition_key=dynamodb.Attribute(name="sessionId", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY, # NOT recommended for production, use with caution
        )
