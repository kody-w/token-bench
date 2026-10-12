#!/usr/bin/env python3
"""Start a measured Brainstem for the bench.

It copies your installed Brainstem's code into a temporary folder (your install is only read, never
written), runs it on its own port with only the bench's agent.py files, and logs the token usage of
every model call it makes to a file the bench reads. Your sign-in is passed in the environment, the
same way it is read from your install; no token is copied to disk. Ctrl-C stops it and removes the copy.

Usage:
  python3 start_brainstem.py                      # ~/.brainstem/src/rapp_brainstem, port 7098
  python3 start_brainstem.py --port 7099 --agents tasks/long-session/arms/agentpy --tap tap/bs.jsonl
  python3 start_brainstem.py --add-agents         # keep the Brainstem's own agents and add the bench's
"""
import argparse, json, os, shutil, signal, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = (".copilot_token", ".copilot_session", ".brainstem_secret", ".env", ".brainstem_data", ".git",
        "venv", ".venv", "__pycache__", "*.pyc", "node_modules", "tests", "logs")


def sign_in(kernel):
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        return json.load(open(os.path.join(kernel, ".copilot_token"))).get("access_token", "")
    except (OSError, ValueError):
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kernel", default=os.path.expanduser("~/.brainstem/src/rapp_brainstem"), help="your installed Brainstem folder")
    ap.add_argument("--python", default=os.path.expanduser("~/.brainstem/venv/bin/python"), help="the Python your Brainstem runs on")
    ap.add_argument("--port", type=int, default=7098)
    ap.add_argument("--agents", default=os.path.join(HERE, "tasks", "long-session", "arms", "agentpy"))
    ap.add_argument("--add-agents", action="store_true", help="load the Brainstem's own agents too, plus the bench's")
    ap.add_argument("--tap", default=os.path.join(HERE, "tap", "bs.jsonl"), help="where token usage is logged")
    a = ap.parse_args()

    if not os.path.isfile(os.path.join(a.kernel, "brainstem.py")):
        sys.exit(f"No Brainstem at {a.kernel}. Install one first: curl -fsSL https://kody-w.github.io/rapp-installer/install.sh | bash")
    token = sign_in(a.kernel)
    if not token:
        sys.exit("Your Brainstem is not signed in. Open it once and sign in, or set GITHUB_TOKEN.")
    python = a.python if os.path.exists(a.python) else sys.executable

    work = tempfile.mkdtemp(prefix="token-bench-brainstem-")
    kernel = os.path.join(work, "rapp_brainstem")
    shutil.copytree(a.kernel, kernel, ignore=shutil.ignore_patterns(*SKIP))
    agents = os.path.abspath(a.agents)
    if a.add_agents:  # the Brainstem's own agents plus the bench's, in the copy
        for name in os.listdir(agents):
            if name.endswith("_agent.py"):
                shutil.copy(os.path.join(agents, name), os.path.join(kernel, "agents", name))
        agents = os.path.join(kernel, "agents")
    tap = os.path.abspath(a.tap)
    os.makedirs(os.path.dirname(tap), exist_ok=True)
    env = dict(os.environ, PORT=str(a.port), AGENTS_PATH=agents, GITHUB_TOKEN=token, TB_TAP_LOG=tap,
               PYTHONPATH=os.pathsep.join(p for p in (os.path.join(HERE, "tap"), os.environ.get("PYTHONPATH", "")) if p))
    log = open(os.path.join(work, "server.log"), "w")
    proc = subprocess.Popen([python, "brainstem.py"], cwd=kernel, env=env, stdout=log, stderr=subprocess.STDOUT)

    def stop(*_):
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    url = f"http://127.0.0.1:{a.port}"
    for _ in range(60):
        if proc.poll() is not None:
            log.flush()
            sys.exit("The Brainstem stopped while starting:\n" + open(os.path.join(work, "server.log")).read()[-2000:])
        try:
            health = json.load(urllib.request.urlopen(url + "/health", timeout=2))
            break
        except Exception:
            time.sleep(1)
    else:
        stop()
    print(f"Measured Brainstem at {url}")
    print(f"  agents: {', '.join(health.get('agents', []))}")
    print(f"  model:  {health.get('model')}")
    print(f"  tokens: {tap}")
    print(f"Run the bench with --bs-url {url} --bs-tap {tap}. Ctrl-C to stop.", flush=True)
    proc.wait()
    stop()


if __name__ == "__main__":
    main()
