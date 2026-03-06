"""
Aster MCP 简化服务器

基于 FastMCP 注册工具，工具参数均显式声明（无 **kwargs），便于兼容。
"""

import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from .config import ConfigManager
from .tools import AsterMCPTools

logger = logging.getLogger(__name__)


class SimpleAsterMCPServer:
    """Aster MCP 简化服务器"""

    def __init__(self, port: int = 9002, host: str = "127.0.0.1") -> None:
        self.port = port
        self.host = host
        self.config_manager = ConfigManager()
        self.tools = AsterMCPTools(self.config_manager)
        self.mcp = FastMCP(name="aster-mcp")
        self._register_tools()
        logger.info("Simple Aster MCP Server initialized on %s:%s", host, port)

    def _register_tools(self) -> None:
        t = self.tools

        @self.mcp.tool
        def ping() -> Dict[str, Any]:
            """检测 Aster 服务连通性"""
            return t.ping()

        @self.mcp.tool
        def get_ticker(symbol: str) -> Dict[str, Any]:
            """获取 24h 行情/最新价。symbol 如 BTCUSDT 或 BTC/USDT"""
            return t.get_ticker(symbol)

        @self.mcp.tool
        def get_order_book(symbol: str, limit: int = 100) -> Dict[str, Any]:
            """获取订单簿深度"""
            return t.get_order_book(symbol, limit)

        @self.mcp.tool
        def get_klines(
            symbol: str,
            interval: str = "1h",
            since: Optional[int] = None,
            limit: int = 100,
        ) -> List[List]:
            """获取 K 线。interval 如 1m, 5m, 1h, 4h, 1d"""
            return t.get_klines(symbol, interval, since, limit)

        @self.mcp.tool
        def get_funding_rate(symbol: Optional[str] = None) -> Any:
            """获取资金费率/标记价。symbol 可选"""
            return t.get_funding_rate(symbol)

        @self.mcp.tool
        def get_exchange_info(symbol: Optional[str] = None) -> Dict[str, Any]:
            """获取交易所/合约信息"""
            return t.get_exchange_info(symbol)

        @self.mcp.tool
        def get_balance(account_id: str) -> Dict[str, Any]:
            """查询账户余额"""
            return t.get_balance(account_id)

        @self.mcp.tool
        def get_positions(account_id: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
            """查询持仓。symbol 可选过滤"""
            return t.get_positions(account_id, symbol)

        @self.mcp.tool
        def get_account_info(account_id: str) -> Dict[str, Any]:
            """查询账户信息（含持仓摘要）"""
            return t.get_account_info(account_id)

        @self.mcp.tool
        def get_account_v4(account_id: str) -> Dict[str, Any]:
            """期货账户信息 V4（更完整，含 assets、positions）"""
            return t.get_account_v4(account_id)

        @self.mcp.tool
        def get_funding_info(symbol: Optional[str] = None) -> Any:
            """查询资金费率配置。symbol 可选"""
            return t.get_funding_info(symbol)

        @self.mcp.tool
        def get_income(
            account_id: str,
            symbol: Optional[str] = None,
            income_type: Optional[str] = None,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> Any:
            """期货账户损益资金流水。incomeType: TRANSFER, REALIZED_PNL, FUNDING_FEE, COMMISSION 等"""
            return t.get_income(account_id, symbol, income_type, limit, start_time, end_time)

        @self.mcp.tool
        def get_commission_rate(account_id: str, symbol: str) -> Dict[str, Any]:
            """期货用户手续费率"""
            return t.get_commission_rate(account_id, symbol)

        @self.mcp.tool
        def get_leverage_bracket(account_id: str, symbol: Optional[str] = None) -> Any:
            """期货杠杆分层标准"""
            return t.get_leverage_bracket(account_id, symbol)

        @self.mcp.tool
        def create_order(
            account_id: str,
            symbol: str,
            side: str,
            order_type: str,
            quantity: str,
            price: Optional[float] = None,
            stop_price: Optional[float] = None,
            time_in_force: str = "GTC",
            reduce_only: bool = False,
            dry_run: bool = False,
        ) -> Dict[str, Any]:
            """Create a futures order. WARNING: this places a LIVE order unless dry_run=True.
            order_type: LIMIT, MARKET, STOP, STOP_MARKET, etc.
            quantity: string to preserve decimal precision.
            dry_run: if True, return an order preview without executing."""
            if dry_run:
                return {
                    "dry_run": True,
                    "account_id": account_id,
                    "symbol": symbol,
                    "side": side,
                    "order_type": order_type,
                    "quantity": quantity,
                    "price": price,
                    "stop_price": stop_price,
                    "time_in_force": time_in_force,
                    "reduce_only": reduce_only,
                }
            return t.create_order(
                account_id, symbol, side, order_type, quantity,
                price, stop_price, time_in_force, reduce_only,
            )

        @self.mcp.tool
        def cancel_order(
            account_id: str,
            symbol: str,
            order_id: Optional[int] = None,
            orig_client_order_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """撤销订单。order_id 与 orig_client_order_id 二选一"""
            return t.cancel_order(account_id, symbol, order_id, orig_client_order_id)

        @self.mcp.tool
        def cancel_all_orders(account_id: str, symbol: str) -> Dict[str, Any]:
            """撤销某合约全部挂单"""
            return t.cancel_all_orders(account_id, symbol)

        @self.mcp.tool
        def get_order(
            account_id: str,
            symbol: str,
            order_id: Optional[int] = None,
            orig_client_order_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """查询单笔订单"""
            return t.get_order(account_id, symbol, order_id, orig_client_order_id)

        @self.mcp.tool
        def get_open_orders(account_id: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
            """当前挂单"""
            return t.get_open_orders(account_id, symbol)

        @self.mcp.tool
        def get_all_orders(
            account_id: str,
            symbol: str,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> List[Dict[str, Any]]:
            """历史订单"""
            return t.get_all_orders(account_id, symbol, limit, start_time, end_time)

        @self.mcp.tool
        def get_my_trades(
            account_id: str,
            symbol: str,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> List[Dict[str, Any]]:
            """成交记录"""
            return t.get_my_trades(account_id, symbol, limit, start_time, end_time)

        @self.mcp.tool
        def set_leverage(account_id: str, symbol: str, leverage: int) -> Dict[str, Any]:
            """设置杠杆倍数"""
            return t.set_leverage(account_id, symbol, leverage)

        @self.mcp.tool
        def set_margin_mode(account_id: str, symbol: str, margin_mode: str) -> Dict[str, Any]:
            """设置保证金模式：ISOLATED 或 CROSSED"""
            return t.set_margin_mode(account_id, symbol, margin_mode)

        @self.mcp.tool
        def transfer_funds(
            account_id: str,
            asset: str,
            amount: float,
            transfer_type: int,
        ) -> Dict[str, Any]:
            """期货账户划转。transfer_type: 1=现货→期货, 2=期货→现货"""
            return t.transfer_funds(account_id, asset, amount, transfer_type)

        # ---------- 现货 (Spot) ----------
        @self.mcp.tool
        def get_spot_account(account_id: str) -> Dict[str, Any]:
            """现货账户信息（含 balances: free/locked）"""
            return t.get_spot_account(account_id)

        @self.mcp.tool
        def get_spot_ticker(symbol: str) -> Dict[str, Any]:
            """现货 24h 行情"""
            return t.get_spot_ticker(symbol)

        @self.mcp.tool
        def get_spot_price(symbol: Optional[str] = None) -> Any:
            """现货最新价格"""
            return t.get_spot_price(symbol)

        @self.mcp.tool
        def get_spot_order_book(symbol: str, limit: int = 100) -> Dict[str, Any]:
            """现货订单簿"""
            return t.get_spot_order_book(symbol, limit)

        @self.mcp.tool
        def get_spot_klines(
            symbol: str,
            interval: str = "1h",
            since: Optional[int] = None,
            limit: int = 100,
        ) -> List[List]:
            """现货 K 线"""
            return t.get_spot_klines(symbol, interval, since, limit)

        @self.mcp.tool
        def get_spot_exchange_info(symbol: Optional[str] = None) -> Dict[str, Any]:
            """现货交易规则"""
            return t.get_spot_exchange_info(symbol)

        @self.mcp.tool
        def create_spot_order(
            account_id: str,
            symbol: str,
            side: str,
            order_type: str,
            quantity: Optional[str] = None,
            quote_order_qty: Optional[float] = None,
            price: Optional[float] = None,
            stop_price: Optional[float] = None,
            time_in_force: str = "GTC",
            dry_run: bool = False,
        ) -> Dict[str, Any]:
            """Create a spot order. WARNING: this places a LIVE order unless dry_run=True.
            MARKET buy can use quote_order_qty, otherwise use quantity.
            quantity: string to preserve decimal precision.
            dry_run: if True, return an order preview without executing."""
            if dry_run:
                return {
                    "dry_run": True,
                    "account_id": account_id,
                    "symbol": symbol,
                    "side": side,
                    "order_type": order_type,
                    "quantity": quantity,
                    "quote_order_qty": quote_order_qty,
                    "price": price,
                    "stop_price": stop_price,
                    "time_in_force": time_in_force,
                }
            return t.create_spot_order(
                account_id, symbol, side, order_type,
                quantity, quote_order_qty, price, stop_price, time_in_force,
            )

        @self.mcp.tool
        def cancel_spot_order(
            account_id: str,
            symbol: str,
            order_id: Optional[int] = None,
            orig_client_order_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """现货撤单"""
            return t.cancel_spot_order(account_id, symbol, order_id, orig_client_order_id)

        @self.mcp.tool
        def cancel_spot_all_orders(account_id: str, symbol: str) -> Dict[str, Any]:
            """现货撤销某交易对全部挂单"""
            return t.cancel_spot_all_orders(account_id, symbol)

        @self.mcp.tool
        def get_spot_order(
            account_id: str,
            symbol: str,
            order_id: Optional[int] = None,
            orig_client_order_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """现货查询单笔订单"""
            return t.get_spot_order(account_id, symbol, order_id, orig_client_order_id)

        @self.mcp.tool
        def get_spot_open_orders(
            account_id: str,
            symbol: Optional[str] = None,
        ) -> List[Dict[str, Any]]:
            """现货当前挂单"""
            return t.get_spot_open_orders(account_id, symbol)

        @self.mcp.tool
        def get_spot_all_orders(
            account_id: str,
            symbol: str,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> List[Dict[str, Any]]:
            """现货历史订单"""
            return t.get_spot_all_orders(account_id, symbol, limit, start_time, end_time)

        @self.mcp.tool
        def get_spot_my_trades(
            account_id: str,
            symbol: Optional[str] = None,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> List[Dict[str, Any]]:
            """现货成交记录"""
            return t.get_spot_my_trades(account_id, symbol, limit, start_time, end_time)

        @self.mcp.tool
        def get_spot_transaction_history(
            account_id: str,
            asset: Optional[str] = None,
            type: Optional[str] = None,
            limit: int = 100,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
        ) -> Any:
            """现货交易流水。type: TRADE_TARGET, TRANSFER_SPOT_TO_FUTURE 等"""
            return t.get_spot_transaction_history(
                account_id, asset, type, limit, start_time, end_time
            )

        @self.mcp.tool
        def get_spot_commission_rate(account_id: str, symbol: str) -> Dict[str, Any]:
            """现货 Symbol 手续费率"""
            return t.get_spot_commission_rate(account_id, symbol)

        @self.mcp.tool
        def transfer_spot_futures(
            account_id: str,
            asset: str,
            amount: float,
            kind_type: str,
            client_tran_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """现货与期货划转。kindType: SPOT_FUTURE(现货→期货), FUTURE_SPOT(期货→现货)"""
            return t.transfer_spot_futures(account_id, asset, amount, kind_type, client_tran_id)

        @self.mcp.tool
        def get_server_info() -> Dict[str, Any]:
            """MCP server info: version, configured account count, supported markets."""
            accounts = self.config_manager.list_accounts()
            return {
                "server_name": "aster-mcp",
                "version": "0.1.0",
                "configured_accounts": len(accounts),
                "supported_markets": ["futures", "spot"],
                "total_tools": 44,
            }

    def run(self, transport: str = "stdio") -> None:
        """运行 MCP 服务器。transport: sse(HTTP+SSE, 独立运行) 或 stdio(供 Cursor 子进程)"""
        if transport in ("sse", "http", "streamable-http"):
            logger.info("Starting Aster MCP Server on %s:%s (transport=%s)", self.host, self.port, transport)
            self.mcp.run(transport=transport, host=self.host, port=self.port)
        else:
            logger.info("Starting Aster MCP Server (transport=stdio)")
            self.mcp.run(transport="stdio")


def create_simple_server(config_manager: Optional[ConfigManager] = None) -> SimpleAsterMCPServer:
    server = SimpleAsterMCPServer()
    if config_manager:
        server.config_manager = config_manager
        server.tools = AsterMCPTools(config_manager)
    return server


if __name__ == "__main__":
    server = SimpleAsterMCPServer()
    server.run()
