"""Runs ONE generated build123d script. Invoked as: runner.py code.py outdir
Defense in depth: AST allowlist + restricted builtins + rlimits. The real
boundary must be the container/VM (no network, read-only fs, non-root)."""
import ast, sys, os, json, resource, math

ALLOWED_IMPORTS = {"build123d", "math"}
BANNED_NAMES = {"open","exec","eval","compile","__import__","input","globals","locals",
                "vars","getattr","setattr","delattr","breakpoint","memoryview","exit","quit"}

def check(src):
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS: raise ValueError(f"import not allowed: {a.name}")
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in ALLOWED_IMPORTS: raise ValueError(f"import not allowed: {n.module}")
        elif isinstance(n, ast.Attribute) and n.attr.startswith("__"):
            raise ValueError("dunder attribute access not allowed")
        elif isinstance(n, ast.Name) and (n.id in BANNED_NAMES or n.id.startswith("__")):
            raise ValueError(f"name not allowed: {n.id}")
    return tree

def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (3 << 30, 3 << 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (200 << 20, 200 << 20))

def main(code_path=None, out=None):
    if code_path is None:
        code_path, out = sys.argv[1], sys.argv[2]
        limits()
    src = open(code_path).read()
    tree = check(src)
    import build123d as b
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
    def safe_import(name, *a, **k):
        if name.split(".")[0] not in ALLOWED_IMPORTS: raise ImportError(name)
        return real_import(name, *a, **k)
    safe = {k: getattr(__builtins__, k) if not isinstance(__builtins__, dict) else __builtins__[k]
            for k in ("abs","min","max","sum","range","len","enumerate","zip","float","int","str","bool",
                      "list","tuple","dict","set","round","sorted","reversed","map","filter","any","all",
                      "isinstance","print","pow","divmod","True","False","None","Exception","ValueError")}
    safe["__import__"] = safe_import
    g = {"__builtins__": safe, "math": math}
    g.update({k: v for k, v in vars(b).items() if not k.startswith("_")})
    exec(compile(tree, "generated.py", "exec"), g)
    res = g.get("result")
    if res is None: raise ValueError("script must assign the final shape to `result`")
    shape = res.part if hasattr(res, "part") else res
    os.makedirs(out, exist_ok=True)
    b.export_step(shape, os.path.join(out, "model.step"))
    b.export_stl(shape, os.path.join(out, "model.stl"))
    b.export_gltf(shape, os.path.join(out, "model.glb"), binary=True)
    bb = shape.bounding_box()
    return ({"ok": True, "volume": shape.volume,
        "bbox": [bb.size.X, bb.size.Y, bb.size.Z], "solids": len(shape.solids())})

if __name__ == "__main__":
    try: print(json.dumps(main()))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:600]})); sys.exit(1)
