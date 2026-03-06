"""
Aster MCP CLI

命令：config, list, start, stop, status, test, backup
"""

import os
import sys
import json
import time
import signal
import logging
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .config import ConfigManager
from .simple_server import SimpleAsterMCPServer
from .client import AsterClient
from .v3_client import AsterClientV3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="启用详细日志")
def cli(verbose: bool) -> None:
    """Aster MCP Server - Aster 期货 MCP 服务"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--account-id", help="指定账户 ID")
@click.option("--auth-type", type=click.Choice(["hmac", "v3"]), default="hmac",
              help="鉴权方式: hmac (API Key/Secret) 或 v3 (EIP-712 密钥签名)")
def config(account_id: Optional[str], auth_type: str) -> None:
    """配置 API 密钥和账户。v3 使用 user/signer/private_key 对接专业 API"""
    try:
        cm = ConfigManager()
        if account_id:
            accounts = cm.list_accounts()
            if account_id in accounts and not click.confirm(f"账户 {account_id} 已存在，是否覆盖？"):
                return
            base_url = click.prompt("Base URL", default="https://fapi.asterdex.com", show_default=True)
            description = click.prompt("账户描述 (可选)", default="", show_default=False)

            if auth_type == "v3":
                user = click.prompt("User (主账户钱包地址)", hide_input=False)
                signer = click.prompt("Signer (API 钱包地址)", hide_input=False)
                private_key = click.prompt("Private Key (signer 私钥)", hide_input=True)
                if account_id in accounts:
                    if accounts.get(account_id, {}).get("auth_type") == "eip712":
                        cm.update_account_v3(account_id, user=user, signer=signer, private_key=private_key,
                                            base_url=base_url, description=description)
                        click.echo(f"✓ V3 账户 {account_id} 已更新")
                    else:
                        cm.remove_account(account_id)
                        cm.add_account_v3(account_id, user, signer, private_key, base_url=base_url, description=description)
                        click.echo(f"✓ 已切换为 V3 账户 {account_id}")
                else:
                    cm.add_account_v3(account_id, user, signer, private_key, base_url=base_url, description=description)
                    click.echo(f"✓ V3 账户 {account_id} 已添加")
            else:
                api_key = click.prompt("API Key", hide_input=True)
                api_secret = click.prompt("API Secret", hide_input=True)
                if account_id in accounts:
                    if accounts.get(account_id, {}).get("auth_type") == "eip712":
                        cm.remove_account(account_id)
                        cm.add_account(account_id, api_key, api_secret, base_url=base_url, description=description)
                        click.echo(f"✓ 已切换为 HMAC 账户 {account_id}")
                    else:
                        cm.update_account(account_id, api_key=api_key, api_secret=api_secret, base_url=base_url, description=description)
                        click.echo(f"✓ 账户 {account_id} 已更新")
                else:
                    cm.add_account(account_id, api_key, api_secret, base_url=base_url, description=description)
                    click.echo(f"✓ 账户 {account_id} 已添加")
            if click.confirm("是否测试连接？", default=True):
                _test_connection(account_id)
        else:
            _interactive_setup(cm)
    except Exception as e:
        click.echo(f"配置失败: {e}", err=True)
        sys.exit(1)


def _interactive_setup(cm: ConfigManager) -> None:
    click.echo("=== Aster MCP 配置向导 ===\n")
    auth_choice = click.prompt("鉴权方式", type=click.Choice(["hmac", "v3"]), default="hmac")
    while True:
        account_id = click.prompt("账户 ID (例如 main)", default="main").strip() or "main"
        if account_id in cm.list_accounts() and not click.confirm(f"账户 {account_id} 已存在，是否覆盖？"):
            continue
        base_url = click.prompt("Base URL", default="https://fapi.asterdex.com")
        description = click.prompt("账户描述 (可选)", default="")
        try:
            existing = cm.list_accounts()
            if auth_choice == "v3":
                user = click.prompt("User (主账户钱包地址)")
                signer = click.prompt("Signer (API 钱包地址)")
                private_key = click.prompt("Private Key (signer 私钥)", hide_input=True)
                if account_id in existing:
                    if existing.get(account_id, {}).get("auth_type") == "eip712":
                        cm.update_account_v3(account_id, user=user, signer=signer, private_key=private_key,
                                            base_url=base_url, description=description)
                    else:
                        cm.remove_account(account_id)
                        cm.add_account_v3(account_id, user, signer, private_key, base_url=base_url, description=description)
                else:
                    cm.add_account_v3(account_id, user, signer, private_key, base_url=base_url, description=description)
                click.echo(f"✓ V3 账户 {account_id} 配置成功")
            else:
                api_key = click.prompt("API Key", hide_input=True)
                api_secret = click.prompt("API Secret", hide_input=True)
                if account_id in existing:
                    if existing.get(account_id, {}).get("auth_type") == "eip712":
                        cm.remove_account(account_id)
                        cm.add_account(account_id, api_key, api_secret, base_url=base_url, description=description)
                    else:
                        cm.update_account(account_id, api_key=api_key, api_secret=api_secret, base_url=base_url, description=description)
                else:
                    cm.add_account(account_id, api_key, api_secret, base_url=base_url, description=description)
                click.echo(f"✓ 账户 {account_id} 配置成功")
        except Exception as e:
            click.echo(f"✗ 失败: {e}")
            continue
        if not click.confirm("是否继续添加账户？", default=False):
            break
    click.echo(f"\n配置已保存: {cm.get_config_path()}")


@cli.command()
@click.option("--port", default=9002, help="服务端口", type=int)
@click.option("--host", default="127.0.0.1", help="服务地址")
@click.option("--daemon", "-d", is_flag=True, help="后台运行")
def start(port: int, host: str, daemon: bool) -> None:
    """启动 MCP 服务"""
    try:
        if _is_server_running(port):
            click.echo(f"MCP 服务已在端口 {port} 上运行")
            return
        cm = ConfigManager()
        accounts = cm.list_accounts()
        if not accounts:
            click.echo("未配置任何账户，请先运行: aster-mcp config", err=True)
            sys.exit(1)
        click.echo(f"启动 Aster MCP 服务... {host}:{port}")
        if daemon:
            _start_daemon(host, port)
        else:
            server = SimpleAsterMCPServer(port=port, host=host)
            try:
                signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
                signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
            except ValueError:
                pass
            server.run(transport="sse")
    except Exception as e:
        click.echo(f"启动失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--port", default=9002, type=int)
def stop(port: int) -> None:
    """停止 MCP 服务"""
    pid_file = Path.home() / ".config" / "aster-mcp" / f"mcp_{port}.pid"
    if not pid_file.exists():
        click.echo(f"端口 {port} 上没有运行的 MCP 服务")
        return
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
    except (IOError, ValueError):
        click.echo("无效的 PID 文件")
        pid_file.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
        pid_file.unlink(missing_ok=True)
        click.echo("MCP 服务已停止")
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        click.echo("进程已退出，已清理 PID 文件")
    except Exception as e:
        click.echo(f"停止失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--port", default=9002, type=int)
@click.option("--json-output", is_flag=True)
def status(port: int, json_output: bool) -> None:
    """查看服务状态"""
    try:
        cm = ConfigManager()
        info = {
            "service": "aster-mcp",
            "version": __version__,
            "port": port,
            "running": _is_server_running(port),
            "config_path": cm.get_config_path(),
            "accounts": {aid: {"description": a.get("description", ""), "valid": cm.validate_account(aid)} for aid, a in cm.list_accounts().items()},
        }
        if json_output:
            click.echo(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            click.echo("=== Aster MCP 服务状态 ===")
            click.echo(f"版本: {info['version']}")
            click.echo(f"端口: {info['port']}")
            click.echo(f"状态: {'运行中' if info['running'] else '已停止'}")
            click.echo(f"配置: {info['config_path']}")
            for aid, a in info["accounts"].items():
                click.echo(f"  {'✓' if a['valid'] else '✗'} {aid} - {a['description']}")
    except Exception as e:
        click.echo(f"获取状态失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--json-output", is_flag=True)
def list(json_output: bool) -> None:
    """列出已配置账户"""
    try:
        cm = ConfigManager()
        accounts = cm.list_accounts()
        if not accounts:
            click.echo("未配置任何账户。使用 aster-mcp config 添加。")
            return
        if json_output:
            click.echo(json.dumps(accounts, indent=2, ensure_ascii=False))
        else:
            for aid, a in accounts.items():
                auth = a.get("auth_type", "hmac")
                click.echo(f"  • {aid}  [{auth}]  {a.get('description', '')}  ({a.get('base_url', '')})")
    except Exception as e:
        click.echo(f"列出失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("account_id")
def test(account_id: str) -> None:
    """测试账户连接"""
    _test_connection(account_id)


def _test_connection(account_id: str) -> None:
    try:
        cm = ConfigManager()
        acc = cm.get_account(account_id)
        base = acc.get("base_url", "https://fapi.asterdex.com")
        if acc.get("auth_type") == "eip712":
            c = AsterClientV3(acc["user"], acc["signer"], acc["private_key"], base)
        else:
            c = AsterClient(acc["api_key"], acc["api_secret"], base)
        t = c.get_server_time()
        click.echo("✓ 连接成功")
        click.echo(f"  服务器时间: {t}")
    except Exception as e:
        click.echo(f"✗ 连接失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--backup-path", help="备份文件路径")
def backup(backup_path: Optional[str]) -> None:
    """备份配置文件（不包含 .key）"""
    try:
        cm = ConfigManager()
        path = cm.backup_config(backup_path)
        click.echo(f"配置已备份到: {path}")
    except Exception as e:
        click.echo(f"备份失败: {e}", err=True)
        sys.exit(1)


def _is_server_running(port: int) -> bool:
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _start_daemon(host: str, port: int) -> None:
    import subprocess
    pid_dir = Path.home() / ".config" / "aster-mcp"
    pid_dir.mkdir(parents=True, exist_ok=True)
    pid_file = pid_dir / f"mcp_{port}.pid"
    cmd = [sys.executable, "-m", "aster_mcp.cli", "start", "--host", host, "--port", str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    pid_file.write_text(str(proc.pid))
    time.sleep(2)
    if _is_server_running(port):
        click.echo(f"MCP 服务已在后台启动 (PID: {proc.pid})")
    else:
        click.echo("服务启动失败", err=True)
        pid_file.unlink(missing_ok=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
