#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import aws_logs as logs

# Import your individual stacks directly
from event_driven_microservices.network import Network
from event_driven_microservices.messaging import Messaging
from event_driven_microservices.database import Database
from event_driven_microservices.application_stack import application_stack

app = cdk.App()

# Your core configuration
microservices_config = {
    "network": {
        "vpc_cidr": "10.0.0.0/16",
        "cidr_mask": 24,
        "availability_zones": ["us-east-1a", "us-east-1b"],
        "public_subnet_cidrs": ["10.0.1.0/24", "10.0.2.0/24"],
        "private_subnet_cidrs": ["10.0.3.0/24", "10.0.4.0/24"],
    },
    "messaging": {
        "event_bus_name": "ReceiptEventBus",
    },
    "database": {
        "dynamodb_table_name": "CoffeeOrders",
        # "rds_instance_type": "t3.micro",
        # "cache_node_type": "cache.t3.micro",
        # "cache_num_nodes": 1
    },
    "application": {
        "domain_name": "srikanth.help", ## chanage based on your actual domain
        "subdomain": "coffeeshop",
        "apigw_name": "CoffeeShopAPI",
        "lambda_timeout": 30,
        "lambda_memory": 512,
        "ecs_cluster_name": "CoffeeShopEcsCluster",
        "ecs_task_definition_family": "CoffeeShopTaskDefinition",
        "ecs_task_cpu": 256,
        "ecs_task_memory": 512, 
        "ecr_repository_name": "coffeeshop-app", # create in manual or via CLI before deploying
        "X-ray-tracing_repo": "xray-daemon", 
        "alb_name": "CoffeeShopALB",
        "alb_security_group_name": "AlbSecurityGroup",
        "ecs_service_security_group_name": "EcsSecurityGroup",
        "log_retention_days": logs.RetentionDays.ONE_DAY,        
    }
}

# Define the deployment environment
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT', '230150030147'), # TODO: Replace with your actual AWS Account ID
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
)

# 1. Provision foundational state and messaging (Independent Stacks)
messaging = Messaging(app, 'Messaging', config=microservices_config, env=env)

# 2. Provision network (Independent Stack)
network = Network(
    app, 
    'Network', 
    config=microservices_config, 
    env=env
)

database = Database(
    app, 
    'Database', 
    vpc=network.vpc, 
    config=microservices_config, env=env
)

# 3. Provision compute & API (Depends on the others)
app_stack = application_stack(
    app,
    'Application',
    vpc=network.vpc,
    sqs_queue=messaging.sqs_queue,
    event_bus=messaging.events,
    dynamodb_table=database.table,
    rds_sg=database.rds_sg,
    valkey_sg=database.valkey_sg,
    valkey_cluster=database.cache_cluster,
    db_secret=database.db_instance.secret,
    config=microservices_config,
    env=env
)

app.synth()