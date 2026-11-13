import csv
import re

def is_fill(row):
    remark = str(row.get("备注", ""))
    if "委托中" in remark:
        return False
    idx = remark.find("\u3011")
    if idx < 0:
        return True
    after = remark[idx + 1:].strip()
    if after.startswith("已撤销"):
        return False
    return True

def read_trade_log_fills(base):
    fills = set()
    try:
        with open(base + "/virtual_trade_log.csv", mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("方向") not in ["买入", "卖出"]:
                    continue
                if not is_fill(row):
                    continue
                remark = str(row.get("备注", ""))
                m = re.search(r"委托价?(\d+\.\d+)", remark)
                if m:
                    price = float(m.group(1))
                else:
                    price = float(row.get("价格", 0))
                key = (str(row.get("日期", "")), str(row.get("代码", "")), str(row.get("方向", "")), int(float(row.get("数量", 0))), price)
                fills.add(key)
    except FileNotFoundError:
        return set()
    return fills
