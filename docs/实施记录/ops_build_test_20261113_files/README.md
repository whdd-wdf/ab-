# ~/ops-build/ 搭建说明

## 读了哪些文档、按什么顺序

1. **接口规范**（docs/操作与管控接口规范.md）：
   - 读取了文档的总览部分。
   - 详细阅读了总览与两线分工部分。
   - 阅读了四份实施记录（p1_gate_20261113.md、p1_bintraday_switch_check_20261113.md、p1_fillwatch_20261113.md、p1_bookkeeping_20261113.md）。
   - 阅读了虚拟程序的 README.md 与 virtual/virtual_ops.py 的常量区。

2. **虚拟程序**（virtual/README.md）与**虚拟程序**（virtual/virtual_ops.py）：
   - 详细阅读了虚拟程序的常量区，以了解节点账本与 quota 的精确 JSON 字段名。
   - 详细阅读了虚拟程序的接口事实，包括文件清单、订单 JSON 格式、check 算数接口、虚拟成交与记账口径。

## 四个脚本每步的依据是接口文档哪一节

1. **order_compliance.py**：
   - 对应 §1.5，用于订单合规校验。
   - 对应 §5.2，用于订单执行。

2. **order_executor.py**：
   - 对应 §1.4，用于订单执行。
   - 对应 §5.2，用于订单执行。

3. **gate_local.py**：
   - 对应 §5，用于门控管理。

4. **fillwatch_rehang.py**：
   - 对应 §4.4，用于补挂计算。
   - 对应 §4.5，用于补挂计算。

## 哪些地方文档不够用

1. 节点账本与 quota 的精确 JSON 字段名在接口文档里没有，只能从 virtual/nodes.json 与 virtual_quota.json 看到。
2. 成交入账时 quota/持仓/节点的更新公式在接口文档里没有，抄了 virtual_ops.py 的做法。
3. 交易日判定在虚拟环境里没有新浪日历，只能用周一至五兜底。
4. B 线卖出补挂等细节在接口文档里没有，需要从虚拟程序里提取。
5. 订单队列的命名规则在接口文档里没有，需要从虚拟程序里提取。
6. 订单 JSON 格式中的某些字段名在接口文档里没有，需要从虚拟程序里提取。
7. 订单状态流转的某些细节在接口文档里没有，需要从虚拟程序里提取。
8. 虚拟成交与记账口径在接口文档里没有，需要从虚拟程序里提取。

## 每个脚本的用法与自测方法

1. **order_compliance.py**：
   - 使用命令：`python order_compliance.py --order_file /root/monitor/order_queue/pending/1.json`
   - 自测方法：检查输出结果是否符合预期。

2. **order_executor.py**：
   - 使用命令：`python order_executor.py --order_file /root/monitor/order_queue/pending/1.json`
   - 自测方法：检查输出结果是否符合预期。

3. **gate_local.py**：
   - 使用命令：`python gate_local.py --gate_file /root/monitor/order_queue/failed/1.json`
   - 自测方法：检查输出结果是否符合预期。

4. **fillwatch_rehang.py**：
   - 使用命令：`python fillwatch_rehang.py --fill_file /root/monitor/order