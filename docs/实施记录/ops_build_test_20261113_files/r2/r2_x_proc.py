def process_one(src_path, base, compliance_script):
    order = load_json(src_path, None)
    if order is None:
        return {"kind": "rejected", "order_id": os.path.basename(src_path), "reasons": ["订单文件解析失败"]}
    
    if "order_id" not in order:
        order["order_id"] = os.path.splitext(os.path.basename(src_path))[0]
    
    if "time" not in order:
        order["time"] = now_str()
    
    passed, checks, reasons = run_compliance(order, base, compliance_script)
    
    if passed:
        result = apply_fill(order, base)
        return move_order(src_path, base, "done", result)
    else:
        result = {
            "kind": "rejected",
            "order_id": order["order_id"],
            "code": order.get("code"),
            "side": order.get("side"),
            "price": order.get("price"),
            "qty": order.get("qty"),
            "checks": checks,
            "reasons": reasons
        }
        return move_order(src_path, base, "failed", result)
