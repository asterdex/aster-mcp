"""
Aster Spot API 客户端

用于 MCP 工具层调用 Aster 现货 API。
参考: https://github.com/asterdex/api-docs/blob/master/aster-finance-spot-api_CN.md
Base URL: https://sapi.asterdex.com
"""

import hashlib
import hmac
import time
import requests
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode


def _spot_base_url(futures_base: str) -> str:
    """从期货 base_url 推导现货 base_url"""
    if "fapi" in futures_base:
        return futures_base.replace("fapi", "sapi")
    return "https://sapi.asterdex.com"


class AsterSpotClient:
    """Aster Spot API 客户端"""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://sapi.asterdex.com",
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
        return self._request("GET", "/api/v1/ping")

    def get_server_time(self) -> Dict:
        return self._request("GET", "/api/v1/time")

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/exchangeInfo", params=params)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        return self._request("GET", "/api/v1/depth", params={"symbol": symbol, "limit": limit})

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
        return self._request("GET", "/api/v1/klines", params=params)

    def get_24hr_ticker(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/ticker/24hr", params=params)

    def get_symbol_price(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/ticker/price", params=params)

    def get_book_ticker(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/ticker/bookTicker", params=params)

    # ---------- 账户（需签名）----------
    def get_account(self, recv_window: Optional[int] = None) -> Any:
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/api/v1/account", signed=True, params=params)

    # ---------- 订单（需签名）----------
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        new_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
        }
        if quantity is not None:
            params["quantity"] = quantity
        if quote_order_qty is not None:
            params["quoteOrderQty"] = quote_order_qty
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if time_in_force:
            params["timeInForce"] = time_in_force
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/api/v1/order", signed=True, params=params)

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
        return self._request("DELETE", "/api/v1/order", signed=True, params=params)

    def cancel_all_orders(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("DELETE", "/api/v1/allOpenOrders", signed=True, params=params)

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
        return self._request("GET", "/api/v1/order", signed=True, params=params)

    def get_open_order(
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
        return self._request("GET", "/api/v1/openOrder", signed=True, params=params)

    def get_open_orders(
        self,
        symbol: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/api/v1/openOrders", signed=True, params=params)

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
        return self._request("GET", "/api/v1/allOrders", signed=True, params=params)

    def get_user_trades(
        self,
        symbol: Optional[str] = None,
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        from_id: Optional[int] = None,
        limit: int = 500,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if order_id is not None:
            params["orderId"] = order_id
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if from_id is not None:
            params["fromId"] = from_id
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/api/v1/userTrades", signed=True, params=params)

    def get_transaction_history(
        self,
        asset: Optional[str] = None,
        type: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"limit": limit}
        if asset:
            params["asset"] = asset
        if type:
            params["type"] = type
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/api/v1/transactionHistory", signed=True, params=params)

    def asset_transfer(
        self,
        asset: str,
        amount: float,
        kind_type: str,
        client_tran_id: str,
        recv_window: Optional[int] = None,
    ) -> Any:
        """kindType: FUTURE_SPOT(期货转现货), SPOT_FUTURE(现货转期货)"""
        params = {
            "asset": asset,
            "amount": amount,
            "kindType": kind_type,
            "clientTranId": client_tran_id,
        }
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("POST", "/api/v1/asset/wallet/transfer", signed=True, params=params)

    def get_commission_rate(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/api/v1/commissionRate", signed=True, params=params)
