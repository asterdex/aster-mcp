# Aster MCP External Integration Guide

> For third-party or internal AI clients (Cursor, Claude, LangChain, etc.) integrating with the Aster MCP service.

---
## 1. Overview

**Aster MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes Aster **Futures** and **Spot** APIs as a set of MCP tools for AI agents to call. Clients connect to this service via an MCP client to access market data, place/cancel orders, and query positions/balances without calling Aster REST APIs directly.

- **Protocol**: MCP (implemented with FastMCP; transport options below).
- **Compatible with**: Claude, Cursor, LangChain, CrewAI, AutoGen, and other MCP-capable AI frameworks.
- **Security**: API keys are stored only on the machine running Aster MCP, with encryption; communication between the MCP client and Aster MCP is local or on a controlled network.
- **API reference**: [aster-finance-futures-api](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api_CN.md), [aster-finance-futures-api-v3](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md) (V3 key signing), [aster-finance-spot-api](https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md).

---
## 2. Installation and Running

### 2.1 Installation

```bash
# Install from source (recommended)
pip install git+https://github.com/asterdex/aster-mcp.git

# Or clone and install locally
git clone https://github.com/asterdex/aster-mcp.git && cd aster-mcp
pip install -e .
```

### 2.2 Account Configuration

```bash
# Interactive config (default HMAC; prompts for API Key, Secret, account ID, etc.)
aster-mcp config

# Config for a specific account ID
aster-mcp config --account-id main

# Config for V3 key-signing account (EIP-712, for /fapi/v3)
aster-mcp config --account-id main --auth-type v3
```

**Auth types**:
- **HMAC** (default): API Key + API Secret; used for `/fapi/v1`, `/fapi/v2`.
- **V3 key signing**: User (main wallet address) + Signer (API wallet address) + Private Key (signer private key), EIP-712 signing; used for `/fapi/v3`. Requires `eth-account`.

Config is written to `~/.config/aster-mcp/config.json`; keys are encrypted with Fernet. Do not expose `.key` or decrypted config.

### 2.3 Start the Service

```bash
# Foreground (default 127.0.0.1:9002)
aster-mcp start

# Custom port and host
aster-mcp start --port 9002 --host 0.0.0.0

# Background
aster-mcp start -d
```

Default port is **9002**. Other commands: `aster-mcp stop`, `aster-mcp status`, `aster-mcp list`, `aster-mcp test <account_id>`.

---
## 3. Integration with Cursor / Claude

### 3.1 Cursor

1. Ensure Aster MCP is running via `aster-mcp start` (or a method Cursor can invoke).
2. Add the Aster MCP server in Cursor’s MCP configuration (see Cursor docs for the exact path), e.g.:
   - If Cursor uses **stdio**: configure a subprocess that runs `python -m aster_mcp.simple_server` in an environment where `aster_mcp` is installed.
   - If Cursor uses **HTTP/SSE**: set the server URL to `http://127.0.0.1:9002` (requires Aster MCP to support and enable that transport).
3. Save and restart or refresh MCP; you can then use natural language in chat (e.g. “get Aster market”, “place an Aster order”) and the AI will call the corresponding MCP tools.

### 3.2 Claude (or other MCP clients)

- Use the official or community MCP client to connect to the local Aster MCP process (stdio or HTTP, depending on implementation).
- Tool list and parameters are returned via MCP; pass required parameters such as `account_id`, `symbol`, etc. when calling.

---
## 4. Tool List and Parameter Summary

The following is the current tool set; the authoritative list is from `get_server_info` or MCP `tools/list`.

### 4.1 Futures – Market Data (no account_id)

| Tool            | Description              | Main parameters                          |
|-----------------|--------------------------|------------------------------------------|
| get_ticker      | 24h ticker / last price  | symbol (e.g. BTCUSDT)                    |
| get_order_book  | Order book               | symbol, limit (optional)                  |
| get_klines      | Candlestick data         | symbol, interval, limit (opt), since (opt)|
| get_funding_rate| Funding rate / mark price | symbol (optional)                        |
| get_funding_info| Funding rate config      | symbol (optional)                        |
| get_exchange_info| Exchange / contract info | none or symbol (optional)                 |
| ping            | Connectivity check       | none                                     |

### 4.2 Futures – Account and Positions (account_id required)

| Tool            | Description        | Main parameters     |
|-----------------|--------------------|---------------------|
| get_balance     | Account balance    | account_id          |
| get_positions   | Position risk      | account_id, symbol (opt) |
| get_account_info| Account info       | account_id          |
| get_account_v4  | Account info V4    | account_id          |

### 4.3 Futures – Orders and Trades (account_id required)

| Tool             | Description           | Main parameters |
|------------------|-----------------------|-----------------|
| create_order     | Place order           | account_id, symbol, side, type, quantity, price (opt), stop_price (opt), etc. |
| cancel_order     | Cancel order          | account_id, symbol, order_id (or orig_client_order_id) |
| cancel_all_orders| Cancel all open orders for a symbol | account_id, symbol |
| get_order        | Get single order      | account_id, symbol, order_id (or orig_client_order_id) |
| get_open_orders  | Open orders           | account_id, symbol (optional) |
| get_all_orders   | Order history         | account_id, symbol, limit (opt) |
| get_my_trades    | Trade history         | account_id, symbol, limit (opt), start_time/end_time (opt) |

### 4.4 Futures – Leverage, Transfers, Income (account_id required)

| Tool                 | Description           | Main parameters |
|----------------------|-----------------------|-----------------|
| set_leverage         | Set leverage          | account_id, symbol, leverage |
| set_margin_mode      | Set margin mode       | account_id, symbol, margin_mode (ISOLATED/CROSSED) |
| transfer_funds       | Transfer to/from futures | account_id, asset, amount, type (1: spot→futures, 2: futures→spot) |
| get_income           | PnL / fund flow      | account_id, symbol (opt), income_type (opt), limit, etc. |
| get_commission_rate  | User commission rate  | account_id, symbol |
| get_leverage_bracket | Leverage bracket      | account_id, symbol (optional) |

### 4.5 Spot – Market Data (no account_id)

| Tool                   | Description        | Main parameters                |
|------------------------|--------------------|--------------------------------|
| get_spot_ticker        | Spot 24h ticker     | symbol                         |
| get_spot_price         | Spot last price     | symbol (optional)              |
| get_spot_order_book    | Spot order book     | symbol, limit (optional)       |
| get_spot_klines        | Spot candlesticks  | symbol, interval, limit (opt), since (opt) |
| get_spot_exchange_info | Spot trading rules | symbol (optional)              |

### 4.6 Spot – Account and Orders (account_id required)

| Tool                      | Description              | Main parameters |
|---------------------------|--------------------------|-----------------|
| get_spot_account          | Spot account info        | account_id      |
| create_spot_order         | Place spot order         | account_id, symbol, side, type, quantity or quote_order_qty, price, etc. |
| cancel_spot_order         | Cancel spot order        | account_id, symbol, order_id (or orig_client_order_id) |
| cancel_spot_all_orders    | Cancel all spot orders for symbol | account_id, symbol |
| get_spot_order            | Get single spot order    | account_id, symbol, order_id (or orig_client_order_id) |
| get_spot_open_orders      | Spot open orders         | account_id, symbol (optional) |
| get_spot_all_orders       | Spot order history       | account_id, symbol, limit, etc. |
| get_spot_my_trades        | Spot trade history       | account_id, symbol (opt), limit, etc. |
| get_spot_transaction_history | Spot transaction history | account_id, asset (opt), type (opt), etc. |
| get_spot_commission_rate  | Spot symbol commission   | account_id, symbol |
| transfer_spot_futures      | Spot ↔ futures transfer  | account_id, asset, amount, kindType (SPOT_FUTURE/FUTURE_SPOT) |

### 4.7 System

| Tool            | Description                                      | Main parameters |
|-----------------|--------------------------------------------------|-----------------|
| get_server_info | MCP server info, configured accounts, tools, markets | none            |

- **account_id**: The identifier set in `aster-mcp config`. HMAC accounts map 1:1 to API keys in the Aster backend. V3 accounts map to user/signer; futures and spot share the same API key (V3 supports futures only; spot requires an HMAC account).
- **symbol**: Aster uses no-slash format (e.g. BTCUSDT). Some tools accept BTC/USDT; the server normalizes internally.

---
## 5. LangChain / LangGraph Integration

To use Aster MCP tools in LangChain/LangGraph, load tools via an MCP adapter and attach them to your agent, for example:

```python
# Example: load tools via MCP adapter (package names may vary)
from mcp_langchain import MCPToolkit  # or langchain_community, etc.

toolkit = MCPToolkit(
    server_command="python",
    server_args=["-m", "aster_mcp.simple_server"],
    server_env={}
)
aster_tools = toolkit.get_tools()

# Add aster_tools to the agent's tools list
# llm_with_tools = llm.bind_tools(aster_tools)
```

Ensure the current Python environment has `aster-mcp` installed and at least one account configured with `aster-mcp config`.

---
## 6. Errors and Rate Limits

- **Auth failure**: Check that account_id is configured, API Key/Secret are correct, and read/trade permissions are enabled.
- **Network/timeout**: Check connectivity to `fapi.asterdex.com` and Aster service status; use `ping` or `get_server_info` to verify.
- **Business errors**: For place/cancel order, change leverage, etc., 4xx/5xx or business error codes are returned by MCP to the caller; handle via the message or user flow.
- **Rate limits**: Follow Aster’s official API limits; MCP does not add extra throttling; control call frequency on the agent side.

---
## 7. Version and Support

- **Current version**: See `aster-mcp --version` or `get_server_info` response.
- **Protocol**: MCP follows [modelcontextprotocol.io](https://modelcontextprotocol.io/); the server will follow FastMCP and community updates as the protocol evolves.
- **Feedback**: Via the project repository Issues or internal channels.

---
## 8. References

- This repo’s README.md (installation and quick start)
- Aster Futures API: `https://fapi.asterdex.com` — [aster-finance-futures-api](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api_CN.md)
- Aster Futures API V3 (key signing): [aster-finance-futures-api-v3](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md)
- Aster Spot API: `https://sapi.asterdex.com` — [aster-finance-spot-api](https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md)
