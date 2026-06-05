import json
import shlex
from collections.abc import Awaitable, Callable
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .client import MCSManagerClient
from .config import PluginConfig, collect_event_identities
from .errors import ConfigError, MCSManagerConsoleError
from .formatters import (
    HELP_TEXT,
    format_action_result,
    format_daemons,
    format_instance_detail,
    format_instances,
    format_logs,
)


@register(
    "astrbot_plugin_mcsmanager_console",
    "QingJunXue",
    "通过 /mcs 聊天命令管理 MCSManager。",
    "0.1.0",
)
class MCSManagerConsolePlugin(Star):
    def __init__(self, context: Context, config: Any | None = None):
        super().__init__(context)
        self.config = PluginConfig.from_astrbot(config)
        self.client: MCSManagerClient | None = None

    @filter.command("mcs")
    async def mcs(self, event: AstrMessageEvent):
        """MCSManager Console 命令入口。"""
        try:
            result = await self._dispatch(event)
        except MCSManagerConsoleError as exc:
            result = str(exc)
        except Exception as exc:
            logger.error(f"MCSManager Console unexpected error: {exc}")
            result = "MCSManager Console 执行失败，请查看 AstrBot 日志。"
        yield event.plain_result(result)

    async def terminate(self):
        if self.client is not None:
            await self.client.close()

    async def _dispatch(self, event: AstrMessageEvent) -> str:
        parts = _parse_args(event.message_str)
        if not parts or parts[0] in {"帮助", "help", "-h", "--help"}:
            return HELP_TEXT

        action = parts[0]
        if action in {"节点", "实例", "详情"}:
            self.config.require_ready()
        else:
            self.config.require_ready()
            self.config.require_admin(collect_event_identities(event))

        client = self._get_client()

        if action == "节点":
            return format_daemons(await client.list_daemons())
        if action == "实例":
            daemon_id = _require_arg(parts, 1, "节点ID")
            return format_instances(await client.list_instances(daemon_id))
        if action == "详情":
            daemon_id, instance_id = _require_pair(parts)
            return format_instance_detail(await client.instance_detail(daemon_id, instance_id))
        if action in PROCESS_ACTIONS:
            daemon_id, instance_id = _require_pair(parts)
            data = await PROCESS_ACTIONS[action](client, daemon_id, instance_id)
            return format_action_result(action, data)
        if action == "命令":
            daemon_id, instance_id = _require_pair(parts)
            command = _require_rest(parts, 3, "控制台命令")
            return format_action_result("命令发送", await client.send_command(daemon_id, instance_id, command))
        if action == "日志":
            daemon_id, instance_id = _require_pair(parts)
            return format_logs(await client.instance_log(daemon_id, instance_id), self.config.log_max_lines)
        if action == "创建":
            daemon_id = _require_arg(parts, 1, "节点ID")
            payload = _json_arg(_require_rest(parts, 2, "JSON配置"))
            return format_action_result("创建实例", await client.create_instance(daemon_id, payload))
        if action == "删除":
            daemon_id, instance_id = _require_pair(parts)
            return format_action_result("删除实例", await client.delete_instance(daemon_id, instance_id))
        if action == "配置":
            daemon_id, instance_id = _require_pair(parts)
            payload = _json_arg(_require_rest(parts, 3, "JSON配置"))
            return format_action_result("更新配置", await client.update_instance(daemon_id, instance_id, payload))

        return f"未知命令：{action}\n发送 /mcs 帮助 查看用法。"

    def _get_client(self) -> MCSManagerClient:
        if self.client is None:
            self.client = MCSManagerClient(self.config.base_url, self.config.api_key)
        return self.client


async def _start(client: MCSManagerClient, daemon_id: str, instance_id: str) -> Any:
    return await client.start_instance(daemon_id, instance_id)


async def _stop(client: MCSManagerClient, daemon_id: str, instance_id: str) -> Any:
    return await client.stop_instance(daemon_id, instance_id)


async def _restart(client: MCSManagerClient, daemon_id: str, instance_id: str) -> Any:
    return await client.restart_instance(daemon_id, instance_id)


async def _kill(client: MCSManagerClient, daemon_id: str, instance_id: str) -> Any:
    return await client.kill_instance(daemon_id, instance_id)


PROCESS_ACTIONS: dict[str, Callable[[MCSManagerClient, str, str], Awaitable[Any]]] = {
    "启动": _start,
    "停止": _stop,
    "重启": _restart,
    "强杀": _kill,
}


def _parse_args(message: str) -> list[str]:
    text = message.strip()
    if text.startswith("/mcs"):
        text = text[4:].strip()
    if not text:
        return []
    try:
        return shlex.split(text, posix=False)
    except ValueError as exc:
        raise ConfigError(f"命令参数解析失败：{exc}") from exc


def _require_arg(parts: list[str], index: int, name: str) -> str:
    if len(parts) <= index or not parts[index].strip():
        raise ConfigError(f"缺少参数：{name}。")
    return parts[index].strip()


def _require_pair(parts: list[str]) -> tuple[str, str]:
    return _require_arg(parts, 1, "节点ID"), _require_arg(parts, 2, "实例ID")


def _require_rest(parts: list[str], index: int, name: str) -> str:
    if len(parts) <= index:
        raise ConfigError(f"缺少参数：{name}。")
    rest = " ".join(parts[index:]).strip()
    if not rest:
        raise ConfigError(f"缺少参数：{name}。")
    return rest


def _json_arg(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError("JSON 配置格式错误。") from exc
    if not isinstance(payload, dict):
        raise ConfigError("JSON 配置必须是对象。")
    return payload