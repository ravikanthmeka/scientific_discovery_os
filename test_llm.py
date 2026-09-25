import asyncio
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
import os

llm = ChatBedrock(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    max_tokens=100
)

res = llm.invoke([HumanMessage(content="Hello!")])
print("RESPONSE METADATA:")
print(res.response_metadata)
print("\nUSAGE METADATA:")
if hasattr(res, "usage_metadata"):
    print(res.usage_metadata)
