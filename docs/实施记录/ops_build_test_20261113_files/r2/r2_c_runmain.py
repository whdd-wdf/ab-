def run_compliance(order, base):
    checks = []
    reasons = []
    line = line_of_order(order)
    if line == "A" and order.get("code") in A_CODES:
        check_a(order, base, checks, reasons)
    else:
        check_b(order, base, checks, reasons)
    return (len(reasons) == 0, checks, reasons)


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="/workspace/ab-/virtual")
    parser.add_argument("--order")
    parser.add_argument("--order-file")
    args = parser.parse_args()
    base = args.base
    try:
        if args.order:
            order = json.loads(args.order)
        elif args.order_file:
            with open(args.order_file, 'r') as f:
                order = json.load(f)
        else:
            order = json.loads(sys.stdin.read())
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    passed, checks, reasons = run_compliance(order, base)
    print(json.dumps({"ok": True, "passed": passed, "checks": checks, "reasons": reasons}, ensure_ascii=False))
    sys.exit(0 if passed else 1)

