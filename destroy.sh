#!/bin/sh

# --- AWS CloudFormation Stack Deletion Script ---
#
# This script deletes a predefined list of AWS CloudFormation stacks.
# It waits for each deletion to complete before proceeding to the next.
#
# Prerequisites:
# - AWS CLI must be installed and configured with valid credentials.
#   (e.g., run `aws configure` or ensure your environment variables are set)

# Define the list of stack names to be deleted
STACKS_TO_DELETE="microservices-stage-Database microservices-stage-Messaging microservices-stage-Application microservices-stage-Network"

echo "Initiating deletion of specified CloudFormation stacks..."
echo "======================================================="

# Loop through the string and delete each stack sequentially
for stack in $STACKS_TO_DELETE; do
    echo -n "Processing stack: $stack ... "

    # First, check if the stack actually exists to avoid errors
    if aws cloudformation describe-stacks --stack-name "$stack" > /dev/null 2>&1; then
        # If it exists, initiate the deletion
        aws cloudformation delete-stack --stack-name "$stack"
        echo "Deletion initiated. Waiting for completion..."

        # Wait for the stack deletion to complete successfully
        aws cloudformation wait stack-delete-complete --stack-name "$stack"
        echo "✅ Successfully deleted stack: $stack"
    else
        # If it doesn't exist, print a warning and skip
        echo "⚠️  Warning: Stack does not exist or was already deleted. Skipping."
    fi
    echo # Add a newline for cleaner output
done

echo "======================================================="
echo "Script finished. All specified stacks have been processed."
