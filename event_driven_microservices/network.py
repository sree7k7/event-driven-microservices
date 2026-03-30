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
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
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


        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")
