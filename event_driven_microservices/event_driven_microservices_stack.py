from aws_cdk import (
    Duration,
    SecretValue,
    Stack,
    Stage,
    aws_sqs as sqs,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk.pipelines import CodePipeline, CodePipelineSource, ShellStep
from aws_cdk import aws_ssm as ssm
# from event_driven_microservices import network
from event_driven_microservices.stage import Stage
from constructs import Construct

PUBLIC = ec2.SubnetType.PUBLIC
PRIVATE = ec2.SubnetType.PRIVATE_ISOLATED

class EventDrivenMicroservicesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.backend_repository = CodePipelineSource.git_hub(
            "sree7k7/event-driven-microservices",
            "main",
            authentication=SecretValue.secrets_manager("/github/token")
        )

        pipeline = CodePipeline(
            self,
            "MicroservicesPipelineStack",
            pipeline_name="event-driven-microservices",
            # cross_account_keys=True,
            self_mutation=True,
            synth=ShellStep("Synth",
                            input=self.backend_repository,
                            commands=[
                                "npm install -g aws-cdk",
                                # "python -m pip install -r requirements.txt",
                                "cdk synth",
                            ]
                            )        
        )

        ## Config parameters
        microservices_config= {
            "network": {
            "vpc_cidr": "10.0.0.0/16",
            "cidr_mask": 24,
            "availability_zones": ["us-east-1a", "us-east-1b"],
            "public_subnet_cidrs": ["10.0.1.0/24", "10.0.2.0/24"],
            "private_subnet_cidrs": ["10.0.3.0/24", "10.0.4.0/24"],
            "db_username": "admin",
            "db_password": ssm.StringParameter.value_from_lookup(self, "/db/password"),
            },
        }

        stage = pipeline.add_stage(Stage(
            self,
            "microservices-stage", #change
            config = microservices_config,
            # env=cdk.Environment(account=microservices_config['AWS_Account'], region="eu-central-1")
            )
        )
