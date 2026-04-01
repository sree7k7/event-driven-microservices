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

        ## create vpc endpoints for SQS, SNS, and DynamoDB 
        # to ensure that our Lambda functions can access these services without traversing the public internet, 
        # enhancing security and reducing latency.
        # This is especially important for the GenerateReceiptWorker Lambda, which needs to access the SQS Queue and DynamoDB Table, and the ProcessOrderWorker Lambda, which needs to access the SNS Topic and DynamoDB Table.
        self.vpc.add_interface_endpoint(
            "SqsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS
        )
        # ecs, ecr endpoint for ecs tasks to pull container images from ECR without traversing the public internet
        self.vpc.add_interface_endpoint(
            "ECSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECS
        )
        self.vpc.add_interface_endpoint(
            "endpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER
        )
        self.vpc.add_interface_endpoint(
            "ECREndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR
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

        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")


        ## ==========================================
        ## Security Groups
        ## ==========================================

        ## VPC security group to allow all outbound traffic (you will need to add the actual ingress rules later)
        self.vpc_sg = ec2.SecurityGroup(
            self,
            "VPCSecurityGroup",
            vpc=self.vpc,
            description="Allow all outbound traffic from VPC",
            allow_all_outbound=True
        )
        self.vpc_sg.connections.allow_from_any_ipv4(ec2.Port.all_traffic())

        # ## ECS tasks security group to allow all outbound traffic (you will need to add the actual ingress rules later)
        # self.ecs_tasks_sg = ec2.SecurityGroup(
        #     self,
        #     "ECSTasksSecurityGroup",
        #     vpc=self.vpc,
        #     description="Allow all outbound traffic from ECS tasks",
        #     allow_all_outbound=True
        # )
        # self.ecs_tasks_sg.connections.allow_from_any_ipv4(ec2.Port.all_traffic())

        # ## RDS security group to allow inbound traffic on port 5432 from ECS tasks security group (you will need to add the actual ingress rules later)
        # self.rds_sg = ec2.SecurityGroup(
        #     self,
        #     "RDSSecurityGroup",
        #     vpc=self.vpc,
        #     description="Allow all outbound traffic from RDS",
        #     allow_all_outbound=True
        # )
        # self.rds_sg.connections.allow_from_security_group(self.ecs_tasks_sg, ec2.Port.tcp(5432))

    