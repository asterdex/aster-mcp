# Aster MCP 外部对接文档

> 面向第三方或内部 AI 客户端（Cursor、Claude、LangChain 等）对接 Aster MCP 服务的说明。

---
## 1. 概述

**Aster MCP** 是基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的服务器，将 Aster **期货 (Futures)** 与 **现货 (Spot)** API 封装为一组 MCP 工具，供 AI Agent 调用。对接方通过 MCP 客户端连接本服务，即可实现行情查询、下单、撤单、查持仓/余额等能力，而无需直接调用 Aster REST API。

- **协议**：MCP（当前实现为 FastMCP，传输方式见下）。
- **适用**：Claude、Cursor、LangChain、CrewAI、AutoGen 等支持 MCP 的 AI 框架。
- **安全**：API 密钥仅存于运行 Aster MCP 的机器本地，加密存储；MCP 客户端与 Aster MCP 之间为本地或受控网络通信。
- **API 参考**：[aster-finance-futures-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api_CN.md)、[aster-finance-futures-api-v3_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md)（V3 密钥签名）、[aster-finance-spot-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md)。

---
## 2. 安装与运行

### 2.1 安装

```bash
# 从源码安装（推荐）
pip install git+https://github.com/asterdex/aster-mcp.git

# 或克隆后本地安装
git clone https://github.com/asterdex/aster-mcp.git && cd aster-mcp
pip install -e .
```

### 2.2 配置账户

```bash
# 交互式配置（默认 HMAC，会提示输入 API Key、Secret、账户 ID 等）
aster-mcp config

# 指定账户 ID 配置
aster-mcp config --account-id main

# 配置 V3 密钥签名账户（EIP-712，对接专业 API /fapi/v3）
aster-mcp config --account-id main --auth-type v3
```

**鉴权方式**：
- **HMAC**（默认）：API Key + API Secret，对接 `/fapi/v1`、`/fapi/v2`。
- **V3 密钥签名**：User（主账户钱包地址）+ Signer（API 钱包地址）+ Private Key（signer 私钥），EIP-712 签名，对接 `/fapi/v3`。需安装 `eth-account`。

配置写入 `~/.config/aster-mcp/config.json`，密钥经 Fernet 加密；切勿将 `.key` 或含解密后密钥的配置外泄。

### 2.3 启动服务

```bash
# 前台运行（默认 127.0.0.1:9002）
aster-mcp start

# 指定端口与网卡
aster-mcp start --port 9002 --host 0.0.0.0

# 后台运行
aster-mcp start -d
```

默认端口为 **9002**。其他常用命令：`aster-mcp stop`、`aster-mcp status`、`aster-mcp list`、`aster-mcp test <account_id>`。

---
## 3. 在 Cursor / Claude 中对接

### 3.1 Cursor

1. 确保 Aster MCP 已通过 `aster-mcp start` 启动（或使用 Cursor 可调用的启动方式）。
2. 在 Cursor 的 MCP 配置中增加 Aster MCP 服务器（具体配置路径以 Cursor 文档为准），例如：
   - 若 Cursor 使用 **stdio**：配置为通过子进程启动 `python -m aster_mcp.simple_server`，工作目录为已安装 `aster_mcp` 的环境。
   - 若 Cursor 使用 **HTTP/SSE**：配置服务器 URL 为 `http://127.0.0.1:9002`（需 Aster MCP 支持并开启该传输）。
3. 保存后重启或刷新 MCP，即可在对话中通过自然语言使用“查 Aster 行情”“用 Aster 下单”等，由 AI 调用对应 MCP 工具。

### 3.2 Claude（或其他 MCP 客户端）

- 使用官方或社区 MCP 客户端连接本机 Aster MCP 进程（stdio 或 HTTP，依实现而定）。
- 工具列表与参数以 MCP 协议返回；调用时传入 `account_id`、`symbol` 等必填参数即可。

---
## 4. 工具列表与参数摘要

以下为当前规划的工具集，实际以运行 `get_server_info` 或 MCP 的 `tools/list` 为准。

### 4.1 期货 - 市场数据（无需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| get_ticker | 24h 行情/最新价 | symbol（如 BTCUSDT） |
| get_order_book | 订单簿 | symbol, limit（可选） |
| get_klines | K 线 | symbol, interval, limit（可选）, since（可选） |
| get_funding_rate | 资金费率/标记价 | symbol（可选） |
| get_funding_info | 资金费率配置 | symbol（可选） |
| get_exchange_info | 交易所/合约信息 | 无或 symbol（可选） |
| ping | 连通性检测 | 无 |

### 4.2 期货 - 账户与持仓（需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| get_balance | 账户余额 | account_id |
| get_positions | 持仓风险 | account_id, symbol（可选） |
| get_account_info | 账户信息 | account_id |
| get_account_v4 | 账户信息 V4（更完整） | account_id |

### 4.3 期货 - 订单与成交（需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| create_order | 下单 | account_id, symbol, side, type, quantity, price（可选）, stop_price（可选）等 |
| cancel_order | 撤单 | account_id, symbol, order_id（或 orig_client_order_id） |
| cancel_all_orders | 撤销某合约全部挂单 | account_id, symbol |
| get_order | 查询单笔订单 | account_id, symbol, order_id（或 orig_client_order_id） |
| get_open_orders | 当前挂单 | account_id, symbol（可选） |
| get_all_orders | 历史订单 | account_id, symbol, limit（可选） |
| get_my_trades | 成交记录 | account_id, symbol, limit（可选）, start_time/end_time（可选） |

### 4.4 期货 - 杠杆、资金流水与划转（需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| set_leverage | 设置杠杆 | account_id, symbol, leverage |
| set_margin_mode | 设置保证金模式 | account_id, symbol, margin_mode（ISOLATED/CROSSED） |
| transfer_funds | 期货账户划转 | account_id, asset, amount, type（1: 现货→期货, 2: 期货→现货） |
| get_income | 账户损益资金流水 | account_id, symbol（可选）, income_type（可选）, limit 等 |
| get_commission_rate | 用户手续费率 | account_id, symbol |
| get_leverage_bracket | 杠杆分层标准 | account_id, symbol（可选） |

### 4.5 现货 - 市场数据（无需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| get_spot_ticker | 现货 24h 行情 | symbol |
| get_spot_price | 现货最新价格 | symbol（可选） |
| get_spot_order_book | 现货订单簿 | symbol, limit（可选） |
| get_spot_klines | 现货 K 线 | symbol, interval, limit（可选）, since（可选） |
| get_spot_exchange_info | 现货交易规则 | symbol（可选） |

### 4.6 现货 - 账户与订单（需 account_id）

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| get_spot_account | 现货账户信息 | account_id |
| create_spot_order | 现货下单 | account_id, symbol, side, type, quantity 或 quote_order_qty, price 等 |
| cancel_spot_order | 现货撤单 | account_id, symbol, order_id（或 orig_client_order_id） |
| cancel_spot_all_orders | 现货撤销某交易对全部挂单 | account_id, symbol |
| get_spot_order | 现货查询单笔订单 | account_id, symbol, order_id（或 orig_client_order_id） |
| get_spot_open_orders | 现货当前挂单 | account_id, symbol（可选） |
| get_spot_all_orders | 现货历史订单 | account_id, symbol, limit 等 |
| get_spot_my_trades | 现货成交记录 | account_id, symbol（可选）, limit 等 |
| get_spot_transaction_history | 现货交易流水 | account_id, asset（可选）, type（可选） 等 |
| get_spot_commission_rate | 现货 Symbol 手续费率 | account_id, symbol |
| transfer_spot_futures | 现货与期货划转 | account_id, asset, amount, kindType（SPOT_FUTURE/FUTURE_SPOT） |

### 4.7 系统

| 工具名 | 说明 | 主要参数 |
|--------|------|----------|
| get_server_info | MCP 服务信息、已配置账户数、工具列表、支持市场 | 无 |

- **account_id**：为在 `aster-mcp config` 时填写的账户标识。HMAC 账户与 Aster 后台的 API Key 一一对应。V3 账户与 user/signer 对应，期货与现货共用同一 API Key（V3 账户仅支持期货，现货需 HMAC 账户）。
- **symbol**：Aster 使用无斜杠格式（如 BTCUSDT）；部分工具可接受 BTC/USDT，服务内部会统一转换。

---
## 5. 与 LangChain / LangGraph 集成

若需将 Aster MCP 工具接入 LangChain/LangGraph，可通过 MCP 适配器加载工具后绑定到 Agent，例如：

```python
# 示例：通过 MCP 适配器获取工具（具体包名以生态为准）
from mcp_langchain import MCPToolkit  # 或 langchain_community 等

toolkit = MCPToolkit(
    server_command="python",
    server_args=["-m", "aster_mcp.simple_server"],
    server_env={}
)
aster_tools = toolkit.get_tools()

# 将 aster_tools 加入 Agent 的 tools 列表
# llm_with_tools = llm.bind_tools(aster_tools)
```

运行前请确保当前 Python 环境已安装 `aster-mcp` 且已执行 `aster-mcp config` 配置至少一个账户。

---
## 6. 错误与限流

- **认证失败**：检查 account_id 是否已配置、API Key/Secret 是否正确、是否已启用交易/读取权限。
- **网络/超时**：检查本机到 `fapi.asterdex.com` 的网络及 Aster 服务状态；可先调用 `ping` 或 `get_server_info` 自检。
- **业务错误**：下单、撤单、改杠杆等若返回 4xx/5xx 或业务错误码，MCP 会将错误信息返回给调用方，由 AI 或用户根据文案处理。
- **限流**：遵守 Aster 官方 API 限流；MCP 层不额外做聚合限流，建议 Agent 侧控制调用频率。

---
## 7. 版本与支持

- **当前版本**：以 `aster-mcp --version` 或 `get_server_info` 返回为准。
- **协议版本**：MCP 协议遵循 [modelcontextprotocol.io](https://modelcontextprotocol.io/)；若协议升级，本服务会随 FastMCP 及社区实践更新。
- **问题反馈**：通过项目仓库 Issue 或内部渠道反馈。

---
## 8. 参考

- 本仓库 README.md（安装与快速开始）
- Aster 期货 API：`https://fapi.asterdex.com` — [aster-finance-futures-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api_CN.md)
- Aster 期货 API V3（密钥签名）：[aster-finance-futures-api-v3_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md)
- Aster 现货 API：`https://sapi.asterdex.com` — [aster-finance-spot-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md)
