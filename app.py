#!/usr/bin/env python3
import os
import aws_cdk as cdk
from event_driven_microservices.stage import Stage

app = cdk.App()

# Your core configuration (moved out of the old pipeline stack)
microservices_config = {
    "network": {
        "vpc_cidr": "10.0.0.0/16",
        "cidr_mask": 24,
        "availability_zones": ["us-east-1a", "us-east-1b"],
        "public_subnet_cidrs": ["10.0.1.0/24", "10.0.2.0/24"],
        "private_subnet_cidrs": ["10.0.3.0/24", "10.0.4.0/24"],
        # Note: We removed the SSM lookup for the DB password here. 
        # If you add RDS back later, do the SSM lookup directly inside database.py!
    },
}

# Deploy the Stage directly to your AWS Account
appstage = Stage(
    app, 
    "ProdStage", 
    config=microservices_config,
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

app.synth()