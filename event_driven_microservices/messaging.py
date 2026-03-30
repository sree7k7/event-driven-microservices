import random
import this
import aws_cdk
import constructs
import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
from constructs import Construct

import aws_cdk.aws_sqs as sqs
import aws_cdk.aws_sns as sns
import aws_cdk.aws_sns_subscriptions as subscriptions


class Messaging(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## sns topic
        self.sns_topic = sns.Topic(
            self,
            "OrderTopic"
        )
        ## the Quarantine Queue (DLQ)
        self.dlq = sqs.Queue(self, "ReceiptDLQ")
        
        ## sqs queue
        self.sqs_queue = sqs.Queue(
            self,
            "ReceiptQueue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
            dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=3, # Quarantines the message after 3 failed attempts
                    queue=self.dlq
                )
        )
        
        ## sns subscription 
        self.sns_subscription = sns.Subscription(
            self,
            "OrderSubscription",
            topic=self.sns_topic,
            protocol=sns.SubscriptionProtocol.SQS,
            endpoint=self.sqs_queue.queue_arn
        )
        self.sns_topic.add_subscription(subscriptions.SqsSubscription(self.sqs_queue))
