"""
配置管理模块

提供 API 密钥的加密存储、多账户管理。敏感信息使用 Fernet 加密存储在 ~/.config/aster-mcp/
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ConfigManager:
    """Aster MCP 配置管理器"""

    def __init__(self) -> None:
        self.config_dir = Path.home() / ".config" / "aster-mcp"
        self.config_file = self.config_dir / "config.json"
        self.key_file = self.config_dir / ".key"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._cipher = Fernet(self._get_encryption_key())
        self._config = self._load_config()

    def _get_encryption_key(self) -> bytes:
        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as f:
            f.write(key)
        os.chmod(self.key_file, 0o600)
        logger.info("Created new encryption key at %s", self.key_file)
        return key

    def _load_config(self) -> Dict[str, Any]:
        default = {
            "accounts": {},
            "server": {"port": 9002, "host": "127.0.0.1", "log_level": "INFO"},
            "mcp": {"server_name": "aster-mcp", "version": "0.1.0"},
        }
        if not self.config_file.exists():
            self._save_config(default)
            return default
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to load config: %s", e)
            raise RuntimeError("无法加载配置文件") from e

    def _save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        data = config or self._config
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.chmod(self.config_file, 0o600)

    def encrypt_value(self, value: str) -> str:
        return self._cipher.encrypt(value.encode()).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        try:
            return self._cipher.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            logger.error("Decrypt failed: %s", e)
            raise RuntimeError("解密失败") from e

    def add_account(
        self,
        account_id: str,
        api_key: str,
        api_secret: str,
        base_url: str = "https://fapi.asterdex.com",
        description: str = "",
    ) -> None:
        if account_id in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 已存在")
        self._config["accounts"][account_id] = {
            "auth_type": "hmac",
            "api_key": self.encrypt_value(api_key),
            "api_secret": self.encrypt_value(api_secret),
            "base_url": base_url.rstrip("/"),
            "description": description,
            "created_at": self._get_current_timestamp(),
        }
        self._save_config()
        logger.info("Added account: %s", account_id)

    def add_account_v3(
        self,
        account_id: str,
        user: str,
        signer: str,
        private_key: str,
        base_url: str = "https://fapi.asterdex.com",
        description: str = "",
    ) -> None:
        """添加 V3 密钥签名账户（EIP-712）。user=主账户钱包，signer=API 钱包，private_key=signer 私钥"""
        if account_id in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 已存在")
        self._config["accounts"][account_id] = {
            "auth_type": "eip712",
            "user": self.encrypt_value(user.strip()),
            "signer": self.encrypt_value(signer.strip()),
            "private_key": self.encrypt_value(private_key.strip()),
            "base_url": base_url.rstrip("/"),
            "description": description,
            "created_at": self._get_current_timestamp(),
        }
        self._save_config()
        logger.info("Added v3 account: %s", account_id)

    def remove_account(self, account_id: str) -> None:
        if account_id not in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 不存在")
        del self._config["accounts"][account_id]
        self._save_config()

    def get_account(self, account_id: str) -> Dict[str, Any]:
        if account_id not in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 不存在")
        acc = self._config["accounts"][account_id].copy()
        auth = acc.get("auth_type", "hmac")
        if auth == "eip712":
            acc["user"] = self.decrypt_value(acc["user"])
            acc["signer"] = self.decrypt_value(acc["signer"])
            acc["private_key"] = self.decrypt_value(acc["private_key"])
        else:
            acc["api_key"] = self.decrypt_value(acc["api_key"])
            acc["api_secret"] = self.decrypt_value(acc["api_secret"])
        return acc

    def list_accounts(self) -> Dict[str, Dict[str, Any]]:
        out = {}
        for aid, data in self._config["accounts"].items():
            out[aid] = {
                "auth_type": data.get("auth_type", "hmac"),
                "description": data.get("description", ""),
                "base_url": data.get("base_url", "https://fapi.asterdex.com"),
                "created_at": data.get("created_at", ""),
            }
        return out

    def update_account(
        self,
        account_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if account_id not in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 不存在")
        acc = self._config["accounts"][account_id]
        if acc.get("auth_type") == "eip712":
            raise ValueError("V3 账户请使用 update_account_v3 更新")
        if api_key is not None:
            acc["api_key"] = self.encrypt_value(api_key)
        if api_secret is not None:
            acc["api_secret"] = self.encrypt_value(api_secret)
        if base_url is not None:
            acc["base_url"] = base_url.rstrip("/")
        if description is not None:
            acc["description"] = description
        acc["updated_at"] = self._get_current_timestamp()
        self._save_config()

    def update_account_v3(
        self,
        account_id: str,
        user: Optional[str] = None,
        signer: Optional[str] = None,
        private_key: Optional[str] = None,
        base_url: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if account_id not in self._config["accounts"]:
            raise ValueError(f"账户 {account_id} 不存在")
        acc = self._config["accounts"][account_id]
        if acc.get("auth_type") != "eip712":
            raise ValueError("非 V3 账户请使用 update_account 更新")
        if user is not None:
            acc["user"] = self.encrypt_value(user.strip())
        if signer is not None:
            acc["signer"] = self.encrypt_value(signer.strip())
        if private_key is not None:
            acc["private_key"] = self.encrypt_value(private_key.strip())
        if base_url is not None:
            acc["base_url"] = base_url.rstrip("/")
        if description is not None:
            acc["description"] = description
        acc["updated_at"] = self._get_current_timestamp()
        self._save_config()

    def validate_account(self, account_id: str) -> bool:
        try:
            acc = self.get_account(account_id)
            if acc.get("auth_type") == "eip712":
                return bool(acc.get("user") and acc.get("signer") and acc.get("private_key"))
            return bool(acc.get("api_key") and acc.get("api_secret"))
        except Exception:
            return False

    def get_config_path(self) -> str:
        return str(self.config_file)

    def backup_config(self, backup_path: Optional[str] = None) -> str:
        from datetime import datetime
        import shutil
        if backup_path is None:
            backup_path = str(self.config_dir / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(self.config_file, backup_path)
        logger.warning(
            "Backup does NOT include the encryption key file (.key). "
            "Without the .key file, encrypted fields in the backup cannot be decrypted. "
            "Back up '%s' separately and store it securely.",
            self.key_file,
        )
        return backup_path

    @staticmethod
    def _get_current_timestamp() -> str:
        from datetime import datetime
        return datetime.now().isoformat()
