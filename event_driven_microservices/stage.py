import aws_cdk as cdk
from constructs import Construct
from event_driven_microservices.network import Network
from event_driven_microservices.messaging import Messaging
from event_driven_microservices.database import Database

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
            sqs_queue = Messagings.sqs_queue,
            sns_topic_arn = Messagings.sns_topic.topic_arn,
            dynamodb_table_name = Db.table.table_name,
            config = config,
        )