# Aster MCP Server

基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的 **Aster 期货 + 现货** MCP 服务，让 AI Agent（如 Cursor、Claude、LangChain）能够安全地查询行情、下单、查持仓与账户。

## 功能概览

- **配置与安全**：多账户、本地 Fernet 加密存储 API 密钥（`~/.config/aster-mcp/`）
- **鉴权方式**：支持 **HMAC**（API Key/Secret）与 **V3 密钥签名**（EIP-712，user/signer/private_key，对接 [aster-finance-futures-api-v3](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md)）
- **MCP 工具**：
  - **期货 (Futures)**：行情、账户/持仓、下单/撤单、杠杆与保证金、资金划转、资金流水、手续费率、杠杆分层
  - **现货 (Spot)**：行情、账户、下单/撤单、成交记录、交易流水、手续费率、期货现货划转
- **CLI**：`config` / `list` / `start` / `stop` / `status` / `test` / `backup`

## 安装

```bash
pip install -e .
# 或
pip install git+https://github.com/<org>/aster-mcp.git
```

## 快速开始

```bash
# 1. 配置账户（交互式，默认 HMAC）
aster-mcp config

# 配置 V3 密钥签名账户（EIP-712）
aster-mcp config --account-id main --auth-type v3

# 2. 列出账户
aster-mcp list

# 3. 启动 MCP 服务（默认 stdio，供 Cursor/Claude 等调用）
aster-mcp start

# 4. 测试连接
aster-mcp test main
```

## 在 Cursor 中使用

1. 确保已 `aster-mcp config` 配置至少一个账户。
2. 在 Cursor 的 MCP 设置中添加 Aster MCP，命令示例：
   - `python -m aster_mcp.simple_server`（工作目录与 Python 环境需已安装 `aster_mcp`）。
3. 对话中即可通过自然语言使用「查 Aster BTC 价格」「用 Aster 账户下单」等。

## 工具列表（摘要）

| 类别     | 期货工具 | 现货工具 |
|----------|----------|----------|
| 市场数据 | `get_ticker`, `get_order_book`, `get_klines`, `get_funding_rate`, `get_funding_info`, `get_exchange_info`, `ping` | `get_spot_ticker`, `get_spot_price`, `get_spot_order_book`, `get_spot_klines`, `get_spot_exchange_info` |
| 账户     | `get_balance`, `get_positions`, `get_account_info`, `get_account_v4` | `get_spot_account` |
| 订单     | `create_order`, `cancel_order`, `cancel_all_orders`, `get_order`, `get_open_orders`, `get_all_orders`, `get_my_trades` | `create_spot_order`, `cancel_spot_order`, `cancel_spot_all_orders`, `get_spot_order`, `get_spot_open_orders`, `get_spot_all_orders`, `get_spot_my_trades` |
| 设置/其他 | `set_leverage`, `set_margin_mode`, `transfer_funds`, `get_income`, `get_commission_rate`, `get_leverage_bracket` | `get_spot_transaction_history`, `get_spot_commission_rate`, `transfer_spot_futures` |
| 系统     | `get_server_info` | |

详细参数与对接说明见 [Aster-MCP 外部对接文档](docs/Aster-MCP外部对接文档.md)。

## 项目结构

```
aster-mcp/
├── aster_mcp/
│   ├── __init__.py
│   ├── config.py       # 配置与加密
│   ├── client.py       # Aster FAPI 客户端（期货，HMAC）
│   ├── v3_client.py    # Aster FAPI v3 客户端（EIP-712 密钥签名）
│   ├── spot_client.py  # Aster SAPI 客户端（现货）
│   ├── tools.py        # MCP 工具实现
│   ├── simple_server.py
│   └── cli.py
├── docs/
│   └── Aster-MCP外部对接文档.md
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 与 Aster API 关系

- 本仓库内置 **Aster FAPI 客户端**（`client.py`，期货）与 **SAPI 客户端**（`spot_client.py`，现货）。
- **鉴权方式**：
  - **HMAC**：使用 API Key/Secret，对接 `/fapi/v1`、`/fapi/v2` 等。
  - **V3 密钥签名**：使用 user（主账户钱包）、signer（API 钱包）、private_key（signer 私钥），EIP-712 签名，对接 `/fapi/v3`。需安装 `eth-account`。
- 期货 Base URL：`https://fapi.asterdex.com`；现货 Base URL：`https://sapi.asterdex.com`，可在配置中按账户覆盖。
- API 文档参考：[aster-finance-futures-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api_CN.md)、[aster-finance-futures-api-v3_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md)、[aster-finance-spot-api_CN](https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md)。

## 风险与合规

- 期货交易有风险，请先在测试环境验证。
- API 密钥仅本地加密存储，勿泄露或上传。
- 请遵守当地法规与 Aster 平台条款。

## 许可证

MIT
