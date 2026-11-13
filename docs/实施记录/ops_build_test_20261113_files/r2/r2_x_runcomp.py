def run_compliance(order, base, compliance_script):
    import subprocess, json

    cmd = [sys.executable, compliance_script, "--base", base, "--order", json.dumps(order, ensure_ascii=False)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            return (False, [], ["合规脚本退出码 " + str(proc.returncode)])
        try:
            out = json.loads(proc.stdout)
            if not out:
                return (False, [], ["合规输出解析失败"])
            return (bool(out.get("passed", False)), out.get("checks", []), out.get("reasons", []))
        except json.JSONDecodeError:
            return (False, [], ["合规输出解析失败"])
    except subprocess.TimeoutExpired:
        return (False, [], ["合规调用超时"])
    except Exception as e:
        return (False, [], ["合规调用失败： " + str(e)])