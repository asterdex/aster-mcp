"""
Aster FAPI v3 客户端（EIP-712 密钥签名）

用于对接 Aster 专业 API（aster-finance-futures-api-v3_CN），使用 EIP-712 结构化数据签名。
鉴权参数：user（主账户钱包地址）、signer（API 钱包地址）、nonce（微秒时间戳）、signature。

参考: https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3_CN.md
"""

import re
import time
import requests
from typing import Any, Dict, List, Optional

# EIP-712 签名依赖，可选安装
try:
    from eth_account.messages import encode_typed_data
    from eth_account import Account
    _HAS_ETH_ACCOUNT = True
except ImportError:
    _HAS_ETH_ACCOUNT = False

# Regex for validating a 64-hex-char private key (with optional 0x prefix)
_PK_RE = re.compile(r'^(0x)?[0-9a-fA-F]{64}$')

# EIP-712 domain for Aster v3 API signing.
# Note: chainId 1666 is an off-chain signing identifier specific to AsterDex.
# It is NOT the Harmony ONE network chainId. Do not confuse with on-chain chainIds
# (ETH=1, BSC=56, Arbitrum=42161).
# EIP-712 域配置（与 Aster v3 文档一致）
EIP712_DOMAIN = {
    "name": "AsterSignTransaction",
    "version": "1",
    "chainId": 1666,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}


def _params_to_str(params: Dict[str, Any]) -> str:
    """按 key ASCII 排序生成 param 字符串"""
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


class AsterClientV3:
    """Aster FAPI v3 客户端（EIP-712 密钥签名）"""

    def __init__(
        self,
        user: str,
        signer: str,
        private_key: str,
        base_url: str = "https://fapi.asterdex.com",
    ) -> None:
        if not _HAS_ETH_ACCOUNT:
            raise RuntimeError(
                "aster-mcp v3 鉴权需要 eth_account，请安装: pip install eth-account"
            )
        self.user = user.strip()
        self.signer = signer.strip()
        self._private_key = private_key.strip()
        if not _PK_RE.match(self._private_key):
            raise ValueError("Invalid private key: must be 64 hex chars (with or without 0x prefix)")
        if not self._private_key.startswith("0x"):
            self._private_key = "0x" + self._private_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "aster-mcp/0.1.0",
        })
        self._last_nonce_us = 0
        self._nonce_seq = 0

    def _next_nonce(self) -> int:
        now_us = int(time.time() * 1_000_000)
        if now_us == self._last_nonce_us:
            self._nonce_seq += 1
        else:
            self._last_nonce_us = now_us
            self._nonce_seq = 0
        return now_us + self._nonce_seq

    def _sign_eip712(self, params: Dict[str, Any]) -> str:
        """EIP-712 签名：params 转字符串，加入 nonce/user/signer，生成 signature"""
        params = dict(params)
        params["nonce"] = str(self._next_nonce())
        params["user"] = self.user
        params["signer"] = self.signer
        param_str = _params_to_str(params)

        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Message": [{"name": "msg", "type": "string"}],
            },
            "primaryType": "Message",
            "domain": EIP712_DOMAIN,
            "message": {"msg": param_str},
        }
        message = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(message, private_key=self._private_key)
        return signed.signature.hex()

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
            params["signature"] = self._sign_eip712(params)

        method = method.upper()
        for _attempt in range(4):  # 1 initial + 3 retries
            if method == "GET":
                resp = self.session.get(url, params=params, timeout=(5, 15))
            elif method in ("POST", "PUT", "DELETE"):
                resp = self.session.request(
                    method, url, data=params, timeout=(5, 15)
                )
            else:
                raise ValueError(f"Unsupported method: {method}")
            if resp.status_code in (429, 418) and _attempt < 3:
                retry_after = int(resp.headers.get("Retry-After", 1))
                time.sleep(retry_after * (2 ** _attempt))
                continue
            break

        resp.raise_for_status()
        return resp.json()

    # ---------- 公开行情（v3 路径）----------
    def ping(self) -> Dict:
        return self._request("GET", "/fapi/v3/ping")

    def get_server_time(self) -> Dict:
        return self._request("GET", "/fapi/v3/time")

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v3/exchangeInfo", params=params)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        return self._request("GET", "/fapi/v3/depth", params={"symbol": symbol, "limit": limit})

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
        return self._request("GET", "/fapi/v3/klines", params=params)

    def get_premium_index(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v3/premiumIndex", params=params)

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
        return self._request("GET", "/fapi/v3/fundingRate", params=params)

    def get_24hr_ticker(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v3/ticker/24hr", params=params)

    def get_symbol_price(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v3/ticker/price", params=params)

    def get_funding_info(self, symbol: Optional[str] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v3/fundingInfo", params=params)

    # ---------- 账户（需签名）----------
    def get_account_balance(self, recv_window: Optional[int] = None) -> Any:
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v3/balance", signed=True, params=params)

    def get_account_info(self, recv_window: Optional[int] = None) -> Any:
        params = {}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v3/account", signed=True, params=params)

    def get_position_risk(self, symbol: Optional[str] = None, recv_window: Optional[int] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v3/positionRisk", signed=True, params=params)

    def get_income(
        self,
        symbol: Optional[str] = None,
        income_type: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        recv_window: Optional[int] = None,
    ) -> Any:
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
        return self._request("GET", "/fapi/v3/income", signed=True, params=params)

    def get_commission_rate(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v3/commissionRate", signed=True, params=params)

    def get_leverage_bracket(
        self,
        symbol: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = recv_window
        return self._request("GET", "/fapi/v3/leverageBracket", signed=True, params=params)

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
            "quantity": str(quantity),
            "timeInForce": time_in_force,
            "reduceOnly": str(reduce_only).lower(),
        }
        if price is not None:
            params["price"] = str(price)
        if stop_price is not None:
            params["stopPrice"] = str(stop_price)
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("POST", "/fapi/v3/order", signed=True, params=params)

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = str(order_id)
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("DELETE", "/fapi/v3/order", signed=True, params=params)

    def cancel_all_orders(self, symbol: str, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol}
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("DELETE", "/fapi/v3/allOpenOrders", signed=True, params=params)

    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = str(order_id)
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("GET", "/fapi/v3/order", signed=True, params=params)

    def get_open_orders(self, symbol: Optional[str] = None, recv_window: Optional[int] = None) -> Any:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("GET", "/fapi/v3/openOrders", signed=True, params=params)

    def get_all_orders(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "limit": str(limit)}
        if order_id is not None:
            params["orderId"] = str(order_id)
        if start_time is not None:
            params["startTime"] = str(start_time)
        if end_time is not None:
            params["endTime"] = str(end_time)
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("GET", "/fapi/v3/allOrders", signed=True, params=params)

    def get_user_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        from_id: Optional[int] = None,
        limit: int = 500,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "limit": str(limit)}
        if start_time is not None:
            params["startTime"] = str(start_time)
        if end_time is not None:
            params["endTime"] = str(end_time)
        if from_id is not None:
            params["fromId"] = str(from_id)
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("GET", "/fapi/v3/userTrades", signed=True, params=params)

    def change_leverage(self, symbol: str, leverage: int, recv_window: Optional[int] = None) -> Any:
        params = {"symbol": symbol, "leverage": str(leverage)}
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("POST", "/fapi/v3/leverage", signed=True, params=params)

    def change_margin_type(
        self,
        symbol: str,
        margin_type: str,
        recv_window: Optional[int] = None,
    ) -> Any:
        params = {"symbol": symbol, "marginType": margin_type.upper()}
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("POST", "/fapi/v3/marginType", signed=True, params=params)

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
            "amount": str(amount),
            "kindType": kind_type,
            "clientTranId": client_tran_id,
        }
        if recv_window is not None:
            params["recvWindow"] = str(recv_window)
        return self._request("POST", "/fapi/v3/asset/wallet/transfer", signed=True, params=params)
