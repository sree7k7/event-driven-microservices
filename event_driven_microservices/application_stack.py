import aws_cdk as cdk
from aws_cdk import RemovalPolicy, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from aws_cdk import aws_logs as logs
import aws_cdk.aws_lambda as lambdaFn
import aws_cdk.aws_lambda_event_sources as lambdaFn_events
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_integrations as integrations
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_elasticloadbalancingv2 as elbv2
import aws_cdk.aws_servicediscovery as servicediscovery
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_route53 as route53
import aws_cdk.aws_route53_targets as route53_targets
import aws_cdk.aws_certificatemanager as acm

## compute stack is where we define our compute resources, in this case, our lambda functions. We also define the event source for the GenerateReceiptWorker Lambda, which is the SQS Queue created in the Messaging stack. The ProcessOrderWorker Lambda is triggered by API Gateway, which we'll set up in a later step.
class application_stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, sqs_queue, sns_topic, dynamodb_table, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        domain_name = "srikanth.help" # <-- REPLACE THIS with your own domain name that you have in Route 53. This is needed for the ACM certificate and CloudFront distribution.
        website_sub_domain = f"microservices.{domain_name}" # e.g. microservices.srikanth.help
        ## This configuration ensures that logs are structured in JSON format, making it easier to query and
        process_order_fn_logs = logs.LogGroup(
            self,
            "ProcessOrderWorkerLogs",
            log_group_name="/aws/lambda/ProcessOrderWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        ## logging configuration for structured logging for the GenerateReceiptWorker Lambda
        generate_receipt_fn_logs = logs.LogGroup(
            self,
            "GenerateReceiptWorkerLogs",
            log_group_name="/aws/lambda/GenerateReceiptWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        ## lambda funtion ProcessOrderWorker
        ##This function acts as the entry point. It handles the API Gateway request, writes to DynamoDB, and broadcasts the event to SNS.
        self.process_order_fn = lambdaFn.Function(
            self,
            "ProcessOrderWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="ProcessOrderWorker.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            # vpc=vpc,
            # vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            timeout=cdk.Duration.seconds(10),
            environment={
                'TABLE_NAME': dynamodb_table.table_name,
                'TOPIC_ARN': sns_topic.topic_arn
            },
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=process_order_fn_logs, # Use the defined log group for structured logging
        )

        ## lambda function ReceiptGenerator
        ## The ProcessOrderWorker Lambda shouts to the SNS Topic, which drops the message into the SQS Queue, which wakes up the ReceiptGenerator Lambda
        self.generate_receipt_fn = lambdaFn.Function(
            self,
            "ReceiptGenerator",
            runtime=lambdaFn.Runtime.PYTHON_3_12,
            handler="ReceiptGenerator.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            timeout=cdk.Duration.seconds(10),
            events=[
                lambdaFn_events.SqsEventSource(sqs_queue)
            ],
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=generate_receipt_fn_logs, # Use the defined log group for structured logging
        )

        ## Grant the necessary permissions
        dynamodb_table.grant_read_write_data(self.process_order_fn)
        sns_topic.grant_publish(self.process_order_fn)
        sqs_queue.grant_send_messages(self.generate_receipt_fn)
        sqs_queue.grant_consume_messages(self.generate_receipt_fn)

        # ==========================================
        # API GATEWAY (The VIP Host - HTTP API v2)
        # ==========================================

# Create the HTTP API Gateway, which will serve as the front door for our application, 
# handling incoming HTTP requests and routing them to the appropriate backend services. 
# We use HTTP API v2 for its improved performance and lower cost compared to REST API, 
# making it ideal for our event-driven architecture.
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

        # 2. Define the Integration (using the lambda created directly above)
        process_order_integration = integrations.HttpLambdaIntegration(
            "ProcessOrderIntegration",
            handler=self.process_order_fn
        )

        # 3. Create the Route and attach the integration
        self.http_api.add_routes(
            path="/api/orders",
            methods=[apigwv2.HttpMethod.POST],
            integration=process_order_integration
        )

        # ==========================================
        # ECS (The Workhorse for Heavy Lifting) cluster and task definition
        # ==========================================

        self.ecs_cluster = ecs.Cluster(
            self,
            "EcsCluster",
            vpc=vpc,
            cluster_name="CoffeeShopEcsCluster",
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name="coffeeshop.internal",
                type=servicediscovery.NamespaceType.DNS_PRIVATE, # Use private DNS for service discovery within the VPC
            )
        )

        ## create ecs taskdefinition with fargate compatibility and 512mb of memory and 256 cpu units and 
        # service discovery enabled for the task
        self.ecs_task_definition = ecs.FargateTaskDefinition(
            self,
            "EcsTaskDefinition",
            memory_limit_mib=512,
            cpu=256,
            family="CoffeeShopTaskDefinition",
        )

        ## add a container to the task definition with the image from the public ECR repository and a container port of 80
        container = self.ecs_task_definition.add_container(
            "AppContainer",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            port_mappings=[ecs.PortMapping(container_port=80, protocol=ecs.Protocol.TCP)],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="CoffeeShopApp")
        )


        ## ecs service that runs the task definition in the cluster with a desired count of 1 and assigns a public IP to the task
        self.ecs_service = ecs.FargateService(
            self, 
            "Service", 
            cluster=self.ecs_cluster, 
            task_definition=self.ecs_task_definition, 
            min_healthy_percent=100,
            desired_count=1,
            assign_public_ip=False, # We want to keep our tasks private and only accessible through the load balancer, so we set this to False
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"), # We want our ECS tasks to run in the private subnets for better security, so we specify the subnet group name here
            ## Enable service discovery here
            cloud_map_options=ecs.CloudMapOptions(
                name="api"
            )
        )

        # Create the Public Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self, "ALB", 
            vpc=vpc, 
            internet_facing=True,
            load_balancer_name="CoffeeShopALB"
        )
        ## Add a listener to the ALB on port 80 and forward traffic to the ECS service, 
        # and use HTTPS protocol for the listener to encrypt traffic between the client and the load balancer.
        listener = self.alb.add_listener("publicListener", port=80)

        ## Attach ecs service to the ALB Target Group with health check configuration
        listener.add_targets(
            "EcsTarget", 
            port=80, 
            targets=[
                self.ecs_service.load_balancer_target(
                    container_name="AppContainer", 
                    container_port=80
                )],
            health_check=elbv2.HealthCheck(
                path="/",
                interval=cdk.Duration.seconds(60),
                timeout=cdk.Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2
            )   
        )

        # ===========================================
        # Route 53 Private Hosted Zone for internal service discovery and communication within the VPC
        # ===========================================
        ## import the existing hosted zone
        hosted_zone = route53.HostedZone.from_lookup(
            self,
            "HostedZone",
            domain_name="srikanth.help"
        )

        ## ACM certificate for the custom domain name
        new_certificate = acm.DnsValidatedCertificate(
            self, "Certificate",
            domain_name=website_sub_domain,
            hosted_zone=hosted_zone,
            region="us-east-1",
        )

        # ==========================================
        # cloudfront dristribution in front of the ALB for global content delivery and DDoS protection
        # CDN route traffic based on the url paths i,e APIgw or alb
        # ==========================================

        self.cloudfront_distribution = cloudfront.Distribution(
            self, "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(self.alb),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="/*",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100, # Use the lowest price class for cost optimization in this demo
            domain_names=[website_sub_domain],
            certificate=new_certificate,
        ## apigw distribution for API Gateway with path pattern matching for /orders path to route to the API Gateway and all other paths to route to the ALB
            additional_behaviors = {
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(f"{self.http_api.api_id}.execute-api.{self.region}.{self.url_suffix}"),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED, # Disable caching for API Gateway routes to ensure clients always get fresh data
                )
            }
        )


            
        # Output the URL
        cdk.CfnOutput(
            self, 
            "HttpApiEndpointUrl", 
            value=self.http_api.url,
            description="The URL of the HTTP API Gateway"
        )
    