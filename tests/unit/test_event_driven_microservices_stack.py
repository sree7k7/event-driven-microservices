# import aws_cdk as core
# import aws_cdk.assertions as assertions

# from event_driven_microservices.event_driven_microservices_stack import EventDrivenMicroservicesStack

# # example tests. To run these tests, uncomment this file along with the example
# # resource in event_driven_microservices/event_driven_microservices_stack.py
# def test_sqs_queue_created():
#     app = core.App()
#     stack = EventDrivenMicroservicesStack(app, "event-driven-microservices")
#     template = assertions.Template.from_stack(stack)

# #     template.has_resource_properties("AWS::SQS::Queue", {
# #         "VisibilityTimeout": 300
# #     })
