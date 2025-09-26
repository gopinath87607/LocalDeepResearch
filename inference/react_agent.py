import json
import json5
import os
from typing import Dict, Iterator, List, Literal, Optional, Tuple, Union
from qwen_agent.llm.schema import Message
from qwen_agent.utils.utils import build_text_completion_prompt
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError
import tiktoken
from transformers import AutoTokenizer 
from datetime import datetime
from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, DEFAULT_SYSTEM_MESSAGE, Message
from qwen_agent.settings import MAX_LLM_CALL_PER_RUN
from qwen_agent.tools import BaseTool
from qwen_agent.utils.utils import format_as_text_message, merge_generate_cfgs
from prompt import *
import time
import asyncio
import re  # For parsing

from tool_file import *
from tool_scholar import *
from tool_python import *
from tool_search import *
from tool_visit import *

OBS_START = '<tool_response>'
OBS_END = '\n</tool_response>'

MAX_LLM_CALL_PER_RUN = int(os.getenv('MAX_LLM_CALL_PER_RUN', 100))

TOOL_CLASS = [
    FileParser(),
    Scholar(),
    Visit(),
    Search(),
    PythonInterpreter(),
]
TOOL_MAP = {tool.name: tool for tool in TOOL_CLASS}

import random
import datetime


def today_date():
    return datetime.date.today().strftime("%Y-%m-%d")


def make_serializable(obj):
    """Convert any object to JSON serializable format"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [make_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    else:
        return str(obj)


class MultiTurnReactAgent(FnCallAgent):
    def __init__(self,
                 function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
                 llm: Optional[Union[Dict, BaseChatModel]] = None,
                 **kwargs):

        self.llm_generate_cfg = llm["generate_cfg"]
        self.llm_local_path = llm["model"]
        # Load tokenizer for chat template
        self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2-7B-Instruct")  # Adjust if your model has custom tokenizer
        self.last_tool_call = None  # Track last tool to detect repeats
        self.dummy_count = 0  # Track dummies to force answer
        self.model = "deepresearch"  # Default model name for llama.cpp

    def sanity_check_output(self, content):
        return "<think>" in content and "</think>" in content
    
    def call_server(self, msgs, planning_port, max_tries=10):
        
        # Configure for llama.cpp server
        openai_api_key = "dummy-key"  # llama.cpp doesn't need real API key
        openai_api_base = f"http://127.0.0.1:{planning_port}/v1"

        client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            timeout=600.0,
        )

        base_sleep_time = 1 
        
        for attempt in range(max_tries):
            try:
                print(f"--- Attempting to call llama.cpp server, try {attempt + 1}/{max_tries} ---")
                print(f"--- Using endpoint: {openai_api_base} ---")
                
                # Apply chat template to msgs
                prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                # Send as completion-style (user message) to avoid role issues
                formatted_msgs = [{"role": "user", "content": prompt}]
                
                chat_response = client.chat.completions.create(
                    model=self.model,  # Model name for llama.cpp
                    messages=formatted_msgs,
                    stop=["\n<tool_response>", "<tool_response>"],  # Removed "<answer>" to allow full gen
                    temperature=self.llm_generate_cfg.get('temperature', 0.6),
                    top_p=self.llm_generate_cfg.get('top_p', 0.95),
                    max_tokens=4000,  # Reduced for llama.cpp
                )
                
                content = chat_response.choices[0].message.content.strip()
                print(f"--- llama.cpp server call successful ---")
                print(f"Generated content: {content[:200]}...")  # Debug: Log snippet
                return content
                
            except APIError as e:
                if e.status_code == 500 and "assistant messages" in str(e).lower():
                    print(f"History error detected (consecutive assistants): {str(e)}")
                    # Quick fix: Append dummy user observation
                    msgs.append({"role": "user", "content": "Observation: No new information from previous step. Proceed to think and answer."})
                    if attempt < max_tries - 1:  # One more try only
                        time.sleep(base_sleep_time * (2 ** attempt))
                        continue
                    else:
                        raise  # Fail after fix attempt
                # Existing retry for other errors
                print(f"Error: Attempt {attempt + 1} failed with API error: {str(e)}")
                if attempt < max_tries - 1:
                    time.sleep(base_sleep_time * (2 ** attempt))
                    continue
                else:
                    raise
            except (APIConnectionError, APITimeoutError) as e:
                print(f"Connection/Timeout error: {str(e)}")
                if attempt < max_tries - 1:
                    time.sleep(base_sleep_time * (2 ** attempt))
                    continue
                else:
                    raise
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                raise

        return ""  # Fallback

    # Fixed: Match original signature _run(self, task_info, model)
    def _run(self, data: dict, model: str, **kwargs) -> dict:
        self.model = model
        try:
            item = data['item']
            question = item.get("question", "")
            answer = item.get("answer", "")
            rollout_idx = data.get("rollout_idx", 1)
        except:
            raw_msg = data['item']['messages'][1]["content"]
            question = raw_msg.split("User:")[1].strip() if "User:" in raw_msg else raw_msg
            answer = ""  # Fallback
            rollout_idx = 1
        
        start_time = time.time()
        planning_port = data['planning_port']
        self.user_prompt = question
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT + today_date()}]
        messages.append({"role": "user", "content": question})
        
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        max_rounds = 15  # Reduced: Shorter loops to prevent repetition
        round_num = 0  # Renamed to avoid conflict with outer 'round'
        prediction = None
        termination = None
        tool_count = 0  # Count tools to force synthesis after 2
        
        while round_num < max_rounds and num_llm_calls_available > 0:
            # Check whether time is reached
            if time.time() - start_time > 150 * 60: # 150 minutes in seconds
                prediction = 'No answer found after 2h30mins'
                termination = 'No answer found after 2h30mins'
                break
            
            round_num += 1
            if num_llm_calls_available <= 0:
                break
            
            # Call LLM
            content = self.call_server(messages, planning_port)
            num_llm_calls_available -= 1
            print(f"Round {round_num}: {content}")
            
            # Early stop if <answer> detected
            if '<answer>' in content and '</answer>' in content:
                print("Research complete: <answer> detected, stopping loop.")
                prediction = content.split('<answer>')[1].split('</answer>')[0].strip()
                messages.append({"role": "assistant", "content": content.strip()})
                termination = 'answer'
                break
            
            # Append assistant response
            messages.append({"role": "assistant", "content": content.strip()})
            
            # Parse for tool call
            tool_call_match = re.search(r'<tool_call>\s*(\{"name":\s*"(\w+)",\s*"arguments":\s*({.*?})\})\s*</tool_call>', content, re.DOTALL | re.IGNORECASE)
            if tool_call_match:
                tool_name = tool_call_match.group(2)
                tool_args_str = tool_call_match.group(3)
                current_tool_call = (tool_name, tool_args_str)  # Track for repeat check
                try:
                    tool_args = json5.loads(tool_args_str)
                except:
                    tool_args = {}
                
                # Detect repeat tool call
                if current_tool_call == self.last_tool_call:
                    print("Repeated tool call detected; forcing synthesis.")
                    observation = "Repeated tool—synthesize existing info into answer."
                    tool_count += 1  # Count as executed
                else:
                    # Execute tool
                    observation = self.custom_call_tool(tool_name, tool_args)
                    tool_count += 1
                    self.last_tool_call = current_tool_call
                
                # Add observation as user
                messages.append({"role": "user", "content": f"{OBS_START}{observation}{OBS_END}"})
                
                # After tool, nudge for synthesis if enough tools
                if tool_count >= 2:
                    messages.append({"role": "user", "content": "You have gathered sufficient information from tools. Synthesize all into a final <answer> now—do not call more tools."})
            else:
                # No tool call → add dummy observation
                self.dummy_count += 1
                print("No tool call detected; adding dummy observation to continue.")
                messages.append({"role": "user", "content": "Observation: This is a simple query. No tools needed—provide final answer now."})
                
                # After 2 dummies, force <answer>
                if self.dummy_count >= 2:
                    messages.append({"role": "user", "content": "End with <answer> your final response now—no more thinking or tools."})
            
            # Token check
            max_tokens = 108 * 1024
            token_count = self.count_tokens(messages)
            print(f"round: {round_num}, token count: {token_count}")
            
            if token_count > max_tokens:
                print(f"Token quantity exceeds the limit: {token_count} > {max_tokens}")
                messages[-1]['content'] = "You have now reached the maximum context length. Provide your final answer."
                content = self.call_server(messages, planning_port)
                messages.append({"role": "assistant", "content": content.strip()})
                prediction = content  # Fallback
                termination = 'token limit reached'
                break
        
        # Fallback if no answer: Extract from last <think> or default
        if prediction is None:
            if '<answer>' in messages[-1]['content']:
                prediction = messages[-1]['content'].split('<answer>')[1].split('</answer>')[0]
                termination = 'answer'
            else:
                last_think = re.search(r'<think>(.*?)</think>', messages[-1]['content'], re.DOTALL)
                prediction = last_think.group(1).strip() if last_think else 'Based on reasoning, the answer is a comprehensive summary of the query.'
                termination = 'max_rounds reached'
                if num_llm_calls_available == 0:
                    termination = 'exceed available llm calls'
        
        # Reset trackers
        self.last_tool_call = None
        self.dummy_count = 0
        
        # Build result
        result = {
            "question": str(question),
            "answer": str(answer),
            "messages": make_serializable(messages),
            "prediction": str(prediction),
            "termination": str(termination),
            "rollout_idx": rollout_idx,
            "rollout_id": rollout_idx
        }
        return result

    def custom_call_tool(self, tool_name: str, tool_args: dict, **kwargs):
        if tool_name in TOOL_MAP:
            tool_args["params"] = tool_args
            if "python" in tool_name.lower():
                # Handle Python: Expect code in arguments or fallback
                code_raw = tool_args.get('code', '')  # Adjust based on expected arg
                if code_raw:
                    result = TOOL_MAP['PythonInterpreter'].call(code_raw)
                else:
                    result = TOOL_MAP['PythonInterpreter'].call(tool_args)
            elif tool_name == "parse_file":
                params = {"files": tool_args["files"]}
                raw_result = asyncio.run(TOOL_MAP[tool_name].call(params, file_root_path="./eval_data/file_corpus"))
                result = str(raw_result) if not isinstance(raw_result, str) else raw_result
            else:
                raw_result = TOOL_MAP[tool_name].call(tool_args, **kwargs)
                result = str(raw_result)
            return result
        else:
            return f"Error: Tool {tool_name} not found"

    # Fixed: count_tokens now takes 'messages' and uses tokenizer correctly
    def count_tokens(self, messages):
        # Use the class tokenizer
        full_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False)
        tokens = self.tokenizer(full_prompt, return_tensors="pt")
        token_count = len(tokens["input_ids"][0])
        return token_count
