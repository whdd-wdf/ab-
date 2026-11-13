def find_node_for_sell(code, sell_price, nodes):
    tick = tick_of(code)
    for node in nodes:
        node_price = node["node_price"]
        if round_tick(node_price * 1.02, tick) == round_tick(sell_price, tick):
            return node_price
    return None
