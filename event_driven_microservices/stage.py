import aws_cdk as cdk
from constructs import Construct
from event_driven_microservices.network import Network


class Stage(cdk.Stage):
    def __init__(self, scope: Construct, construct_id: str, config: object, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        network = Network(
            self,
            'Network',
            config = config,
        )