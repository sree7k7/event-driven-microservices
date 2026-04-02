import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct


class Network(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## ==========================================
        ## VPC and Subnets
        ## ==========================================
        
        self.vpc = ec2.Vpc(
            self,
            'VPC',
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

                ## Create a dedicated Security Group for all Interface VPC Endpoints
        self.vpc_endpoints_sg = ec2.SecurityGroup(
            self,
            "VpcEndpointsSg",
            vpc=self.vpc,
            description="Security Group for Interface VPC Endpoints"
        )
        self.vpc_endpoints_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic from within the VPC (including ECS tasks)"
        )

        ## create vpc endpoints for SQS, SNS, and DynamoDB 
        # to ensure that our Lambda functions can access these services without traversing the public internet, 
        # enhancing security and reducing latency.
        # This is especially important for the GenerateReceiptWorker Lambda, which needs to access the SQS Queue and DynamoDB Table, and the ProcessOrderWorker Lambda, which needs to access the SNS Topic and DynamoDB Table.
        self.vpc.add_interface_endpoint(
            "SqsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS,
            security_groups=[self.vpc_endpoints_sg],
            open=True
        )
        # ecs, ecr endpoint for ecs tasks to pull container images from ECR without traversing the public internet
        self.vpc.add_interface_endpoint(
            "ECSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECS,
            security_groups=[self.vpc_endpoints_sg],
            open=True
        )
        self.vpc.add_interface_endpoint(
            "endpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            security_groups=[self.vpc_endpoints_sg],
            open=True

        )
        self.vpc.add_interface_endpoint(
            "ECREndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            security_groups=[self.vpc_endpoints_sg],
            open=True

        )
        ## Secrets manager endpoint for ECS to retrieve the RDS credentials securely
        self.vpc.add_interface_endpoint(
            "SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            security_groups=[self.vpc_endpoints_sg],
            open=True

        )
        ## CloudWatch Logs endpoint for ECS to send container logs securely
        self.vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            security_groups=[self.vpc_endpoints_sg],
            open=True

        )
        ## dynamodb endpoint for dynamodb tables to be accessed from within the VPC
        self.vpc.add_gateway_endpoint(
            "DynamoDBVPCEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )        

        ## s3 endpoint for s3 buckets to be accessed from within the VPC
        self.vpc.add_gateway_endpoint(
            "S3VPCEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3
        )

        ## x-ray endpoint for x-ray to be accessed from within the VPCcom.amazonaws.us-east-1.xray
        self.vpc.add_interface_endpoint(
            "XRayEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.XRAY,
            security_groups=[self.vpc_endpoints_sg],
            open=True
        )

        ## SSM Messages endpoint required for ECS Exec to work in isolated subnets
        self.vpc.add_interface_endpoint(
            "SSMMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            security_groups=[self.vpc_endpoints_sg],
            open=True
        )

        ## ssm endpoint required for ECS Exec to work in isolated subnets
        self.vpc.add_interface_endpoint(
            "SSMEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            security_groups=[self.vpc_endpoints_sg],
            open=True
        )

        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")