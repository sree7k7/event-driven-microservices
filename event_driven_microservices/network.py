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


class Network(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, sqs_queue, sns_topic_arn, dynamodb_table_name, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.vpc = ec2.Vpc(
            self,
            'BackupVPC',
            ip_addresses=ec2.IpAddresses.cidr(config['network']['vpc_cidr']),
            availability_zones=config['network']['availability_zones'],
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,                                   
                    cidr_mask=config['network']['cidr_mask']
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,                                   
                    cidr_mask=config['network']['cidr_mask']
                )
                ]
        )

        ## lambda funtion ProcessOrderWorker
        ##This function acts as the entry point. It handles the API Gateway request, writes to DynamoDB, and broadcasts the event to SNS.
        self.process_order_fn = lambdaFn.Function(
            self,
            "ProcessOrderWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_13,
            handler="ProcessOrderWorker.handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            environment={
                'TABLE_NAME': dynamodb_table_name,
                'TOPIC_ARN': sns_topic_arn
            }
        )

        ## lambda function GenerateReceiptWorker
        ## The ProcessOrderWorker Lambda shouts to the SNS Topic, which drops the message into the SQS Queue, which wakes up the GenerateReceiptWorker Lambda
        self.generate_receipt_fn = lambdaFn.Function(
            self,
            "GenerateReceiptWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_13,
            handler="GenerateReceiptWorker.handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            events=[
                lambdaFn_events.SqsEventSource(sqs_queue)
            ]
        )

        



        ## RDS database
        # self.db = ec2.DatabaseInstance(
        #     self,
        #     "Database",
        #     engine=ec2.DatabaseInstanceEngine.postgres(
        #         version=ec2.PostgresEngineVersion.VER_13_7
        #     ),
        #     vpc=self.vpc,
        #     vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
        #     credentials=ec2.Credentials.from_username(
        #         username=config['network']['db_username'],
        #         password=cdk.SecretValue.unsafe_plain_text(config['network']['db_password'])
        #     ),
        #     removal_policy=RemovalPolicy.DESTROY,
        #     deletion_protection=False,
        # )

### Multi-AZ DB instance deployment. This spins up a "standby" database in your second Availability Zone. If the primary database hardware catches fire, AWS instantly flips traffic to the standby one with zero downtime.

        # cluster = rds.DatabaseCluster(self, "Database",
        #     engine=rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_13_7),
        #     credentials=rds.Credentials.from_generated_secret("clusteradmin"),  # Optional - will default to 'admin' username and generated password
        #     writer=rds.ClusterInstance.provisioned("writer",
        #         publicly_accessible=False
        #     ),
        #     readers=[
        #         rds.ClusterInstance.provisioned("reader1", promotion_tier=1),
        #         rds.ClusterInstance.serverless_v2("reader2")
        #     ],
        #     vpc_subnets=ec2.SubnetSelection(
        #         subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        #     ),
        #     vpc=self.vpc,
        # )



        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")
