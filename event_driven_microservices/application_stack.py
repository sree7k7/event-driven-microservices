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
import aws_cdk.aws_ecr as ecr
import os
import aws_cdk.aws_certificatemanager as acm
import aws_cdk.aws_wafv2 as wafv2
import aws_cdk.aws_iam as iam
import aws_cdk.aws_dynamodb as dynamodb

## compute stack is where we define our compute resources, in this case, our lambda functions. We also define the event source for the GenerateReceiptWorker Lambda, which is the SQS Queue created in the Messaging stack. The ProcessOrderWorker Lambda is triggered by API Gateway, which we'll set up in a later step.
class application_stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, sqs_queue, event_bus, dynamodb_table, vpc, rds_sg, valkey_sg, db_secret, valkey_cluster, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        domain_name = config['application']['domain_name'] # <-- REPLACE THIS with your own domain name that you have in Route 53. This is needed for the ACM certificate and CloudFront distribution.
        website_sub_domain = f"{config['application']['subdomain']}.{domain_name}" # e.g. coffeeshop.srikanth.help

        # ===========================================
        # Route 53 Private Hosted Zone for internal service discovery and communication within the VPC
        # ===========================================
        ## import the existing hosted zone
        hosted_zone = route53.HostedZone.from_lookup(
            self,
            "HostedZone",
            domain_name=config['application']['domain_name']
        )

        ## ACM certificate for the custom domain name
        new_certificate = acm.Certificate(
            self, "Certificate",
            domain_name=website_sub_domain,
            validation=acm.CertificateValidation.from_dns(hosted_zone)
        )

        ## This configuration ensures that logs are structured in JSON format, making it easier to query and
        process_order_fn_logs = logs.LogGroup(
            self,
            "ProcessOrderWorkerLogs",
            log_group_name="/aws/lambda/ProcessOrderWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=config['application']['log_retention_days'],
        )

        ## logging configuration for structured logging for the GenerateReceiptWorker Lambda
        generate_receipt_fn_logs = logs.LogGroup(
            self,
            "GenerateReceiptWorkerLogs",
            log_group_name="/aws/lambda/GenerateReceiptWorker",
            removal_policy=RemovalPolicy.DESTROY,
            retention=config['application']['log_retention_days'],
        )

        ## lambda funtion ProcessOrderWorker
        ##This function acts as the entry point. It handles the API Gateway request, writes to DynamoDB, and broadcasts the event to the Event Bus (EventBridge) for other services to consume. It also has structured logging and X-Ray tracing enabled for better observability. The environment variables include the DynamoDB table name and the Event Bus name, which it needs to interact with those services.
        self.process_order_fn = lambdaFn.Function(
            self,
            "ProcessOrderWorker",
            function_name="ProcessOrderWorker",
            runtime=lambdaFn.Runtime.PYTHON_3_14,
            handler="ProcessOrderWorker.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            timeout=cdk.Duration.seconds(config['application']['lambda_timeout']),
            memory_size=config['application']['lambda_memory'],
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=process_order_fn_logs, # Use the defined log group for structured logging
            tracing=lambdaFn.Tracing.ACTIVE, # Enable X-Ray tracing for better observability
            environment={
                'TABLE_NAME': dynamodb_table.table_name,
                'EVENT_BUS_NAME': event_bus.event_bus_name,
            },
        )

        ## grant the lambda function for xray permissions to write to x-ray. AWSXRayDaemonWriteAccess is an AWS managed policy that includes the necessary permissions for Lambda functions to send trace data to X-Ray, including PutTraceSegments and PutTelemetryRecords. By attaching this managed policy to the Lambda function's execution role, we ensure that it has the required permissions to interact with X-Ray without needing to manually specify each permission.
        dynamodb_table.grant_read_write_data(self.process_order_fn)
        event_bus.grant_put_events_to(self.process_order_fn)
        # self.process_order_fn.role.add_managed_policy(
        #     iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        # )

        ## lambda function ReceiptGenerator
        ## The ProcessOrderWorker Lambda shouts to the Event Bus, which drops the message into the SQS Queue, which wakes up the ReceiptGenerator Lambda
        self.generate_receipt_fn = lambdaFn.Function(
            self,
            "ReceiptGenerator",
            function_name="ReceiptGenerator",
            runtime=lambdaFn.Runtime.PYTHON_3_14,
            handler="ReceiptGenerator.lambda_handler",
            code=lambdaFn.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="private"),
            timeout=cdk.Duration.seconds(config['application']['lambda_timeout']),
            memory_size=config['application']['lambda_memory'],
            events=[
                lambdaFn_events.SqsEventSource(sqs_queue)
            ],
            logging_format=lambdaFn.LoggingFormat.JSON, # Structured logging
            system_log_level_v2=lambdaFn.SystemLogLevel.INFO, # Control Lambda system logs
            application_log_level_v2=lambdaFn.ApplicationLogLevel.INFO, # Control application logs
            log_group=generate_receipt_fn_logs, # Use the defined log group for structured logging
            tracing=lambdaFn.Tracing.ACTIVE, # Enable X-Ray tracing for better observability
            environment={
                'AWS_XRAY_TRACING_NAME': 'ReceiptGenerator'
            }
        )

        ## Grant the necessary permissions
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
            api_name=config['application']['apigw_name'],
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

        ## ALB security group to allow inbound traffic on port 80 from anywhere (you will need to add the actual ingress rules later)
        alb_sg = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            security_group_name=config['application']['alb_security_group_name'],
            vpc=vpc,
            description="Allow inbound traffic to ALB",
            allow_all_outbound=True
        )
        alb_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(80))

        # ==========================================
        # ECS (The Workhorse for Heavy Lifting) cluster and task definition
        # ==========================================
        
        ## create ecs security group for the cluster and allow inbound traffic on port 8080 from the ALB security group (you will need to add the actual ingress rules later)
        ecs_sg = ec2.SecurityGroup(
            self,
            "EcsSecurityGroup",
            security_group_name=config['application']['ecs_service_security_group_name'],
            vpc=vpc,
            description="Allow traffic from ALB to ECS tasks"
        )
        ecs_sg.connections.allow_from(alb_sg, ec2.Port.tcp(8080))


        self.ecs_cluster = ecs.Cluster(
            self,
            "EcsCluster",
            vpc=vpc,
            cluster_name=config['application']['ecs_cluster_name'],
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
            memory_limit_mib=config['application']['ecs_task_memory'],
            cpu=config['application']['ecs_task_cpu'],
            family=config['application']['ecs_task_definition_family'],
        )
        
        # 1. Give the ECS Task permission to write traces to X-Ray
        self.ecs_task_definition.task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        )

        # Grab the tag from the environment (Pipeline will inject this)
        # If it's not there, default to "latest" for local testing
        image_tag = os.environ.get("IMAGE_TAG", "latest")

        repo = ecr.Repository.from_repository_name(
            self, 
            "CoffeeShopRepo", 
            repository_name=config['application']['ecr_repository_name']
        )

        ## add a container to the task definition with the image from the public ECR repository and a container port of 8080
        container = self.ecs_task_definition.add_container(
            "AppContainer",
            image=ecs.ContainerImage.from_ecr_repository(repo, "latest"),
            port_mappings=[ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP)],
            logging =ecs.LogDrivers.aws_logs(
                stream_prefix="CoffeeShopApp",
                log_group=logs.LogGroup(
                    self,
                    "CoffeeShopAppLogs",
                    log_group_name="/aws/ecs/Task/CoffeeShopApp",
                    removal_policy=RemovalPolicy.DESTROY,
                    retention=logs.RetentionDays.ONE_WEEK,
                ),
            ),
            # NEW: Give FastAPI the Valkey URL!
            environment={
                "VALKEY_HOST": valkey_cluster.attr_primary_end_point_address,
                "VALKEY_PORT": valkey_cluster.attr_primary_end_point_port,
            },
            # Inject the secret fields as environment variables
            secrets={
                "DB_HOST": ecs.Secret.from_secrets_manager(db_secret, field="host"),
                "DB_PORT": ecs.Secret.from_secrets_manager(db_secret, field="port"),
                "DB_USERNAME": ecs.Secret.from_secrets_manager(db_secret, field="username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, field="password"),
            }
        )

        ## Lookup for newly created private X-Ray repo
        xray_repo = ecr.Repository.from_repository_name(
            self,
            "XRayRepo",
            repository_name=config['application']['X-ray-tracing_repo']
        )

        # Add the X-Ray Daemon Sidecar Container using your PRIVATE repo
        self.ecs_task_definition.add_container(
            "XRayDaemonContainer",
            image=ecs.ContainerImage.from_ecr_repository(xray_repo, "latest"),
            container_name="XRayDaemonContainer",
            cpu=32, 
            memory_limit_mib=256,
            port_mappings=[ecs.PortMapping(container_port=2000, protocol=ecs.Protocol.UDP)],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="XRayDaemon",
                log_group=logs.LogGroup(
                    self,
                    "XRayDaemonLogs",
                    log_group_name="/aws/xray/daemon",
                    removal_policy=RemovalPolicy.DESTROY,
                    retention=config['application']['log_retention_days'],
                ),
            ),
            # environment={
            #     "AWS_EC2_METADATA_DISABLED": "true"
            # }
        )

        ## add dependency so that the X-Ray container starts before the app container to ensure that the daemon is ready to receive traces when the app starts sending them
        container.add_container_dependencies(
            ecs.ContainerDependency(
                container=self.ecs_task_definition.find_container("XRayDaemonContainer"),
                condition=ecs.ContainerDependencyCondition.START
            )
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
            security_groups=[ecs_sg],
            ## Enable service discovery here
            cloud_map_options=ecs.CloudMapOptions(
                name="api"
            ),
            enable_execute_command=True # Allows us to run commands directly inside the container
        )

        ## ==========================================
        # Application Load Balancer (ALB) for routing traffic to the ECS service
        # ==========================================

        self.alb = elbv2.ApplicationLoadBalancer(
            self, "ALB", 
            vpc=vpc, 
            internet_facing=True,
            load_balancer_name=config['application']['alb_name'],
            security_group=alb_sg
        )
        ## Add a listener to the ALB on port 80 and forward traffic to the ECS service, 
        # and use HTTPS protocol for the listener to encrypt traffic between the client and the load balancer.
        # 1. Listen on Port 80 (HTTP)
        listener = self.alb.add_listener("httpListener", port=80)

        # 2. Forward that traffic to the FastAPI Container on Port 8080
        listener.add_targets(
            "ecstarget", 
            port=8080, 
            targets=[
                self.ecs_service.load_balancer_target(
                    container_name="AppContainer", 
                    container_port=8080
                )],
            health_check=elbv2.HealthCheck(
                path="/health", # Your FastAPI health route
                interval=cdk.Duration.seconds(15), # Fast checks for development
                timeout=cdk.Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2
            )   
        )

        # ========================
        ## AWS WAF for DDoS protection and web application security in front of the CloudFront distribution
        # ========================

        self.web_acl = wafv2.CfnWebACL(
            self, "WebAcl",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(
                allow=wafv2.CfnWebACL.AllowActionProperty()
            ),
            scope="CLOUDFRONT",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="CoffeeShopWebAcl",
                sampled_requests_enabled=True
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWS-AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(
                        none={}
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            name="AWSManagedRulesCommonRuleSet",
                            vendor_name="AWS"
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWS-AWSManagedRulesCommonRuleSet",
                        sampled_requests_enabled=True
                    )
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=2,
                    action=wafv2.CfnWebACL.RuleActionProperty(
                        block=wafv2.CfnWebACL.BlockActionProperty() # Block them if they exceed the limit
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=100, # Max requests per 5 minutes per IP
                            aggregate_key_type="IP"
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimitRule",
                        sampled_requests_enabled=True
                    )
                )

            ]
        )


        # ==========================================
        # cloudfront dristribution in front of the ALB for global content delivery and DDoS protection
        # CDN route traffic based on the url paths i,e APIgw or alb
        # ==========================================

        self.cloudfront_distribution = cloudfront.Distribution(
            self, "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    self.alb,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    http_port=80, # Specify the port if your ALB is listening on a non-standard port
                    
                    ),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            price_class=cloudfront.PriceClass.PRICE_CLASS_100, # Use the lowest price class for cost optimization in this demo
            domain_names=[website_sub_domain],
            certificate=new_certificate,
        ## apigw distribution for API Gateway with path pattern matching for /orders path to route to the API Gateway and all other paths to route to the ALB
            additional_behaviors = {
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(f"{self.http_api.api_id}.execute-api.{self.region}.{self.url_suffix}"),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED, # Disable caching for API Gateway routes to ensure clients always get fresh data
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER, # Forward all headers except the Host header to API Gateway for proper routing
                )
            },
            web_acl_id=self.web_acl.attr_arn
        )

        ## Route 53 record to point the custom domain to the CloudFront distribution
        route53.ARecord(
            self, "AliasRecord",
            zone=hosted_zone,
            record_name=website_sub_domain,
            target=route53.RecordTarget.from_alias(route53_targets.CloudFrontTarget(self.cloudfront_distribution))
        )

                ## Add the ingress rule for the ecs tasks to access the RDS database on port 5432
        ec2.CfnSecurityGroupIngress(
            self,
            "EcsToRdsIngress",
            group_id=rds_sg.security_group_id,
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            source_security_group_id=self.ecs_service.connections.security_groups[0].security_group_id
        )

        ## Add the ingress rule for the ecs tasks to access the Valkey cache on port 6379
        ec2.CfnSecurityGroupIngress(
            self,
            "EcsToValkeyIngress",
            group_id=valkey_sg.security_group_id,
            ip_protocol="tcp",
            from_port=6379,
            to_port=6379,
            source_security_group_id=self.ecs_service.connections.security_groups[0].security_group_id
        )

        # Output the URL
        cdk.CfnOutput(
            self, 
            "HttpApiEndpointUrl", 
            value=self.http_api.url,
            description="The URL of the HTTP API Gateway"
        )
    
