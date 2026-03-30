import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_integrations as integrations



class Network(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id)
        
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

        ## create vpc endpoints for SQS, SNS, and DynamoDB 
        # to ensure that our Lambda functions can access these services without traversing the public internet, 
        # enhancing security and reducing latency.
        # This is especially important for the GenerateReceiptWorker Lambda, which needs to access the SQS Queue and DynamoDB Table, and the ProcessOrderWorker Lambda, which needs to access the SNS Topic and DynamoDB Table.
        self.vpc.add_interface_endpoint(
            "SqsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS
        )
        self.vpc.add_interface_endpoint(
            "SNSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SNS
        )
        self.vpc.add_gateway_endpoint(
            "DynamoDBVPCEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )        

        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")
