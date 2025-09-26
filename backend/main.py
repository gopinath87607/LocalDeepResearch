from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import subprocess
import os
import uuid
import threading
import asyncio
import time
import glob
import re  # For parsing logs
from urllib.parse import urlparse
import requests

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://localhost:3001"])
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://localhost:3001"])

research_sessions = {}
active_connections = {}
chat_sessions = {}

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/research/start', methods=['POST'])
def start_research():
    data = request.get_json()
    query = data.get("query", "")
    session_id = data.get("session_id") or str(uuid.uuid4())
    
    # Modified: Reject simple greetings
    if len(query.strip()) < 3 or query.lower() in ['hi', 'hello', 'hey', 'what\'s up']:
        return jsonify({"error": "Please ask a research question (e.g., 'What is xAI?'). Greetings get a simple reply!"}), 400
    
    research_sessions[session_id] = {
        "query": query,
        "status": "started",
        "steps": [],
        "sources": [],
        "result": ""
    }
    
    # Initialize chat session for this research
    chat_sessions[session_id] = {
        "messages": [],
        "research_context": query,
        "research_result": ""
    }
    
    # Run research in background thread
    thread = threading.Thread(target=run_deepresearch_sync, args=(session_id, query))
    thread.daemon = True
    thread.start()
    
    return jsonify({"session_id": session_id, "status": "started"})

@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    session_id = data.get("session_id")
    message = data.get("message", "").strip()
    
    if not session_id or not message:
        return jsonify({"error": "Missing session_id or message"}), 400
    
    if session_id not in chat_sessions:
        return jsonify({"error": "Invalid session_id"}), 400
    
    # Add user message to chat history
    chat_sessions[session_id]["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": time.strftime('%H:%M:%S')
    })
    
    # Send chat response in background thread
    thread = threading.Thread(target=handle_chat_message, args=(session_id, message))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "processing"})

def handle_chat_message(session_id, user_message):
    """Handle chat message with main model"""
    try:
        chat_session = chat_sessions[session_id]
        research_context = chat_session.get("research_context", "")
        research_result = chat_session.get("research_result", "")
        
        # Build context for the main model
        system_prompt = f"""You are a helpful AI assistant. The user recently completed a research session about: "{research_context}"

The research results were:
{research_result[:2000]}...

Please respond to the user's follow-up questions based on this context and your general knowledge. Be helpful, accurate, and reference the research when relevant."""

        # Prepare messages for the model
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add recent chat history (last 10 messages to avoid token limits)
        recent_messages = chat_session["messages"][-10:]
        for msg in recent_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Call main model
        response = call_main_model(messages)
        
        # Add assistant response to chat history
        chat_sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": time.strftime('%H:%M:%S')
        })
        
        # Send response to frontend
        send_update(session_id, {
            "type": "chat_response",
            "message": response,
            "timestamp": time.strftime('%H:%M:%S')
        })
        
    except Exception as e:
        print(f"Error in chat handling: {str(e)}")
        send_update(session_id, {
            "type": "chat_error",
            "message": f"Sorry, I encountered an error: {str(e)}"
        })

def call_main_model(messages, max_retries=3):
    """Call the main research model for chat"""
    api_key = os.environ.get("API_KEY", "dummy-key")
    api_base = os.environ.get("API_BASE", "http://localhost:8080/v1")
    model_name = os.environ.get("SUMMARY_MODEL_NAME", "deepresearch")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{api_base}/chat/completions",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"API error: {response.status_code} - {response.text}")
                if attempt == max_retries - 1:
                    return "I'm having trouble connecting to the model. Please try again."
                    
        except requests.RequestException as e:
            print(f"Request error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                return "I'm having trouble connecting to the model. Please check if the server is running."
            time.sleep(1)
    
    return "Unable to get response from the model after multiple attempts."

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    session_id = data.get('session_id')
    if session_id:
        active_connections[session_id] = request.sid
        print(f'Client joined session: {session_id}')

def send_update(session_id, update):
    if session_id in active_connections:
        print(f"Sending update to session {session_id}: {update['type']}")
        socketio.emit('research_update', update, room=active_connections[session_id])
    else:
        print(f"No active connection for session {session_id} - update {update['type']} dropped")

def extract_and_send_urls(session_id, line_stripped):
    """Extract URLs from research output and send as separate events"""
    url_patterns = [
        # Direct URLs
        r'https?://[^\s\)]+',
        # Visit tool patterns
        r'"url":\s*"([^"]+)"',
        # Search result links
        r'\[([^\]]+)\]\(([^)]+)\)',
        # JSON arrays with URLs
        r'"url":\s*\[([^\]]+)\]'
    ]
    
    found_urls = []
    
    for pattern_idx, pattern in enumerate(url_patterns):
        matches = re.finditer(pattern, line_stripped)
        for match in matches:
            urls_to_process = []
            title = ''
            
            if pattern_idx == 0:  # Direct URL
                url = match.group(0).rstrip('.,;:!?')
                urls_to_process.append(url)
            elif pattern_idx == 1:  # JSON url field
                url = match.group(1)
                urls_to_process.append(url)
            elif pattern_idx == 2:  # Markdown link
                title = match.group(1)
                url = match.group(2)
                urls_to_process.append(url)
            elif pattern_idx == 3:  # JSON array
                # Parse URLs from array
                url_array_str = match.group(1)
                url_matches = re.findall(r'"([^"]*https?://[^"]*)"', url_array_str)
                urls_to_process.extend(url_matches)
            
            for url in urls_to_process:
                if url and url.startswith('http') and len(url) > 10:
                    # Extract domain for display
                    try:
                        parsed = urlparse(url)
                        domain = parsed.netloc.replace('www.', '')
                        found_urls.append({
                            'url': url,
                            'domain': domain,
                            'title': title if title else domain,
                            'timestamp': time.strftime('%H:%M:%S'),
                            'displayName': title if title else domain
                        })
                    except:
                        continue
    
    # Send URLs as separate events
    for url_info in found_urls:
        send_update(session_id, {
            "type": "url_found",
            "url_info": url_info
        })

def intercept_visit_calls(session_id, tool_content):
    """Specifically look for visit tool calls and extract URLs"""
    if '"name": "visit"' in tool_content or 'visit(' in tool_content:
        # Parse visit tool calls
        url_patterns = [
            r'"url":\s*"([^"]+)"',
            r'"url":\s*\[([^\]]+)\]'
        ]
        goal_pattern = r'"goal":\s*"([^"]+)"'
        
        goal_match = re.search(goal_pattern, tool_content)
        goal = goal_match.group(1) if goal_match else "Research"
        
        urls = []
        for pattern in url_patterns:
            url_match = re.search(pattern, tool_content)
            if url_match:
                if pattern == url_patterns[0]:  # Single URL
                    urls.append(url_match.group(1))
                else:  # Array of URLs
                    url_array = url_match.group(1).replace('"', '').split(',')
                    urls.extend([u.strip() for u in url_array])
        
        # Send each URL as a visit event
        for url in urls:
            if url.startswith('http'):
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace('www.', '')
                    send_update(session_id, {
                        "type": "url_visited",
                        "url_info": {
                            'url': url,
                            'domain': domain,
                            'goal': goal,
                            'timestamp': time.strftime('%H:%M:%S'),
                            'status': 'visiting',
                            'displayName': domain
                        }
                    })
                except:
                    continue

def run_deepresearch_sync(session_id, query):
    try:
        # Delay to allow client to join session
        time.sleep(1)
        send_update(session_id, {
            "type": "research_started",
            "session_id": session_id,
            "query": query
        })
        
        # Create input file (updated to inference/eval_data for script compatibility)
        input_file = f"/home/gopi/DeepResearch/inference/eval_data/session_{session_id}.jsonl"
        os.makedirs("/home/gopi/DeepResearch/inference/eval_data", exist_ok=True)
        
        with open(input_file, "w") as f:
            f.write(json.dumps({"question": query, "answer": ""}) + "\n")
        
        print(f"Input file created: {input_file}")
        
        # Run DeepResearch
        result = run_deepresearch_command(session_id, query)
        
        # Store research result in chat session for context
        if session_id in chat_sessions:
            chat_sessions[session_id]["research_result"] = result
        
        send_update(session_id, {
            "type": "research_complete",
            "result": result,  # Now just the prediction (clean answer)
            "session_id": session_id
        })
        
        # Enable chat mode
        send_update(session_id, {
            "type": "chat_ready",
            "message": "Research complete! You can now ask follow-up questions."
        })
        
    except Exception as e:
        print(f"Error in run_deepresearch_sync: {str(e)}")
        send_update(session_id, {
            "type": "error",
            "message": str(e)
        })

def run_deepresearch_command(session_id, query):
    try:
        deepresearch_path = "/home/gopi/DeepResearch"
        
        env = os.environ.copy()
        env['DATASET'] = f"session_{session_id}"
        env['OUTPUT_PATH'] = f"{deepresearch_path}/outputs/session_{session_id}"
        print(f"Environment set: DATASET={env['DATASET']}, OUTPUT_PATH={env['OUTPUT_PATH']}")
        
        # Run the bash script with env vars
        process = subprocess.Popen(
            [f"{deepresearch_path}/inference/run_react_infer_with_progress.sh"],
            cwd=deepresearch_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream output with better categorization AND URL extraction
        for line in iter(process.stdout.readline, ''):
            line_stripped = line.strip()
            print(f"Subprocess line: {line_stripped}")  # Keep backend logging
            
            if not line_stripped:
                continue
            
            # Extract and send URLs from this line
            extract_and_send_urls(session_id, line_stripped)
                
            # Progress updates (step tracking)
            if "PROGRESS:" in line:
                try:
                    progress_data = json.loads(line.split("PROGRESS: ")[1])
                    step_num = progress_data.get("step", 1)
                    send_update(session_id, {
                        "type": "step_start", 
                        "step": progress_data, 
                        "progress": (step_num / 5) * 100
                    })
                except:
                    pass
            
            # ReAct thoughts and actions (for research intelligence panel)
            elif "<think>" in line:
                send_update(session_id, {"type": "react_thought", "content": line_stripped})
            elif "<tool_call>" in line:
                send_update(session_id, {"type": "react_action", "content": line_stripped})
            
            # FIXED: Capture JSON tool call content (arguments/parameters)
            elif line_stripped.startswith('{"name":') and any(key in line for key in ["arguments", "query", "url"]):
                send_update(session_id, {"type": "react_action", "content": line_stripped})
                # Also intercept visit calls for URL tracking
                intercept_visit_calls(session_id, line_stripped)
            elif line_stripped.startswith("</tool_call>"):
                send_update(session_id, {"type": "react_action", "content": line_stripped})
            
            # Tool responses and search results (research intelligence)
            elif line.startswith("Round") and ":" in line:
                send_update(session_id, {"type": "react_action", "content": line_stripped})
            elif "token count:" in line:
                send_update(session_id, {"type": "research_log", "content": line_stripped})
            
            # ADDED: Capture summaries and extracted content
            elif line.startswith("Summary:") or "summary:" in line.lower():
                send_update(session_id, {"type": "research_log", "content": line_stripped})
            elif any(keyword in line.lower() for keyword in ["search results", "visiting", "found", "extracted", "analysis", "token", "contract", "supply"]):
                # Capture research findings and analysis
                if len(line_stripped) > 20:  # Only meaningful content
                    send_update(session_id, {"type": "research_log", "content": line_stripped})
                
            # Server status (for server panel)
            elif any(server_msg in line for server_msg in ["server is ready", "Starting inference", "Processing", "Model endpoint"]):
                send_update(session_id, {"type": "server_status", "content": line_stripped})
            
            # Important completion messages
            elif any(complete in line for complete in ["Research complete", "All tasks completed", "COMPLETE:", "✓"]):
                send_update(session_id, {"type": "research_details", "content": line_stripped})
            
            # General research activity - capture more research content
            elif not any(skip in line.lower() for skip in ["dataset name:", "output directory:", "data splitting:", "total items", "rollout", "successfully processed"]):
                # Capture longer meaningful content (like summaries, analysis, etc.)
                if len(line_stripped) > 25:
                    # Check if it's research-relevant content
                    if (any(research_indicator in line.lower() for research_indicator in 
                        ["astra", "token", "contract", "blockchain", "bep-20", "supply", "holders", "price", "market", "address", "summary", "analysis", "keeladi", "kodumanal", "archaeological", "excavation"]) 
                        or line.startswith(("The ", "This ", "Based on", "According to", "Analysis:"))
                        or ("query" in line and "[" in line)):  # Capture query arrays
                        send_update(session_id, {"type": "research_log", "content": line_stripped})
                # Server/system messages
                elif any(server_word in line.lower() for server_word in ["model", "endpoint", "processing", "rollout", "workers"]):
                    send_update(session_id, {"type": "server_status", "content": line_stripped})
        
        return_code = process.poll()
        print(f"Subprocess return code: {return_code}")
        
        # Debug: List all files in output dir
        output_dir = f"/home/gopi/DeepResearch/outputs/session_{session_id}"
        if os.path.exists(output_dir):
            all_files = os.listdir(output_dir)
            print(f"All files in {output_dir}: {all_files}")
            for subdir in all_files:
                sub_path = os.path.join(output_dir, subdir)
                if os.path.isdir(sub_path):
                    sub_files = os.listdir(sub_path)
                    print(f"Files in {subdir}: {sub_files}")
                    for deeper_sub in sub_files:
                        deeper_path = os.path.join(sub_path, deeper_sub)
                        if os.path.isdir(deeper_path):
                            deeper_files = os.listdir(deeper_path)
                            print(f"Files in {subdir}/{deeper_sub}: {deeper_files}")
        
        if return_code == 0:
            # Flexible search for any .jsonl file in the output dir (handles iter1.jsonl or predictions.jsonl)
            output_dir = f"/home/gopi/DeepResearch/outputs/session_{session_id}"
            if os.path.exists(output_dir):
                # Recursive search for .jsonl files
                jsonl_files = []
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.jsonl'):
                            jsonl_files.append(os.path.join(root, file))
                
                if jsonl_files:
                    # Prefer 'predictions.jsonl' if exists, else take the first .jsonl (e.g., iter1.jsonl)
                    output_file = next((f for f in jsonl_files if 'predictions' in f), jsonl_files[0])
                    
                    # FIXED: Parse JSONL and extract only 'prediction' for clean answer
                    with open(output_file, "r") as f:
                        lines = f.readlines()
                        if lines:
                            try:
                                result_json = json.loads(lines[-1].strip())  # Last line is the final result
                                clean_result = result_json.get('prediction', 'No prediction found')  # Extract prediction only
                                print(f"Output file read from: {output_file}")
                                print(f"Extracted prediction: {clean_result[:100]}...")  # Debug snippet
                                return clean_result
                            except json.JSONDecodeError as e:
                                print(f"JSON parse error: {e}")
                                return "Research completed but output parsing failed"
                        else:
                            return "Research completed successfully (empty output file)"
                else:
                    print("No .jsonl files found in output dir")
                    return "Research completed successfully (no output file generated)"
            else:
                print(f"Output dir not found: {output_dir}")
                return "Research completed but output directory missing"
        else:
            error_msg = f"Error: Subprocess failed with code {return_code}"
            print(error_msg)
            return error_msg
            
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return error_msg

if __name__ == "__main__":
    print("Starting DeepResearch Flask Backend on http://localhost:8000")
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
