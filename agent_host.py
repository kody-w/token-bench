"""Generic stdio MCP host for RAPP agent.py files: exposes every *_agent.py in a folder as tools.
Usage: python3 agent_host.py <agents_dir>"""
import importlib.util, inspect, json, os, sys
d = os.path.abspath(sys.argv[1]); sys.path.insert(0, d)
agents = {}
for f in sorted(os.listdir(d)):
    if f.endswith("_agent.py"):
        spec = importlib.util.spec_from_file_location(f[:-3], os.path.join(d, f)); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ == mod.__name__ and hasattr(cls, "perform"):
                try: a = cls()
                except TypeError: continue
                if getattr(a, "metadata", None): agents[a.metadata["name"]] = a
def send(m): sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
for line in sys.stdin:
    if not line.strip(): continue
    m = json.loads(line); mid = m.get("id"); meth = m.get("method")
    if meth == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": m["params"].get("protocolVersion", "2025-06-18"),
              "capabilities": {"tools": {}}, "serverInfo": {"name": "agentpy", "version": "1"}}})
    elif meth == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": n, "description": a.metadata["description"],
              "inputSchema": a.metadata.get("parameters", {"type": "object", "properties": {}})} for n, a in agents.items()]}})
    elif meth == "tools/call":
        p = m["params"]
        try: out, err = str(agents[p["name"]].perform(**p.get("arguments", {}))), False
        except Exception as e: out, err = f"error: {e}", True
        send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": out}], "isError": err}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
