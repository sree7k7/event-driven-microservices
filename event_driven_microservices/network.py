import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_integrations as integrations



class Network(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, process_order_fn, **kwargs) -> None:
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


        # ==========================================
        # API GATEWAY (The VIP Host - HTTP API v2)
        # ==========================================
        
        # 1. Create the HTTP API
        self.http_api = apigwv2.HttpApi(
            self,
            "OrderHttpApi",
            api_name="Order Processing HTTP API",
            description="The modern, fast front door for the event-driven system.",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.POST, 
                    apigwv2.CorsHttpMethod.OPTIONS
                ]
            )
        )

        # # 2. Define the Integration
        # process_order_integration = integrations.HttpLambdaIntegration(
        #     "ProcessOrderIntegration",
        #     handler=process_order_fn
        # )

        # # 3. Create the Route and attach the integration
        # self.http_api.add_routes(
        #     path="/orders",
        #     methods=[apigwv2.HttpMethod.POST],
        #     integration=process_order_integration
        # )
        
        # # 4. Output the URL
        # cdk.CfnOutput(
        #     self, 
        #     "HttpApiEndpointUrl", 
        #     value=self.http_api.url,
        #     description="The URL of the HTTP API Gateway"
        # )


        # Override the AWS Console 'Name' tag for the private subnets
        private_subnets = self.vpc.select_subnets(subnet_group_name="private").subnets
        for i, subnet in enumerate(private_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/privateSubnet{i}")

        public_subnets = self.vpc.select_subnets(subnet_group_name="public").subnets
        for i, subnet in enumerate(public_subnets, start=1):
            cdk.Tags.of(subnet).add("Name", f"/publicSubnet{i}")
