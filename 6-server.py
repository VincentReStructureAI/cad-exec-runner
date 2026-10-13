"""Exec service. POST /run {code} -> {ok, volume, bbox, files:{step,stl,glb} as base64}
Auth: header x-exec-secret must equal env EXEC_SECRET. Run in a locked-down container."""
import runner, build123d, http.server, json, os, subprocess, sys, tempfile, base64, hmac
SECRET = os.environ.get("EXEC_SECRET", "")
HERE = os.path.dirname(os.path.abspath(__file__))
def fork_run(cp, out):
    """Fork a child from the warm parent (build123d already imported), run with rlimits, return JSON via pipe."""
    r, w = os.pipe(); pid = os.fork()
    if pid == 0:
        try:
            os.close(r); runner.limits(); os.chdir(os.path.dirname(cp))
            try: res = runner.main(cp, out)
            except Exception as e: res = {"ok": False, "error": f"{type(e).__name__}: {e}"[:600]}
            os.write(w, json.dumps(res).encode())
        finally: os._exit(0)
    os.close(w); chunks = []
    import select, signal, time
    end = time.time() + 45
    while time.time() < end:
        if select.select([r], [], [], 1)[0]:
            b = os.read(r, 65536)
            if not b: break
            chunks.append(b)
    else:
        os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0); os.close(r); return {"ok": False, "error": "timeout"}
    os.waitpid(pid, 0); os.close(r)
    try: return json.loads(b"".join(chunks))
    except Exception: return {"ok": False, "error": "generation crashed"}

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("content-type","application/json"); self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._send(200, {"ok": True})
    def do_POST(self):
        if not SECRET or not hmac.compare_digest(self.headers.get("x-exec-secret",""), SECRET):
            return self._send(401, {"ok": False, "error": "unauthorized"})
        n = int(self.headers.get("content-length","0"))
        if n > 50_000: return self._send(413, {"ok": False, "error": "code too large"})
        code = json.loads(self.rfile.read(n)).get("code","")
        with tempfile.TemporaryDirectory() as d:
            cp = os.path.join(d,"code.py"); open(cp,"w").write(code)
            res = fork_run(cp, os.path.join(d,"out"))
            if res.get("ok"):
                res["files"] = {e: base64.b64encode(open(os.path.join(d,"out","model."+e),"rb").read()).decode() for e in ("step","stl","glb")}
            self._send(200, res)
    def log_message(self,*a): pass
if __name__ == "__main__":
    http.server.HTTPServer((os.environ.get("HOST","127.0.0.1"), int(os.environ.get("PORT","8787"))), H).serve_forever()
