# 华为 VPS 维护手册（海龙虾用）

> 华为 VPS（123.60.222.204，Tailscale 100.74.158.35，主机名 hw-vps）是交易系统的中间站与稳定备份。
> 本手册只讲怎么登录、查什么、红线是什么。交易规则与总纲在文档库，不在这里改。

## 登录方式

```bash
~/hw_ssh.sh root@100.74.158.35 '<命令>'
```

- 脚本在 `~/hw_ssh.sh`，工作目录里也有一份 `./hw_ssh.sh`，两份相同。
- 密钥 `~/.ssh/homeline_agent_ed25519`（600 权限），只认这一把，不用密码。
- 两个通道自动切换：① Tailscale 直连（100.74.158.35）② 公网直连（123.60.222.204:22）。
  只在 ssh 退出码 255（通道故障）时才换通道；远端命令自己的非零退出立即返回、不重试。
- **只认华为**：host 不是 100.74.158.35 / 123.60.222.204 / hw-vps 一律拒绝，别拿它连别的机器。

## 华为上有什么（/root/monitor/）

- `gate_local.py` + `is_trading_day.py`：自备门控。交易日 07:30 开门、17:05 关门，写标志 `/root/monitor/.trading_day`。
- `cofool_fillwatch.py` / `fillwatch_rehang.py`：A 线成交监视（compare 模式，未切 live）。
- `order_executor.py` + `order_queue/`：B 线订单队列执行器（华为版为准）。
- `order_compliance.py`：下单前合规校验。
- `huawei_bookings.csv`：华为记账轻量版（compare 不写，live 才写）。
- 定时器：`gate-local-open.timer` / `gate-local-close.timer`、`cofool-fillwatch.timer`、`cofool-monitor` 两个计时器。

## 日常巡查（只读为主）

```bash
~/hw_ssh.sh root@100.74.158.35 'uptime; df -h / | tail -1; free -m | head -2'
~/hw_ssh.sh root@100.74.158.35 'systemctl list-timers --all | grep -E "gate|fillwatch|monitor"'
~/hw_ssh.sh root@100.74.158.35 'ls -la /root/monitor/.trading_day 2>&1; tail -20 /root/monitor/gate_local.log 2>&1'
~/hw_ssh.sh root@100.74.158.35 'systemctl status cofool-fillwatch.timer --no-pager | head -8'
```

- 门控窗口：交易日 07:30–17:05 才开门；非交易日、关门后定时器 inactive 是正常的，不是故障。
- 日志在 `/root/monitor/` 下（`*.log`），先看日志再动手。

## 红线（用户 2026-11-14 定，不可破）

- **不下单、不改交易规则与总纲、不碰真实资金、不删数据。**
- 涉及规则原则或破坏性操作（删文件、清队列、改配置、重启服务）先问用户。
- 发现问题先定位、再修，修完写进巡查小结；修不好就报用户，别硬撑。
- 每日 17:30 前经飞书发巡查小结给用户。

## 出问题先查什么

1. 通道不通：`tailscale status | grep hw-vps` 看隧道在不在；再试 `~/hw_ssh.sh` 会自动切公网。
2. 门控没开门：查 `gate_local.log` 与 `.trading_day` 标志日期是不是当天。
3. 定时器没跑：`systemctl list-timers` 看下次触发时间，是不是非交易日。
