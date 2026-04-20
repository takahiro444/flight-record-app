#!/usr/bin/env python3
"""
Update AgentCore Runtime container image.

Required environment variables:
  AGENTCORE_RUNTIME_ARN - ARN of the AgentCore Runtime to update
  ECR_IMAGE_URI         - Full ECR image URI for the new container image
  AWS_REGION            - optional, defaults to us-west-2
"""

import boto3
import json
import os
import sys

RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")
NEW_IMAGE = os.environ.get("ECR_IMAGE_URI")
REGION = os.environ.get("AWS_REGION", "us-west-2")

if not RUNTIME_ARN or not NEW_IMAGE:
    print("ERROR: AGENTCORE_RUNTIME_ARN and ECR_IMAGE_URI environment variables are required", file=sys.stderr)
    sys.exit(2)

def update_runtime_image():
    """Update the AgentCore Runtime to use new container image."""
    
    # Try bedrock-agent-runtime client
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        print(f"Using bedrock-agent-runtime client")
        print(f"Available operations: {client._service_model.operation_names}")
    except Exception as e:
        print(f"bedrock-agent-runtime error: {e}")
    
    # Try bedrock-agent client
    try:
        client = boto3.client('bedrock-agent', region_name=REGION)
        print(f"\nUsing bedrock-agent client")
        print(f"Available operations: {client._service_model.operation_names}")
    except Exception as e:
        print(f"bedrock-agent error: {e}")
    
    # Try bedrock client
    try:
        client = boto3.client('bedrock', region_name=REGION)
        print(f"\nUsing bedrock client")
        print(f"Available operations: {client._service_model.operation_names}")
    except Exception as e:
        print(f"bedrock error: {e}")

if __name__ == "__main__":
    update_runtime_image()
