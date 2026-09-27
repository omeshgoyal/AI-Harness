from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import uvicorn
import config
from llm import call_llm, get_system_prompt, get_totals
from tools import safe_call
from context import reminder
from permissions import check
import history
import checkpoints
import session

app = FastAPI()

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state
global_messages = [{"role": "system", "content": get_system_prompt()}]
pending_tool_calls = []
current_permission_request = None
current_session_name = None

@app.get("/")
def index():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

def get_permission_data():
    if not current_permission_request:
        return None
    func_name = current_permission_request.function.name
    try:
        args = json.loads(current_permission_request.function.arguments)
    except:
        args = {}
    return {
        "tool_call_id": current_permission_request.id,
        "func_name": func_name,
        "args": args
    }

@app.get("/api/state")
def get_state():
    return {
        "messages": global_messages,
        "cost": get_totals()["cost_usd"],
        "pending_permission": current_permission_request is not None,
        "permission_data": get_permission_data(),
        "sessions": session.list_sessions(),
        "current_session": current_session_name
    }

@app.post("/api/session/new")
async def new_session():
    global global_messages, pending_tool_calls, current_permission_request, current_session_name
    global_messages = [{"role": "system", "content": get_system_prompt()}]
    pending_tool_calls = []
    current_permission_request = None
    current_session_name = None
    checkpoints.begin_turn()
    return {"status": "ok"}

@app.post("/api/session/load")
async def load_session(req: Request):
    data = await req.json()
    name = data.get("name")
    loaded = session.load(name)
    if loaded:
        global global_messages, pending_tool_calls, current_permission_request, current_session_name
        global_messages = loaded
        pending_tool_calls = []
        current_permission_request = None
        current_session_name = name
        return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/session/save")
async def save_session(req: Request):
    data = await req.json()
    name = data.get("name")
    path = session.save(global_messages, name)
    global current_session_name
    current_session_name = name or path.split("/")[-1].replace(".json", "")
    return {"status": "ok", "name": current_session_name}

def process_tools():
    global pending_tool_calls
    global current_permission_request
    
    while pending_tool_calls:
        tool_call = pending_tool_calls.pop(0)
        func_name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except:
            args = {}
            
        action, reason = check(func_name, args)
        
        if action in ["ask", "confirm"]:
            current_permission_request = tool_call
            return {
                "status": "permission_required",
                "permission_data": get_permission_data()
            }
        elif action == "deny":
            global_messages.append({
                "role": "tool", "tool_call_id": tool_call.id,
                "name": func_name, "content": f"Blocked by policy: {reason}"
            })
        else:
            result = safe_call(func_name, args)
            global_messages.append({
                "role": "tool", "tool_call_id": tool_call.id,
                "name": func_name, "content": str(result)
            })
    return None

def run_loop():
    global pending_tool_calls
    
    res = process_tools()
    if res:
        return res
        
    for turn in range(config.MAX_AGENT_TURNS):
        global_messages[0]["content"] = get_system_prompt()
        
        try:
            message, usage = call_llm(global_messages + [reminder()])
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
        msg_dict = message.model_dump(exclude_none=True)
        global_messages.append(msg_dict)
        
        if not getattr(message, 'tool_calls', None):
            checkpoints.commit_turn()
            history.sweep()
            history.strip(global_messages)
            return {"status": "done"}
            
        pending_tool_calls.extend(message.tool_calls)
        
        res = process_tools()
        if res:
            return res
            
    return {"status": "done"}

@app.post("/api/chat")
async def chat(req: Request):
    data = await req.json()
    user_input = data.get("text")
    
    global global_messages
    global_messages.append({"role": "user", "content": user_input})
    checkpoints.begin_turn()
    
    return run_loop()

@app.post("/api/permission")
async def handle_permission(req: Request):
    data = await req.json()
    allow = data.get("allow", False)
    
    global current_permission_request
    if not current_permission_request:
        return {"error": "No pending request"}
        
    func_name = current_permission_request.function.name
    
    if allow:
        try:
            args = json.loads(current_permission_request.function.arguments)
        except:
            args = {}
        result = safe_call(func_name, args)
        global_messages.append({
            "role": "tool", "tool_call_id": current_permission_request.id,
            "name": func_name, "content": str(result)
        })
    else:
        global_messages.append({
            "role": "tool", "tool_call_id": current_permission_request.id,
            "name": func_name, "content": "Denied by user."
        })
        
    current_permission_request = None
    return run_loop()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
