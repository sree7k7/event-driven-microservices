import random
import this
import constructs
import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
import aws_cdk.aws_rds as rds
import aws_cdk.aws_lambda as lambdaFn
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_elasticache as elasticache
from aws_cdk import aws_iam as iam


class Database(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## For simplicity, we're using DynamoDB as our database. In a real-world application, you might use RDS or another database service.
        self.table = dynamodb.TableV2(
            self,
            "OrdersTable",
            table_name="CoffeeOrders",
            billing=dynamodb.Billing.on_demand(),
            partition_key=dynamodb.Attribute(name="sessionId", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY, # NOT recommended for production, use with caution
            point_in_time_recovery=False,
            deletion_protection=False, # NOT recommended for production, use with caution
        )

        # ==========================================
        # Amazon RDS (PostgreSQL)
        # ==========================================

        # Create a dedicated Security Group for RDS and allow access from ECS tasks (you will need to add the actual ingress rules later)

        self.rds_sg = ec2.SecurityGroup(
            self,
            "RDSSecurityGroup",
            vpc=vpc,
            description="Allow access to RDS Database",
            allow_all_outbound=True
        )

        self.db_instance = rds.DatabaseInstance(
            self,
            "ReceiptsDB",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_17_6
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            allocated_storage=20, # Good practice to explicitly define storage for micro instances
            security_groups=[self.rds_sg],
            removal_policy=cdk.RemovalPolicy.DESTROY, 
            deletion_protection=False, 
            # Use the modern CDK method to auto-generate the secret
            credentials=rds.Credentials.from_username("postgres"), 
        )

        ## permission for rds to access x-ray (so we can see database performance in our X-Ray traces!) AWSXRayDaemonWriteAccess
        self.rds_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.udp(2000),
            description="Allow RDS to access X-Ray"
        )


        # ==========================================
        # ElastiCache (Valkey)
        # ==========================================
        
        # 1. Create a dedicated Security Group for Valkey
        self.valkey_sg = ec2.SecurityGroup(
            self,
            "ValkeySecurityGroup",
            vpc=vpc,
            description="Allow access to Valkey Cache",
            allow_all_outbound=True
        )

        # 2. Fix the Subnet Group to use isolated_subnets instead of private_subnets
        cache_subnet_group = elasticache.CfnSubnetGroup(
            self,
            "CacheSubnetGroup",
            description="Subnet group for Elasticache Valkey",
            subnet_ids=[subnet.subnet_id for subnet in vpc.isolated_subnets]
        )

        # 3. Create the Cache Cluster (using Replication Group for Valkey)
        self.cache_cluster = elasticache.CfnReplicationGroup(
            self,
            "ValkeyReplicationGroup", # Changed logical ID to force a clean replacement
            replication_group_description="Valkey Cache Cluster",
            cache_node_type="cache.t3.micro",
            engine="valkey",
            num_cache_clusters=2,
            security_group_ids=[self.valkey_sg.security_group_id], # Attach the dedicated SG
            cache_subnet_group_name=cache_subnet_group.ref,
            transit_encryption_enabled=True, # Enable in-transit encryption for better security
        )

        ## permission for valkey to access x-ray (so we can see cache performance in our X-Ray traces!) AWSXRayDaemonWriteAccess 
        self.valkey_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.udp(2000),
            description="Allow Valkey to access X-Ray"
        )