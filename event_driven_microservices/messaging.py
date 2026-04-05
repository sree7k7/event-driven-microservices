import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy
from constructs import Construct

import aws_cdk.aws_sqs as sqs
import aws_cdk.aws_events as events
import aws_cdk.aws_logs as logs
import aws_cdk.aws_events_targets as targets


class Messaging(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## Create an aws eventbridge topic to receive json payload from lambda functions
        self.events = events.EventBus(
            self,
            "ReceiptEventBus", 
            event_bus_name=config['messaging']['event_bus_name'],
        )

        ## the Quarantine Queue (DLQ)
        self.dlq = sqs.Queue(self, "ReceiptDLQ")
        
        ## sqs queue
        self.sqs_queue = sqs.Queue(
            self,
            "ReceiptQueue",
            queue_name="ReceiptQueue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
            dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=3, # Quarantines the message after 3 failed attempts
                    queue=self.dlq
                )
        )

        # ==========================================
        # EventBridge Rules & Targets
        # ==========================================
        
        # 1. Route 'OrderPlaced' events to the SQS Queue
        events.Rule(
            self,
            "RouteOrdersToReceiptQueue",
            event_bus=self.events,
            event_pattern=events.EventPattern(
                source=["com.coffeeshop.orders"],
                detail_type=["OrderPlaced"]
            ),
            targets=[targets.SqsQueue(self.sqs_queue)]
        )

        # 2. Setup logging for the EventBus via a Target Rule
        bus_log_group = logs.LogGroup(
            self,
            "ReceiptEventBusLogs",
            log_group_name="/aws/events/ReceiptEventBus",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )
        
        events.Rule(
            self,
            "LogAllOrdersEvents",
            event_bus=self.events,
            event_pattern=events.EventPattern(
                source=["com.coffeeshop.orders"]
            ),
            targets=[targets.CloudWatchLogGroup(bus_log_group)]
        )