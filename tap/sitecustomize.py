# Token tap: loaded via PYTHONPATH into a throwaway brainstem. Logs `usage` from every
# chat/completions response to $TB_TAP_LOG. No kernel file is changed.
import json, os, time
_log = os.environ.get("TB_TAP_LOG")
if _log:
    try:
        import requests
        _orig = requests.Session.request
        def _tapped(self, method, url, *a, **kw):
            r = _orig(self, method, url, *a, **kw)
            if "chat/completions" in str(url) and not kw.get("stream"):
                try:
                    u = r.json().get("usage")
                    if u:
                        with open(_log, "a") as f: f.write(json.dumps({"t": time.time(), "usage": u}) + "\n")
                except Exception: pass
            return r
        requests.Session.request = _tapped
    except ImportError: pass
