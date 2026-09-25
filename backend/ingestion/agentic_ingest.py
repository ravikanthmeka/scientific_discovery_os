import os
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_aws import ChatBedrock
from dotenv import load_dotenv

load_dotenv()

# We initialize our Bedrock Claude Haiku client
llm = ChatBedrock(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    max_tokens=4096,
    temperature=0.1,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    max_retries=15
)

# --- Pydantic Models for Structured Output ---

class ParsedLatex(BaseModel):
    clean_text: str = Field(description="The cleaned Markdown text stripped of ugly LaTeX formatting macros.")
    equations: List[str] = Field(description="A list of the core mathematical equations found in the chunk.")

class ScientificEntity(BaseModel):
    name: str = Field(description="The normalized name of the entity.")
    type: str = Field(description="Type of entity (e.g., Material, Algorithm, Physical Property, Particle).")
    
class ExtractedEntities(BaseModel):
    entities: List[ScientificEntity]

class ScientificClaim(BaseModel):
    subject: str = Field(description="The entity or concept the claim is about.")
    predicate: str = Field(description="The relationship (e.g., EXHIBITS, OUTPERFORMS, DECREASES).")
    object: str = Field(description="The target entity, property, or value.")
    evidence_level: str = Field(description="Confidence level based on text (e.g., PROVEN, HYPOTHESIZED, CONTRADICTED).")

class ExtractedClaims(BaseModel):
    claims: List[ScientificClaim]

# --- Agents ---

def agent_parse_latex(raw_tex: str) -> ParsedLatex:
    """Agent 1: Parses raw LaTeX into clean markdown and extracts key equations."""
    structured_llm = llm.with_structured_output(ParsedLatex)
    prompt = f"Extract and clean the following LaTeX chunk. Return clean markdown and isolated equations:\n\n{raw_tex}"
    return structured_llm.invoke(prompt)

def agent_extract_entities(clean_text: str) -> ExtractedEntities:
    """Agent 2: Identifies scientific entities."""
    structured_llm = llm.with_structured_output(ExtractedEntities)
    prompt = f"Identify all specific scientific entities in this text (materials, algorithms, etc.):\n\n{clean_text}"
    return structured_llm.invoke(prompt)

def agent_extract_claims(clean_text: str) -> ExtractedClaims:
    """Agent 3 & 5: Extracts relational claims and assigns evidence levels."""
    structured_llm = llm.with_structured_output(ExtractedClaims)
    prompt = f"Extract all explicit scientific assertions or claims from this text. Identify Subject, Predicate, Object, and Evidence Level:\n\n{clean_text}"
    return structured_llm.invoke(prompt)

# Agent 4 (Linking) is inherently handled by how we insert these structured outputs into Neo4j using MERGE statements.
