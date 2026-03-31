#!/usr/bin/env python3
import os
import aws_cdk as cdk

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
}

# Define the deployment environment
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT', '230150030147'), # TODO: Replace with your actual AWS Account ID
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
)

# 1. Provision foundational state and messaging (Independent Stacks)
messaging = Messaging(app, 'Messaging', config=microservices_config, env=env)
database = Database(app, 'Database', config=microservices_config, env=env)

# 2. Provision network (Independent Stack)
network = Network(app, 'Network', config=microservices_config, env=env)

# 3. Provision compute & API (Depends on the others)
app_stack = application_stack(
    app,
    'Application',
    vpc=network.vpc,
    sqs_queue=messaging.sqs_queue,
    sns_topic=messaging.sns_topic,
    dynamodb_table=database.table,
    config=microservices_config,
    env=env
)

app.synth()