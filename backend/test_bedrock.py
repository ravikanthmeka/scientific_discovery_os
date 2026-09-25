import boto3
import os
from dotenv import load_dotenv

load_dotenv('.env')

client = boto3.client('bedrock-runtime', 
                      region_name=os.getenv('AWS_REGION', 'us-east-1'), 
                      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

# Test cross-region inference profile
try:
    response = client.invoke_model(
        modelId='us.anthropic.claude-haiku-4-5-20251001-v1:0', 
        body='{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
    )
    print("SUCCESS with us.anthropic.claude-haiku-4-5-20251001-v1:0")
except Exception as e:
    print(f"FAILED with us.anthropic.claude-haiku-4-5-20251001-v1:0: {e}")

# Test old version if that fails
try:
    response = client.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0', 
        body='{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
    )
    print("SUCCESS with anthropic.claude-3-haiku-20240307-v1:0")
except Exception as e:
    print(f"FAILED with anthropic.claude-3-haiku-20240307-v1:0: {e}")
