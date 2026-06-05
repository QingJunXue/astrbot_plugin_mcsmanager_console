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

PLUGIN_VERSION = "1.0.0"

ACTION_ALIASES = {
    "node": "节点",
    "nodes": "节点",
    "daemon": "节点",
    "daemons": "节点",
    "实例列表": "实例",
    "实列": "实例",
    "列实例": "实例",
    "list": "实例",
    "ls": "实例",
    "详情": "详情",
    "详细": "详情",
    "状态": "详情",
    "info": "详情",
    "启动": "启动",
    "start": "启动",
    "停止": "停止",
    "stop": "停止",
    "重启": "重启",
    "restart": "重启",
    "强杀": "强杀",
    "kill": "强杀",
    "命令": "命令",
    "cmd": "命令",
    "日志": "日志",
    "log": "日志",
    "logs": "日志",
    "创建": "创建",
    "删除": "删除",
    "配置": "配置",
    "帮助": "帮助",
    "help": "帮助",
    "-h": "帮助",
    "--help": "帮助",
}


@register(
    "astrbot_plugin_mcsmanager_console",
    "QingJunXue",
    "通过 /mcs 聊天命令管理 MCSManager。",
    PLUGIN_VERSION,
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
        if not parts:
            return HELP_TEXT

        action = _normalize_action(parts[0])
        if action == "帮助":
            return HELP_TEXT

        if action in {"节点", "实例", "详情"}:
            self.config.require_ready()
        else:
            self.config.require_ready()
            self.config.require_admin(collect_event_identities(event))

        client = self._get_client()

        if action == "节点":
            return format_daemons(await client.list_daemons())
        if action == "实例":
            if len(parts) >= 2:
                return format_instances(await client.list_instances(parts[1]))
            return await _format_all_instances(client)
        if action == "详情":
            daemon_id, instance_id = await _resolve_instance_args(client, parts, 1)
            return format_instance_detail(await client.instance_detail(daemon_id, instance_id))
        if action in PROCESS_ACTIONS:
            daemon_id, instance_id = await _resolve_instance_args(client, parts, 1)
            data = await PROCESS_ACTIONS[action](client, daemon_id, instance_id)
            return format_action_result(action, data)
        if action == "命令":
            daemon_id, instance_id, command = await _resolve_command_args(client, parts)
            return format_action_result("命令发送", await client.send_command(daemon_id, instance_id, command))
        if action == "日志":
            daemon_id, instance_id = await _resolve_instance_args(client, parts, 1)
            return format_logs(await client.instance_log(daemon_id, instance_id), self.config.log_max_lines)
        if action == "创建":
            daemon_id = _require_arg(parts, 1, "节点ID")
            payload = _json_arg(_require_rest(parts, 2, "JSON配置"))
            return format_action_result("创建实例", await client.create_instance(daemon_id, payload))
        if action == "删除":
            daemon_id, instance_id = await _resolve_instance_args(client, parts, 1)
            return format_action_result("删除实例", await client.delete_instance(daemon_id, instance_id))
        if action == "配置":
            daemon_id, instance_id = _require_pair(parts)
            payload = _json_arg(_require_rest(parts, 3, "JSON配置"))
            return format_action_result("更新配置", await client.update_instance(daemon_id, instance_id, payload))

        return f"未知命令：{parts[0]}\n发送 /mcs 帮助 查看用法。"

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
    for prefix in ("/mcs", "mcs"):
        if text == prefix:
            text = ""
            break
        if text.startswith(f"{prefix} "):
            text = text[len(prefix) :].strip()
            break
    if not text:
        return []
    try:
        return shlex.split(text, posix=False)
    except ValueError as exc:
        raise ConfigError(f"命令参数解析失败：{exc}") from exc


def _normalize_action(action: str) -> str:
    return ACTION_ALIASES.get(action.strip().lower(), action.strip())


async def _format_all_instances(client: MCSManagerClient) -> str:
    instances: list[dict[str, Any]] = []
    for daemon in _data_items(await client.list_daemons()):
        daemon_id = _pick(daemon, "uuid", "id", "daemonId", "remoteServiceUuid")
        if not daemon_id:
            continue
        for instance in _data_items(await client.list_instances(str(daemon_id))):
            item = dict(instance)
            item.setdefault("daemonId", daemon_id)
            instances.append(item)
    return format_instances(instances)


async def _resolve_instance_args(client: MCSManagerClient, parts: list[str], index: int) -> tuple[str, str]:
    if len(parts) <= index:
        raise ConfigError("缺少参数：实例ID。")
    if len(parts) > index + 1:
        return parts[index].strip(), parts[index + 1].strip()
    instance_id = parts[index].strip()
    if not instance_id:
        raise ConfigError("缺少参数：实例ID。")
    return await _find_instance_daemon(client, instance_id)


async def _resolve_command_args(client: MCSManagerClient, parts: list[str]) -> tuple[str, str, str]:
    if len(parts) >= 4:
        return parts[1].strip(), parts[2].strip(), _require_rest(parts, 3, "控制台命令")
    if len(parts) >= 3:
        daemon_id, instance_id = await _find_instance_daemon(client, parts[1].strip())
        return daemon_id, instance_id, _require_rest(parts, 2, "控制台命令")
    raise ConfigError("缺少参数：实例ID 和 控制台命令。")


async def _find_instance_daemon(client: MCSManagerClient, instance_id: str) -> tuple[str, str]:
    matches: list[str] = []
    for daemon in _data_items(await client.list_daemons()):
        daemon_id = _pick(daemon, "uuid", "id", "daemonId", "remoteServiceUuid")
        if not daemon_id:
            continue
        for instance in _data_items(await client.list_instances(str(daemon_id))):
            current_id = _pick(instance, "uuid", "instanceUuid", "id")
            if str(current_id) == instance_id:
                matches.append(str(daemon_id))
    if not matches:
        raise ConfigError("没有找到该实例，请检查实例ID，或改用完整写法：/mcs 详情 <节点ID> <实例ID>。")
    if len(matches) > 1:
        raise ConfigError("多个节点中发现同名实例，请使用完整写法：/mcs 详情 <节点ID> <实例ID>。")
    return matches[0], instance_id


def _data_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "list", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    return []


def _pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        current: Any = item
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, ""):
            return current
    return ""


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