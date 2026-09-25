import asyncio
from typing import List, Dict
import os
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage

load_dotenv()

# Mocking LangChain LLM execution for the local setup without requiring an API key immediately.
# In a real environment, this would use LangChain chains and LLMs.

import sys
import os
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool

load_dotenv()

# Global MCP Client Session
global_mcp_stdio_cm = None
global_mcp_read = None
global_mcp_write = None
global_mcp_session_cm = None
global_mcp_session = None

async def init_global_mcp():
    global global_mcp_stdio_cm, global_mcp_read, global_mcp_write, global_mcp_session_cm, global_mcp_session
    if global_mcp_session is not None:
        return
    
    mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[mcp_server_path],
        env=None
    )
    global_mcp_stdio_cm = stdio_client(server_params)
    global_mcp_read, global_mcp_write = await global_mcp_stdio_cm.__aenter__()
    
    global_mcp_session_cm = ClientSession(global_mcp_read, global_mcp_write)
    global_mcp_session = await global_mcp_session_cm.__aenter__()
    await global_mcp_session.initialize()

async def close_global_mcp():
    global global_mcp_stdio_cm, global_mcp_session_cm, global_mcp_session
    if global_mcp_session_cm:
        await global_mcp_session_cm.__aexit__(None, None, None)
    if global_mcp_stdio_cm:
        await global_mcp_stdio_cm.__aexit__(None, None, None)
    global_mcp_session = None

from database_models import QueryArtifact

class AgentManager:
    def __init__(self, websocket, db_session=None, query_id=None, user_id=None):
        self.websocket = websocket
        self.db_session = db_session
        self.query_id = query_id
        self.user_id = user_id
        
        # Initialize Bedrock LLM
        self.llm = ChatBedrock(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            max_retries=15,
            max_tokens=4096,
            temperature=0.1
        )

    async def _send_log(self, agent_id: str, status: str, log: str, artifact: str = "", agent_name: str = "", tokens: dict = None):
        message = {
            "agent_id": agent_id,
            "status": status,
            "log": log,
            "artifact": artifact,
            "agent_name": agent_name,
            "tokens": tokens
        }
        
        # Save artifact to database if it exists
        if status == "Completed" and artifact and self.db_session and self.query_id:
            try:
                new_art = QueryArtifact(
                    query_id=self.query_id,
                    agent_id=agent_id,
                    agent_name=agent_name or agent_id,
                    content=artifact
                )
                self.db_session.add(new_art)
                self.db_session.commit()
            except Exception as e:
                print(f"Failed to save artifact to DB: {e}")
                
        # Track Tokens and Enforce Limits
        if tokens and tokens.get('total_tokens') and self.db_session and self.query_id:
            try:
                import billing
                import database_models
                query_record = self.db_session.query(database_models.QueryHistory).filter_by(id=self.query_id).first()
                if query_record and query_record.user_id:
                    user = self.db_session.query(database_models.User).filter_by(id=query_record.user_id).first()
                    if user:
                        billing.report_usage(user, tokens['total_tokens'], self.db_session)
                        if user.subscription_tier == "FREE" and user.tokens_used > 1000:
                            error_msg = f"Token limit exceeded. You have used {user.tokens_used} tokens. Please upgrade to PRO to continue."
                            if self.websocket:
                                await self.websocket.send_json({
                                    "agent_id": "SYSTEM",
                                    "status": "Error",
                                    "log": error_msg,
                                    "artifact": ""
                                })
                            raise Exception(error_msg)
            except Exception as e:
                if "Token limit exceeded" in str(e):
                    raise e
                print(f"Failed to report usage for agent tokens: {e}")
                
        if self.websocket:
            await self.websocket.send_json(message)
            await asyncio.sleep(0.5)

    async def run_literature_intelligence(self, domain: str, query: str, llm_with_tools, tools_map, refinement_feedback: str = None):
        agent_id = "literature"
        await self._send_log(agent_id, "Processing", f"Initializing autonomous literature sweep for {domain} via MCP tools...")
        
        prompt = f"""Your task is to search for the most relevant scientific literature and concepts for the user's query: '{query}' in the domain: '{domain}'.
You have access to 'openalex_search_works'. You should use this to query the live OpenAlex scholarly catalog for the most recent and highly cited works related to this query.
Synthesize the retrieved information into a highly compressed literature review.

IMPORTANT: Output ONLY a strict, highly concise bulleted list of raw facts and keywords. Do NOT include conversational filler, intro, outro, inner monologue, or meta-commentary. Use sentence fragments. MAXIMUM 200 WORDS.
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease incorporate this feedback into your updated search strategy and synthesis."

        messages = [HumanMessage(content=prompt)]
        
        await self._send_log(agent_id, "Processing", "Agent is planning its search strategy...")
        ai_msg = self.llm.bind_tools(list(tools_map.values())).invoke(messages)
        
        # Handle autonomous tool calls with a while loop (up to 5 iterations)
        iterations = 0
        while hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls and iterations < 5:
            messages.append(ai_msg)
            for tool_call in ai_msg.tool_calls:
                await self._send_log(agent_id, "Processing", f"Agent dynamically invoking MCP Tool: {tool_call['name']} with args {tool_call['args']}")
                selected_tool = tools_map.get(tool_call["name"])
                if selected_tool:
                    try:
                        tool_output = await selected_tool.ainvoke(tool_call)
                        out_str = str(tool_output).strip()
                        if not out_str:
                            out_str = "No results found."
                        elif len(out_str) > 2000:
                            out_str = out_str[:2000] + "\n...[TRUNCATED FOR BREVITY]"
                        messages.append(ToolMessage(name=tool_call["name"], content=out_str, tool_call_id=tool_call["id"]))
                    except Exception as e:
                        messages.append(ToolMessage(name=tool_call["name"], content=f"Error: {str(e)}", tool_call_id=tool_call["id"]))
                else:
                    messages.append(ToolMessage(name=tool_call["name"], content=f"Tool not found: {tool_call['name']}", tool_call_id=tool_call["id"]))
            
            await self._send_log(agent_id, "Processing", f"Agent synthesizing retrieved data (Iteration {iterations + 1})...")
            ai_msg = self.llm.bind_tools(list(tools_map.values())).invoke(messages)
            iterations += 1

        if iterations == 0:
            await self._send_log(agent_id, "Processing", "Agent decided no tool calls were necessary.")
        
        artifact = f"Knowledge Base Summary:\n\n{ai_msg.content}"
        
        tokens = {}
        if hasattr(ai_msg, "usage_metadata") and ai_msg.usage_metadata:
            tokens = ai_msg.usage_metadata
        elif hasattr(ai_msg, "response_metadata"):
            # Fallback for AWS Bedrock response format
            metrics = ai_msg.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = ai_msg.response_metadata.get("usage", {})
                
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, tokens=tokens)
        
        # We also pass some claims explicitly to the next agent (simulating graph output)
        # To maintain the rest of the pipeline working, we can extract any graph claims if they were called
        return artifact, messages

    async def run_cross_domain_analogy(self, domain: str, query: str, lit_artifact: str, tools_map, refinement_feedback: str = None):
        agent_id = "cross_domain"
        agent_name = "Cross-Domain Innovator"
        await self._send_log(agent_id, "Processing", f"Searching for structural analogies in unrelated domains...", agent_name=agent_name)
        
        prompt = f"""You are the Cross-Domain Innovator Agent.
Your task is to take the following literature synthesis for the domain '{domain}' and find structural analogies in completely unrelated scientific domains.
Use your 'find_analogous_domains' tool to query the local graph database for domains that share scientific entities, methodologies, or structural patterns.
Crucially, you must also use the 'openalex_search_works' tool to query the live OpenAlex catalog to find cross-domain methodologies and papers that utilize similar techniques outside of the original domain.
Then, use 'openalex_search_works' and 'get_domain_methodologies' on those *other* domains to extract insights.
Synthesize how an approach from an analogous domain could solve the original query: '{query}'.

IMPORTANT: Output ONLY a strict, highly concise bulleted list of cross-domain mappings and insights. Do NOT include conversational filler, intro, outro, inner monologue, or meta-commentary. Use sentence fragments. MAXIMUM 200 WORDS.

Literature Synthesis:
{lit_artifact}
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nAdjust your cross-domain search based on this feedback."

        messages = [HumanMessage(content=prompt)]
        
        ai_msg = self.llm.bind_tools(list(tools_map.values())).invoke(messages)
        
        iterations = 0
        while hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls and iterations < 5:
            messages.append(ai_msg)
            for tool_call in ai_msg.tool_calls:
                await self._send_log(agent_id, "Processing", f"Agent dynamically invoking MCP Tool: {tool_call['name']} with args {tool_call['args']}", agent_name=agent_name)
                selected_tool = tools_map.get(tool_call["name"])
                if selected_tool:
                    try:
                        tool_output = await selected_tool.ainvoke(tool_call)
                        out_str = str(tool_output).strip()
                        if not out_str: 
                            out_str = "No results found."
                        elif len(out_str) > 2000:
                            out_str = out_str[:2000] + "\n...[TRUNCATED FOR BREVITY]"
                        messages.append(ToolMessage(name=tool_call["name"], content=out_str, tool_call_id=tool_call["id"]))
                    except Exception as e:
                        messages.append(ToolMessage(name=tool_call["name"], content=f"Error: {str(e)}", tool_call_id=tool_call["id"]))
                else:
                    messages.append(ToolMessage(name=tool_call["name"], content=f"Tool not found: {tool_call['name']}", tool_call_id=tool_call["id"]))
            
            await self._send_log(agent_id, "Processing", f"Agent synthesizing cross-domain findings (Iteration {iterations + 1})...", agent_name=agent_name)
            ai_msg = self.llm.bind_tools(list(tools_map.values())).invoke(messages)
            iterations += 1
            
        artifact = f"Cross-Domain Analogy Synthesis:\n\n{ai_msg.content}"
        tokens = {}
        if hasattr(ai_msg, "usage_metadata") and ai_msg.usage_metadata:
            tokens = ai_msg.usage_metadata
        elif hasattr(ai_msg, "response_metadata"):
            metrics = ai_msg.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = ai_msg.response_metadata.get("usage", {})
                
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, agent_name=agent_name, tokens=tokens)
        return artifact

    async def run_structured_reasoner(self, domain: str, query: str, lit_artifact: str, cross_domain_artifact: str, refinement_feedback: str = None):
        agent_id = "structured_reasoner"
        agent_name = "Agent 6: Graph Reasoner"
        await self._send_log(agent_id, "Processing", f"Reasoning over findings to generate Hypothesis Cards", agent_name=agent_name)
        
        prompt = f"""
You are the Discovery Orchestrator and Structured Reasoner.
You have access to the initial literature synthesis and cross-domain analogies for '{query}' in '{domain}'.

Literature Synthesis:
{lit_artifact}

Cross-Domain Analogies:
{cross_domain_artifact}

Analyze these findings and formulate exactly 3 distinct, actionable "Research Pathways" (hypotheses).
You MUST output your response as a raw JSON array of objects, with no markdown formatting or extra text.
Each object must have the following keys:
- "title": Name of the hypothesis
- "cross_domain_inspiration": Which field inspired this approach
- "theoretical_basis": The core logic
- "proposed_simulation": How this could be modeled or tested

Output ONLY the JSON array.
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease address this feedback in your reasoning."

        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})
        
        # We assume the output is valid JSON. We will pass it as the artifact string.
        artifact = response.content
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, agent_name=agent_name, tokens=tokens)
        return artifact

    async def run_domain_expert(self, domain: str, context: str, refinement_feedback: str = None):
        agent_id = "domain_expert"
        agent_name = f"{domain} Reasoning"
        await self._send_log(agent_id, "Processing", f"Ingesting literature constraints for {domain}...", agent_name=agent_name)
        
        prompt = f"""
You are a highly specialized {domain} Domain Expert AI. 
Review the following Literature Synthesis and derive constraints and logical bounds for finding a solution.
Focus specifically on {domain}-related logic. Keep your reasoning concise.

Literature Synthesis:
{context}
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease adapt your constraints based on this feedback."

        await self._send_log(agent_id, "Processing", f"Applying domain-specific reasoning via Claude Haiku on AWS Bedrock...", agent_name=agent_name)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})
        
        artifact = f"{domain} Constraints generated via Claude:\n\n{response.content}"
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, agent_name=agent_name, tokens=tokens)
        return artifact

    async def run_simulation(self, domain: str, query: str, selected_hypothesis: dict, context: str, refinement_feedback: str = None):
        agent_id = "simulation"
        await self._send_log(agent_id, "Processing", "Generating Simulation Configuration Sandbox...")
        
        prompt = f"""You are the AI Simulation Orchestrator for the Scientific Discovery OS.
The user has selected the following research hypothesis for the domain '{domain}':
Title: {selected_hypothesis.get('title')}
Proposed Simulation: {selected_hypothesis.get('proposed_simulation')}

Design a deterministic simulation configuration map for this hypothesis.
Generate a JSON object with the following structure:
{{
  "columns": [
    {{"name": "var1", "type": "normal", "mean": 50, "std": 10}},
    {{"name": "var2", "type": "uniform", "low": 0, "high": 100}}
  ],
  "rules": [
    {{"target": "result_var", "formula": "var1 * 2 + var2"}}
  ],
  "plot": {{
    "x": "var1",
    "y": "result_var",
    "type": "scatter",
    "title": "Effect of Var1 on Result"
  }}
}}

Output ONLY valid JSON inside ```json blocks. No other text.
"""
        dataset_size = 100
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease adapt the generated simulation based on this feedback."
            if "lot of data" in refinement_feedback.lower() or "large" in refinement_feedback.lower():
                dataset_size = 100000

        await self._send_log(agent_id, "Processing", "Writing simulation configuration...")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})

        
        import re
        import subprocess
        import tempfile
        import json
        import base64
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response.content, re.DOTALL)
        if not json_match:
            artifact = "No valid JSON configuration found in artifact."
            await self._send_log(agent_id, "Completed", "Simulation failed.", artifact, tokens=tokens)
            return artifact
            
        config_json = json_match.group(1)
        
        await self._send_log(agent_id, "Processing", f"Running simulation engine (size={dataset_size})...")
        
        outdir = os.path.join(os.path.dirname(__file__), "runtime_data")
        os.makedirs(outdir, exist_ok=True)
        
        config_path = os.path.join(outdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_json)
            
        generator_script = os.path.join(os.path.dirname(__file__), "utils", "data_generator.py")
        
        try:
            result = subprocess.run(
                [sys.executable, generator_script, "--config", config_path, "--size", str(dataset_size), "--outdir", outdir],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            artifact = f"### Simulation Configuration\n```json\n{config_json}\n```\n\n"
            
            if result.stderr:
                artifact += f"### Engine Logs\n```text\n{result.stderr}\n{result.stdout}\n```\n\n"
            
            csv_path = os.path.join(outdir, "simulation_preview.csv")
            if os.path.exists(csv_path):
                with open(csv_path, "r", encoding="utf-8") as f:
                    preview = "".join(f.readlines()[:10])
                artifact += f"### Data Preview (first 10 rows)\n```csv\n{preview}```\n\n"
                
            img_path = os.path.join(outdir, "simulation_output.png")
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                artifact += f"### Simulation Output\n![Plot](data:image/png;base64,{b64})\n"
                
        except Exception as e:
            artifact = f"Simulation Execution Error: {str(e)}"
        
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, tokens=tokens)
        return artifact

    async def run_hypothesis(self, selected_hypothesis: dict, refinement_feedback: str = None):
        agent_id = "hypothesis"
        agent_name = "Hypothesis Code Generator"
        await self._send_log(agent_id, "Processing", "Generating Python test script for hypothesis...", agent_name=agent_name)
        
        csv_path = os.path.join(os.path.dirname(__file__), "runtime_data", "simulation_preview.csv")
        csv_path = csv_path.replace("\\", "\\\\")
        
        prompt = f"""You are the Hypothesis Code Generator for the Scientific Discovery OS.
The Simulation engine has generated mock data based on the following hypothesis:
Title: {selected_hypothesis.get('title')}
Proposed Simulation: {selected_hypothesis.get('proposed_simulation')}

The mock data is located at: {csv_path}
Write a complete, executable Python script using `pandas`, `scipy.stats`, and `matplotlib` (if plotting is needed) to load this CSV and statistically validate the hypothesis claims. 
- Ensure the script prints clear, human-readable statistical findings (e.g., correlations, t-test p-values, descriptive stats) to standard output.
- If plotting, save the figure to `runtime_data/simulation_output.png` relative to the current directory (do not use `plt.show()`).
- Output ONLY the raw Python code within ```python blocks. No other text.
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease adapt your generated code based on this feedback."

        await self._send_log(agent_id, "Processing", "Writing Python test script...", agent_name=agent_name)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})

        
        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', response.content, re.DOTALL)
        if not code_match:
            artifact = "No valid Python code found."
            await self._send_log(agent_id, "Completed", "Code Generation failed.", artifact, tokens=tokens, agent_name=agent_name)
            return "", artifact
            
        script_code = code_match.group(1)
        
        artifact = f"### Generated Test Script\n```python\n{script_code}\n```\n\n"
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, tokens=tokens, agent_name=agent_name)
        return script_code, artifact

    async def run_experiment(self, script_code: str, refinement_feedback: str = None):
        agent_id = "experiment"
        agent_name = "Experiment Planner"
        await self._send_log(agent_id, "Processing", "Reviewing generated test code...", agent_name=agent_name)
        
        prompt = f"""You are the Experiment Planner for the Scientific Discovery OS.
The Hypothesis Code Generator has written the following Python script to test the hypothesis:

```python
{script_code}
```

Review this code to ensure:
1. All required dependencies (`pandas`, `scipy`, `matplotlib`) are standard.
2. It correctly loads data from `runtime_data/simulation_preview.csv` (or similar relative path).
3. It prints results to standard output and saves any plots appropriately.

Provide a short, bulleted assessment of the code. State whether the code is ready to execute or if any user inputs (like API keys, or custom file paths) might be missing. If it looks good, tell the user to proceed.
"""
        if refinement_feedback:
            prompt += f"\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\nPlease address this feedback in your review."

        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})

        
        artifact = f"### Code Review\n\n{response.content}\n\n**Action Required:** Please review the script. If you approve, click Proceed to run the experiment. Otherwise, provide feedback."
        await self._send_log(agent_id, "Completed", "Task finished successfully.", artifact, tokens=tokens, agent_name=agent_name)
        return artifact

    async def run_validation(self, script_code: str, selected_hypothesis: dict, refinement_feedback: str = None):
        agent_id = "validation"
        agent_name = "Data Analyst Validator"
        await self._send_log(agent_id, "Processing", "Executing generated test script...", agent_name=agent_name)
        
        import subprocess
        import tempfile
        import os
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "analyze.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_code)
                
            try:
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                stdout = result.stdout
                stderr = result.stderr
                returncode = result.returncode
            except Exception as e:
                stdout = ""
                stderr = str(e)
                returncode = 1
                
        await self._send_log(agent_id, "Processing", "Analyzing script output...", agent_name=agent_name)
        
        prompt = f"""You are the Data Analyst for the Scientific Discovery OS.
The Experiment Planner successfully ran the simulation script for the following hypothesis:
Title: {selected_hypothesis.get('title')}

Here is the standard output and standard error from the script execution:
STDOUT:
{stdout}

STDERR:
{stderr}

Analyze these results. Did the statistical tests run successfully? What do the findings mean in the context of the hypothesis? Write a clear, professional analytical conclusion summarizing if the hypothesis is supported or rejected.
"""
        response = self.llm.invoke([HumanMessage(content=prompt)])
        tokens = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata
        elif hasattr(response, "response_metadata"):
            metrics = response.response_metadata.get("amazon-bedrock-invocationMetrics", {})
            if metrics:
                tokens = {"total_tokens": metrics.get("inputTokenCount", 0) + metrics.get("outputTokenCount", 0)}
            else:
                tokens = response.response_metadata.get("usage", {})

        
        artifact = f"### Script Execution Output\n```text\n{stdout}\n{stderr}\n```\n\n### Analytical Conclusion\n\n{response.content}"
        
        await self._send_log(agent_id, "Completed", "Validation finished.", artifact, tokens=tokens, agent_name=agent_name)
        return artifact

    async def _wait_for_user_action(self, agent_id: str):
        await self._send_log(agent_id, "Paused", "Waiting for user review or refinement...")
        while True:
            try:
                data = await self.websocket.receive_text()
                import json
                msg = json.loads(data)
                if msg.get("action") == "proceed":
                    await self._send_log(agent_id, "Completed", "Approved by user.")
                    return "proceed", None
                elif msg.get("action") == "refine":
                    return "refine", msg.get("feedback")
                elif msg.get("action") == "select_hypothesis":
                    await self._send_log(agent_id, "Completed", "Hypothesis selected by user.")
                    return "select_hypothesis", msg.get("hypothesis")
                elif msg.get("action") == "go_back":
                    return "go_back", None
            except Exception as e:
                print(f"Ignored invalid websocket message during pause: {e}")
                if "disconnect" in str(e).lower():
                    raise e

    async def execute_mission(self, domain: str, query: str):
        await self._send_log("SYSTEM", "Processing", "Initializing multi-agent pipeline...")
        
        await self._send_log("SYSTEM", "Processing", "Connecting to persistent Data Layer MCP Server...")
        await init_global_mcp()
        
        # Expose MCP tools to LangChain using the global session
        async def search_openalex_func(query: str, n_results: int = 5):
            res = await global_mcp_session.call_tool("openalex_search_works", arguments={"query": query, "n_results": n_results})
            return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")

        async def get_meth_func(domain: str):
            res = await global_mcp_session.call_tool("get_domain_methodologies", arguments={"domain": domain})
            return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")

        async def find_analogous_domains_func(domain: str):
            res = await global_mcp_session.call_tool("find_analogous_domains", arguments={"domain": domain})
            return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")

        openalex_tool = StructuredTool.from_function(
            coroutine=search_openalex_func,
            name="openalex_search_works",
            description="Search the OpenAlex database for scholarly papers. Returns metadata including title, citations, and related concepts."
        )
        meth_tool = StructuredTool.from_function(
            coroutine=get_meth_func,
            name="get_domain_methodologies",
            description="Retrieve scientific methodologies related to the specified domain from the graph database."
        )
        analogous_tool = StructuredTool.from_function(
            coroutine=find_analogous_domains_func,
            name="find_analogous_domains",
            description="Find scientific domains that are analogous to the target domain based on shared scientific entities and methodologies."
        )
        
        tools_map = {
            "openalex_search_works": openalex_tool,
            "get_domain_methodologies": meth_tool,
            "find_analogous_domains": analogous_tool
        }
        
        await self._send_log("SYSTEM", "Processing", "Data Layer MCP tools mapped successfully.")

        # Human-in-the-Loop Recursive Pipeline
        refinement = None
        while True:
            lit_artifact, messages_history = await self.run_literature_intelligence(domain, query, self.llm, tools_map, refinement)
            action, refinement = await self._wait_for_user_action("literature")
            if action == "proceed": break

        refinement = None
        while True:
            cross_domain_artifact = await self.run_cross_domain_analogy(domain, query, lit_artifact, tools_map, refinement)
            action, refinement = await self._wait_for_user_action("cross_domain")
            if action == "proceed": break

        reasoner_refinement = None
        selected_hypothesis = None
        expert_artifact = None
        val_artifact = "Pipeline finished without running validation."

        while True:
            reasoner_artifact = await self.run_structured_reasoner(domain, query, lit_artifact, cross_domain_artifact, reasoner_refinement)
            
            go_back_to_reasoner = False
            while True:
                action, payload = await self._wait_for_user_action("structured_reasoner")
                
                if action == "select_hypothesis":
                    selected_hypothesis = payload
                    
                    expert_refinement = None
                    while True:
                        expert_artifact = await self.run_domain_expert(domain, reasoner_artifact, expert_refinement)
                        exp_action, exp_payload = await self._wait_for_user_action("domain_expert")
                        
                        if exp_action == "proceed":
                            go_back_to_reasoner = False
                            break
                        elif exp_action == "go_back":
                            await self._send_log("domain_expert", "Idle", "Returning to hypothesis selection.", agent_name="Domain Expert")
                            await self._send_log("structured_reasoner", "Waiting for User", "Please select a hypothesis.", artifact=reasoner_artifact, agent_name="Agent 6: Graph Reasoner")
                            go_back_to_reasoner = True
                            break
                        else:
                            expert_refinement = exp_payload
                            
                    if go_back_to_reasoner:
                        continue
                        
                    sim_refinement = None
                    while True:
                        sim_artifact = await self.run_simulation(domain, query, selected_hypothesis, expert_artifact, sim_refinement)
                        sim_action, sim_payload = await self._wait_for_user_action("simulation")
                        
                        if sim_action == "proceed":
                            go_back_to_reasoner = False
                            break
                        elif sim_action == "go_back":
                            await self._send_log("simulation", "Idle", "Returning to hypothesis selection.", agent_name="Simulation Architect")
                            await self._send_log("structured_reasoner", "Waiting for User", "Please select a hypothesis.", artifact=reasoner_artifact, agent_name="Agent 6: Graph Reasoner")
                            go_back_to_reasoner = True
                            break
                        else:
                            sim_refinement = sim_payload
                            
                    if go_back_to_reasoner:
                        continue

                    # New Pipeline Steps: Hypothesis Coder -> Experiment Planner -> Validator
                    code_refinement = None
                    script_code = ""
                    while True:
                        script_code, hyp_artifact = await self.run_hypothesis(selected_hypothesis, code_refinement)
                        
                        exp_refinement = None
                        while True:
                            exp_artifact = await self.run_experiment(script_code, exp_refinement)
                            exp_action, exp_payload = await self._wait_for_user_action("experiment")
                            
                            if exp_action == "proceed":
                                go_back_to_reasoner = False
                                break
                            elif exp_action == "go_back":
                                await self._send_log("experiment", "Idle", "Returning to code generation.", agent_name="Experiment Planner")
                                go_back_to_reasoner = True
                                break
                            else:
                                exp_refinement = exp_payload
                                
                        if not go_back_to_reasoner:
                            break
                        else:
                            code_refinement = "User rejected the experiment plan. Please rewrite the code."
                            go_back_to_reasoner = False
                            continue
                            
                    val_refinement = None
                    while True:
                        val_artifact = await self.run_validation(script_code, selected_hypothesis, val_refinement)
                        val_action, val_payload = await self._wait_for_user_action("validation")
                        
                        if val_action == "proceed":
                            go_back_to_reasoner = False
                            break
                        elif val_action == "go_back":
                            await self._send_log("validation", "Idle", "Returning to experiment planner.", agent_name="Data Analyst Validator")
                            go_back_to_reasoner = True
                            break
                        else:
                            val_refinement = val_payload
                            
                    if go_back_to_reasoner:
                        continue
                        
                    break # All steps succeeded, break out of wait_for_user_action
                    
                elif action == "proceed":
                    selected_hypothesis = {"title": "Default", "theoretical_basis": "N/A"}
                    expert_artifact = await self.run_domain_expert(domain, reasoner_artifact, None)
                    break
                else:
                    reasoner_refinement = payload
                    break # Break inner loop to regenerate Reasoner cards
                    
            if not go_back_to_reasoner and action in ["select_hypothesis", "proceed"]:
                break
        
        await self._send_log("SYSTEM", "Completed", "All agents completed successfully.", f"Final Output:\n\n{val_artifact}")
        return val_artifact
