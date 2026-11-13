def move_order(base, src_name, dest_dir, result):
    src_path = os.path.join(base, 'order_queue', 'pending', src_name)
    dest_path = os.path.join(base, 'order_queue', dest_dir, src_name)
    with open(src_path, 'r', encoding='utf-8') as f:
        order_json = json.load(f)
    order_json['result'] = result
    with open(dest_path, 'w', encoding='utf-8') as f:
        json.dump(order_json, f, ensure_ascii=False)
    os.remove(src_path)