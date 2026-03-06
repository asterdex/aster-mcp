"""
Aster MCP 工具实现

封装 Aster FAPI（期货）与 SAPI（现货）调用，供 MCP 服务器注册为工具。
符号统一：接受 BTCUSDT 或 BTC/USDT，内部转为 BTCUSDT。
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from .config import ConfigManager
from .client import AsterClient
from .spot_client import AsterSpotClient, _spot_base_url
from .v3_client import AsterClientV3

logger = logging.getLogger(__name__)


def _norm_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


class AsterMCPTools:
    """Aster MCP 工具集合"""

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self._client_cache: Dict[str, AsterClient] = {}
        self._v3_client_cache: Dict[str, AsterClientV3] = {}
        self._spot_client_cache: Dict[str, AsterSpotClient] = {}

    def _get_client(self, account_id: str):
        """返回期货客户端，根据 auth_type 自动选择 HMAC 或 V3 EIP-712"""
        acc = self.config_manager.get_account(account_id)
        auth = acc.get("auth_type", "hmac")
        base_url = acc.get("base_url", "https://fapi.asterdex.com")

        if auth == "eip712":
            if account_id not in self._v3_client_cache:
                self._v3_client_cache[account_id] = AsterClientV3(
                    user=acc["user"],
                    signer=acc["signer"],
                    private_key=acc["private_key"],
                    base_url=base_url,
                )
            return self._v3_client_cache[account_id]

        if account_id not in self._client_cache:
            self._client_cache[account_id] = AsterClient(
                api_key=acc["api_key"],
                api_secret=acc["api_secret"],
                base_url=base_url,
            )
        return self._client_cache[account_id]

    def _get_spot_client(self, account_id: str) -> AsterSpotClient:
        if account_id not in self._spot_client_cache:
            acc = self.config_manager.get_account(account_id)
            if acc.get("auth_type") == "eip712":
                raise ValueError(
                    f"账户 {account_id} 为 V3 密钥签名，现货接口需 HMAC 账户。请使用 HMAC 账户或单独配置现货 API。"
                )
            base = acc.get("base_url", "https://fapi.asterdex.com")
            spot_base = _spot_base_url(base)
            self._spot_client_cache[account_id] = AsterSpotClient(
                api_key=acc["api_key"],
                api_secret=acc["api_secret"],
                base_url=spot_base,
            )
        return self._spot_client_cache[account_id]

    def clear_cache(self) -> None:
        self._client_cache.clear()
        self._v3_client_cache.clear()
        self._spot_client_cache.clear()

    # ---------- 市场数据 ----------
    def ping(self) -> Dict[str, Any]:
        """无需账户，用默认 base_url 测连通性"""
        base = "https://fapi.asterdex.com"
        accounts = self.config_manager.list_accounts()
        if accounts:
            base = next(iter(accounts.values())).get("base_url", base)
        try:
            c = AsterClient("", "", base)
            return c.ping()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_24hr_ticker(s)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_order_book(s, limit=limit)

    def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[List]:
        s = _norm_symbol(symbol)
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_klines(s, interval, start_time=since, limit=limit)

    def get_funding_rate(self, symbol: Optional[str] = None) -> Any:
        s = _norm_symbol(symbol) if symbol else None
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_premium_index(s)

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        s = _norm_symbol(symbol) if symbol else None
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_exchange_info(s)

    # ---------- 账户与持仓 ----------
    def get_balance(self, account_id: str) -> Dict[str, Any]:
        return self._get_client(account_id).get_account_balance()

    def get_positions(self, account_id: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._get_client(account_id).get_position_risk(_norm_symbol(symbol) if symbol else None)
        if isinstance(data, list):
            return data
        return [data] if data else []

    def get_account_info(self, account_id: str) -> Dict[str, Any]:
        return self._get_client(account_id).get_account_info()

    def get_account_v4(self, account_id: str) -> Dict[str, Any]:
        """账户信息 V4（更完整，含 assets、positions）"""
        return self._get_client(account_id).get_account_v4()

    def get_funding_info(self, symbol: Optional[str] = None) -> Any:
        """查询资金费率配置（无需 account_id）"""
        s = _norm_symbol(symbol) if symbol else None
        c = AsterClient("", "", "https://fapi.asterdex.com")
        return c.get_funding_info(s)

    def get_income(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        income_type: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Any:
        """获取账户损益资金流水"""
        s = _norm_symbol(symbol) if symbol else None
        return self._get_client(account_id).get_income(
            symbol=s,
            income_type=income_type,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )

    def get_commission_rate(self, account_id: str, symbol: str) -> Dict[str, Any]:
        """期货用户手续费率"""
        s = _norm_symbol(symbol)
        return self._get_client(account_id).get_commission_rate(s)

    def get_leverage_bracket(
        self,
        account_id: str,
        symbol: Optional[str] = None,
    ) -> Any:
        """杠杆分层标准"""
        s = _norm_symbol(symbol) if symbol else None
        return self._get_client(account_id).get_leverage_bracket(s)

    # ---------- 订单 ----------
    def create_order(
        self,
        account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).create_order(
            symbol=s,
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=float(quantity),
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )

    def cancel_order(
        self,
        account_id: str,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).cancel_order(s, order_id=order_id, orig_client_order_id=orig_client_order_id)

    def cancel_all_orders(self, account_id: str, symbol: str) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).cancel_all_orders(s)

    def get_order(
        self,
        account_id: str,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).get_order(s, order_id=order_id, orig_client_order_id=orig_client_order_id)

    def get_open_orders(self, account_id: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._get_client(account_id).get_open_orders(_norm_symbol(symbol) if symbol else None)
        return data if isinstance(data, list) else [data]

    def get_all_orders(
        self,
        account_id: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        s = _norm_symbol(symbol)
        data = self._get_client(account_id).get_all_orders(s, limit=limit, start_time=start_time, end_time=end_time)
        return data if isinstance(data, list) else [data]

    def get_my_trades(
        self,
        account_id: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        s = _norm_symbol(symbol)
        data = self._get_client(account_id).get_user_trades(s, limit=limit, start_time=start_time, end_time=end_time)
        return data if isinstance(data, list) else [data]

    # ---------- 杠杆与划转 ----------
    def set_leverage(self, account_id: str, symbol: str, leverage: int) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).change_leverage(s, leverage)

    def set_margin_mode(self, account_id: str, symbol: str, margin_mode: str) -> Dict[str, Any]:
        s = _norm_symbol(symbol)
        return self._get_client(account_id).change_margin_type(s, margin_mode)

    def transfer_funds(
        self,
        account_id: str,
        asset: str,
        amount: float,
        transfer_type: int,
    ) -> Dict[str, Any]:
        """transfer_type: 1=现货→期货, 2=期货→现货。V3 账户使用 kindType 自动映射"""
        client = self._get_client(account_id)
        if isinstance(client, AsterClientV3):
            kind = "SPOT_FUTURE" if transfer_type == 1 else "FUTURE_SPOT"
            return client.asset_transfer(asset, amount, kind, str(uuid.uuid4()))
        return client.asset_transfer(asset, amount, transfer_type)

    # ---------- 现货 (Spot) ----------
    def get_spot_account(self, account_id: str) -> Dict[str, Any]:
        """现货账户信息（含 balances: free/locked）"""
        return self._get_spot_client(account_id).get_account()

    def get_spot_ticker(self, symbol: str) -> Dict[str, Any]:
        """现货 24h 行情（无需 account_id）"""
        s = _norm_symbol(symbol)
        c = AsterSpotClient("", "", "https://sapi.asterdex.com")
        return c.get_24hr_ticker(s)

    def get_spot_price(self, symbol: Optional[str] = None) -> Any:
        """现货最新价格（无需 account_id）"""
        s = _norm_symbol(symbol) if symbol else None
        c = AsterSpotClient("", "", "https://sapi.asterdex.com")
        return c.get_symbol_price(s)

    def get_spot_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """现货订单簿（无需 account_id）"""
        s = _norm_symbol(symbol)
        c = AsterSpotClient("", "", "https://sapi.asterdex.com")
        return c.get_order_book(s, limit=limit)

    def get_spot_klines(
        self,
        symbol: str,
        interval: str = "1h",
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[List]:
        """现货 K 线（无需 account_id）"""
        s = _norm_symbol(symbol)
        c = AsterSpotClient("", "", "https://sapi.asterdex.com")
        return c.get_klines(s, interval, start_time=since, limit=limit)

    def get_spot_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """现货交易规则（无需 account_id）"""
        s = _norm_symbol(symbol) if symbol else None
        c = AsterSpotClient("", "", "https://sapi.asterdex.com")
        return c.get_exchange_info(s)

    def create_spot_order(
        self,
        account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[str] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """现货下单。MARKET 买可用 quoteOrderQty，否则用 quantity"""
        s = _norm_symbol(symbol)
        return self._get_spot_client(account_id).create_order(
            symbol=s,
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=float(quantity) if quantity is not None else None,
            quote_order_qty=quote_order_qty,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )

    def cancel_spot_order(
        self,
        account_id: str,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """现货撤单"""
        s = _norm_symbol(symbol)
        return self._get_spot_client(account_id).cancel_order(
            s, order_id=order_id, orig_client_order_id=orig_client_order_id
        )

    def cancel_spot_all_orders(self, account_id: str, symbol: str) -> Dict[str, Any]:
        """现货撤销某交易对全部挂单"""
        s = _norm_symbol(symbol)
        return self._get_spot_client(account_id).cancel_all_orders(s)

    def get_spot_order(
        self,
        account_id: str,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """现货查询单笔订单"""
        s = _norm_symbol(symbol)
        return self._get_spot_client(account_id).get_order(
            s, order_id=order_id, orig_client_order_id=orig_client_order_id
        )

    def get_spot_open_orders(
        self,
        account_id: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """现货当前挂单"""
        s = _norm_symbol(symbol) if symbol else None
        data = self._get_spot_client(account_id).get_open_orders(s)
        return data if isinstance(data, list) else [data]

    def get_spot_all_orders(
        self,
        account_id: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """现货历史订单"""
        s = _norm_symbol(symbol)
        data = self._get_spot_client(account_id).get_all_orders(
            s, limit=limit, start_time=start_time, end_time=end_time
        )
        return data if isinstance(data, list) else [data]

    def get_spot_my_trades(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """现货成交记录"""
        s = _norm_symbol(symbol) if symbol else None
        data = self._get_spot_client(account_id).get_user_trades(
            s, limit=limit, start_time=start_time, end_time=end_time
        )
        return data if isinstance(data, list) else [data]

    def get_spot_transaction_history(
        self,
        account_id: str,
        asset: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Any:
        """现货交易流水。type: TRADE_TARGET, TRANSFER_SPOT_TO_FUTURE 等"""
        return self._get_spot_client(account_id).get_transaction_history(
            asset=asset,
            type=type,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )

    def get_spot_commission_rate(self, account_id: str, symbol: str) -> Dict[str, Any]:
        """现货 Symbol 手续费率"""
        s = _norm_symbol(symbol)
        return self._get_spot_client(account_id).get_commission_rate(s)

    def transfer_spot_futures(
        self,
        account_id: str,
        asset: str,
        amount: float,
        kind_type: str,
        client_tran_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """现货与期货账户划转。kindType: SPOT_FUTURE(现货→期货), FUTURE_SPOT(期货→现货)"""
        tid = client_tran_id or str(uuid.uuid4())
        return self._get_spot_client(account_id).asset_transfer(
            asset, amount, kind_type, tid
        )
