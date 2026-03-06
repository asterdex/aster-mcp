"""
Aster FAPI 客户端（精简实现）

用于 MCP 工具层调用 Aster 期货 API，与 python-aster-sdk 接口兼容。
若已安装 aster_sdk，可改为 from aster_sdk import AsterSDK 并封装。
"""

import hashlib
import hmac
import time
import requests
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode


class AsterClient:
    """Aster FAPI 客户端（仅实现 MCP 所需接口）"""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://fapi.asterdex.com",
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/json",
        })

    def _sign(self, params: Dict[str, Any]) -> str:
        return hmac.new(
            self.api_secret.encode("utf-8"),
            urlencode(params).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        endpoint: str,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        params = dict(params or {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        for _attempt in range(4):  # 1 initial + 3 retries
            if method.upper() == "GET":
                resp = self.session.get(url, params=params, timeout=(5, 15))
            elif method.upper() == "POST":
                resp = self.session.post(url, data=params, timeout=(5, 15))
            elif method.upper() == "DELETE":
                resp = self.session.delete(url, data=params, timeout=(5, 15))
            else:
                raise ValueError(f"Unsupported method: {method}")
            if resp.status_code in (429, 418) and _attempt < 3:
                retry_after = int(resp.headers.get("Retry-After", 1))
                time.sleep(retry_after * (2 ** _attempt))
                continue
            break

        resp.raise_for_status()
        return resp.json()

    # ---------- 公开行情 ----------
    def ping(self) -> Dict:
        return self._request("GET", "/fapi/v1/ping")

    def get_server_time(self) -> Dict:
        return self._request("GET", "/fapi/v1/time")

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/exchangeInfo", params=params)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        return self._request("GET", "/fapi/v1/depth", params={"symbol": symbol, "limit": limit})

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> List[List]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._request("GET", "/fapi/v1/klines", params=params)

    def get_premium_index(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/premiumIndex", params=params)

    def get_funding_rate(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> Any:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._request("GET", "/fapi/v1/fundingRate", params=params)

    def get_24hr_ticker(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/ticker/24hr", params=params)

    def get_symbol_price(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/ticker/price", params=params)

    # ---------- 账户（需签名）----------
    def get_account_balance(self, recv_window: Optional[int] = None) -> Any:
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v2/balance", signed=True, params=params)

    def get_account_info(self, recv_window: Optional[int] = None) -> Any:
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v2/account", signed=True, params=params)

    def get_account_v4(self, recv_window: Optional[int] = None) -> Any:
        """账户信息 V4（更完整，含 assets、positions）"""
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v4/account", signed=True, params=params)

    def get_funding_info(self, symbol: Optional[str] = None, recv_window: Optional[int] = None) -> Any:
        """查询资金费率配置"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/fundingInfo", params=params)

    def get_income(
        self,
        symbol: Optional[str] = None,
        income_type: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        recv_window: Optional[int] = None,
    ) -> Any:
        """获取账户损益资金流水。incomeType: TRANSFER, REALIZED_PNL, FUNDING_FEE, COMMISSION 等"""
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if income_type:
            params["incomeType"] = income_type
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/income", signed=True, params=params)

    def get_commission_rate(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        """用户手续费率"""
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/commissionRate", signed=True, params=params)

    def get_leverage_bracket(
        self,
        symbol: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        """杠杆分层标准"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/leverageBracket", signed=True, params=params)

    def get_position_risk(self, symbol: Optional[str] = None, recv_window: Optional[int] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v2/positionRisk", signed=True, params=params)

    # ---------- 交易（需签名）----------
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        new_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
        }
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/fapi/v1/order", signed=True, params=params)

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("DELETE", "/fapi/v1/order", signed=True, params=params)

    def cancel_all_orders(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("DELETE", "/fapi/v1/allOpenOrders", signed=True, params=params)

    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/order", signed=True, params=params)

    def get_open_orders(self, symbol: Optional[str] = None, recv_window: Optional[int] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/openOrders", signed=True, params=params)

    def get_all_orders(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "limit": limit}
        if order_id is not None:
            params["orderId"] = order_id
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/allOrders", signed=True, params=params)

    def get_user_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        from_id: Optional[int] = None,
        limit: int = 500,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if from_id is not None:
            params["fromId"] = from_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v1/userTrades", signed=True, params=params)

    def change_leverage(self, symbol: str, leverage: int, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol, "leverage": leverage}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/fapi/v1/leverage", signed=True, params=params)

    def change_margin_type(
        self,
        symbol: str,
        margin_type: str,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "marginType": margin_type.upper()}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/fapi/v1/marginType", signed=True, params=params)

    def asset_transfer(self, asset: str, amount: float, transfer_type: int, recv_window: Optional[int] = None) -> Any:
        """type: 1=现货→期货, 2=期货→现货"""
        params = {"asset": asset, "amount": amount, "type": transfer_type}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/fapi/v1/futuresTransfer", signed=True, params=params)
