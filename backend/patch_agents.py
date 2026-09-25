import re

with open('agents.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add _wait_for_user_action to AgentManager
wait_func = """
    async def _wait_for_user_action(self, agent_id: str):
        await self._send_log(agent_id, "Paused", "Waiting for user review or refinement...")
        while True:
            try:
                data = await self.websocket.receive_text()
                import json
                msg = json.loads(data)
                if msg.get("action") == "proceed":
                    return "proceed", None
                elif msg.get("action") == "refine":
                    return "refine", msg.get("feedback")
            except Exception as e:
                print(f"Ignored invalid websocket message during pause: {e}")
"""
if "_wait_for_user_action" not in code:
    code = code.replace("    async def execute_mission(", wait_func + "\n    async def execute_mission(")

# 2. Add refinement_feedback to all run_* functions and update their prompts
code = re.sub(r'async def run_literature_intelligence\(self, domain: str, query: str, llm, tools_map\):', 
              r'async def run_literature_intelligence(self, domain: str, query: str, llm, tools_map, refinement_feedback: str = None):', code)

lit_prompt_update = """Once you have retrieved the data from the tools, formulate a synthesized summary of the findings.
"\"\"
        if refinement_feedback:
            prompt += f"\\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\\nPlease incorporate this feedback into your updated search strategy and synthesis."
"""
code = code.replace('Once you have retrieved the data from the tools, formulate a synthesized summary of the findings.\n"""', lit_prompt_update)


code = re.sub(r'async def run_structured_reasoner\(self, domain: str, query: str, messages_history: list\):', 
              r'async def run_structured_reasoner(self, domain: str, query: str, messages_history: list, refinement_feedback: str = None):', code)

reasoner_prompt_update = """{extracted_findings}
"\"\"
        if refinement_feedback:
            prompt += f"\\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\\nPlease address this feedback in your reasoning."
"""
code = code.replace('{extracted_findings}\n"""', reasoner_prompt_update)


code = re.sub(r'async def run_domain_expert\(self, domain: str, context: str\):', 
              r'async def run_domain_expert(self, domain: str, context: str, refinement_feedback: str = None):', code)

expert_prompt_update = """{context}
"\"\"
        if refinement_feedback:
            prompt += f"\\nUSER REFINEMENT FEEDBACK: {refinement_feedback}\\nPlease adapt your constraints based on this feedback."
"""
code = code.replace('{context}\n"""', expert_prompt_update)


code = re.sub(r'async def run_simulation\(self\):', r'async def run_simulation(self, refinement_feedback: str = None):', code)
code = code.replace('artifact = "Simulation Results: 50 models tested. 3 candidates show theoretical stability."',
                    'artifact = f"Simulation Results: 50 models tested. 3 candidates show theoretical stability. {str(refinement_feedback) if refinement_feedback else \'\'}"')

code = re.sub(r'async def run_hypothesis\(self\):', r'async def run_hypothesis(self, refinement_feedback: str = None):', code)
code = code.replace('artifact = "Hypothesis: Candidate 2 exhibits novel property X under condition Y."',
                    'artifact = f"Hypothesis: Candidate 2 exhibits novel property X under condition Y. {str(refinement_feedback) if refinement_feedback else \'\'}"')

code = re.sub(r'async def run_experiment\(self\):', r'async def run_experiment(self, refinement_feedback: str = None):', code)
code = code.replace('artifact = "Experimental Protocol: Step-by-step synthesis and measurement plan generated."',
                    'artifact = f"Experimental Protocol: Step-by-step synthesis and measurement plan generated. {str(refinement_feedback) if refinement_feedback else \'\'}"')

code = re.sub(r'async def run_validation\(self\):', r'async def run_validation(self, refinement_feedback: str = None):', code)
code = code.replace('artifact = "Final Report: Discovery is valid. Ready for deployment."',
                    'artifact = f"Final Report: Discovery is valid. Ready for deployment. {str(refinement_feedback) if refinement_feedback else \'\'}"')


# 3. Update execute_mission logic
old_pipeline = """        # Sequential pipeline execution passing MCP tools
        lit_artifact, messages_history = await self.run_literature_intelligence(domain, query, self.llm, tools_map)
        reasoner_artifact = await self.run_structured_reasoner(domain, query, messages_history)
        expert_artifact = await self.run_domain_expert(domain, reasoner_artifact)
        sim_artifact = await self.run_simulation()
        hyp_artifact = await self.run_hypothesis()
        exp_artifact = await self.run_experiment()
        val_artifact = await self.run_validation()"""

new_pipeline = """        # Human-in-the-Loop Recursive Pipeline
        refinement = None
        while True:
            lit_artifact, messages_history = await self.run_literature_intelligence(domain, query, self.llm, tools_map, refinement)
            action, refinement = await self._wait_for_user_action("literature")
            if action == "proceed": break

        refinement = None
        while True:
            reasoner_artifact = await self.run_structured_reasoner(domain, query, messages_history, refinement)
            action, refinement = await self._wait_for_user_action("structured_reasoner")
            if action == "proceed": break

        refinement = None
        while True:
            expert_artifact = await self.run_domain_expert(domain, reasoner_artifact, refinement)
            action, refinement = await self._wait_for_user_action("domain_expert")
            if action == "proceed": break

        refinement = None
        while True:
            sim_artifact = await self.run_simulation(refinement)
            action, refinement = await self._wait_for_user_action("simulation")
            if action == "proceed": break

        refinement = None
        while True:
            hyp_artifact = await self.run_hypothesis(refinement)
            action, refinement = await self._wait_for_user_action("hypothesis")
            if action == "proceed": break

        refinement = None
        while True:
            exp_artifact = await self.run_experiment(refinement)
            action, refinement = await self._wait_for_user_action("experiment")
            if action == "proceed": break

        refinement = None
        while True:
            val_artifact = await self.run_validation(refinement)
            action, refinement = await self._wait_for_user_action("validation")
            if action == "proceed": break"""

code = code.replace(old_pipeline, new_pipeline)

with open('agents.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patch applied.")
