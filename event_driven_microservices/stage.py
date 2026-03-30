import aws_cdk as cdk
from constructs import Construct
from event_driven_microservices.network import Network
from event_driven_microservices.messaging import Messaging
from event_driven_microservices.database import Database
from event_driven_microservices.application_stack import application_stack

class Stage(cdk.Stage):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        Messagings = Messaging(
            self,
            'Messaging',
            config = config,
        )

        Db = Database(
            self,
            'Database',
            config = config,
        )
        
        network = Network(
            self,
            'Network',
            config = config,
        )

        app_stack = application_stack(
            self,
            'Application',
            vpc = network.vpc,
            sqs_queue = Messagings.sqs_queue,
            sns_topic = Messagings.sns_topic,
            dynamodb_table = Db.table,
            config = config,
        )