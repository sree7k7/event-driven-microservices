import aws_cdk as cdk
from aws_cdk import (
    Stack,
)
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class EventDrivenMicroservicesStack(Stack):
    """
    This stack was previously used to define an AWS CodePipeline.
    Since moving to GitHub Actions for CI/CD, the application stacks
    are now instantiated directly in `app.py` via the `Stage` construct.

    This stack is now effectively a placeholder and can be removed
    if it's no longer referenced in `app.py`.
    """
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The Stage and configuration have been moved to app.py
        pass