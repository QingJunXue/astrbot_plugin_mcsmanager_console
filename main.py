import json
import shlex
from collections.abc import Awaitable, Callable
from pathlib import Path
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
from .overview_image import render_overview_image

PLUGIN_VERSION = "1.0.0"

ACTION_ALIASES = {
    "dashboard": "概览",
    "overview": "概览",
    "仪表盘": "概览",
    "概览": "概览",
    "node": "节点",
    "节点": "节点",
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
        self.daemon_options: dict[str, list[dict[str, Any]]] = {}
        self.instance_options: dict[str, list[dict[str, Any]]] = {}

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
        yield event.image_result(str(result)) if isinstance(result, Path) else event.plain_result(result)

    async def terminate(self):
        if self.client is not None:
            await self.client.close()

    async def _dispatch(self, event: AstrMessageEvent) -> str | Path:
        parts = _parse_args(event.message_str)
        if not parts:
            return HELP_TEXT

        action = _normalize_action(parts[0])
        if action == "帮助":
            return HELP_TEXT

        if action in {"概览", "节点", "实例", "详情"}:
            self.config.require_ready()
        else:
            self.config.require_ready()
            self.config.require_admin(collect_event_identities(event))

        client = self._get_client()
        option_key = _option_key(event)

        if action == "概览":
            return Path(
                render_overview_image(
                    await client.overview(),
                    font_path=self.config.overview_font_path,
                    font_download_url=self.config.overview_font_download_url,
                )
            )
        if action == "节点":
            daemons = _data_items(await client.list_daemons())
            self.daemon_options[option_key] = daemons
            return format_daemons(daemons, numbered=True, show_ids=self.config.show_ids)
        if action == "实例":
            daemon_id = self._resolve_daemon_selector(option_key, parts[1]) if len(parts) >= 2 else None
            instances = await _load_instances(client, daemon_id)
            self.instance_options[option_key] = instances
            return format_instances(instances, numbered=True, show_ids=self.config.show_ids)
        if action == "详情":
            daemon_id, instance_id = await self._resolve_instance_args(client, option_key, parts, 1)
            return format_instance_detail(await client.instance_detail(daemon_id, instance_id), show_ids=self.config.show_ids)
        if action in PROCESS_ACTIONS:
            daemon_id, instance_id = await self._resolve_instance_args(client, option_key, parts, 1)
            data = await PROCESS_ACTIONS[action](client, daemon_id, instance_id)
            return format_action_result(action, data)
        if action == "命令":
            daemon_id, instance_id, command = await self._resolve_command_args(client, option_key, parts)
            return format_action_result("命令发送", await client.send_command(daemon_id, instance_id, command))
        if action == "日志":
            daemon_id, instance_id = await self._resolve_instance_args(client, option_key, parts, 1)
            return format_logs(await client.instance_log(daemon_id, instance_id), self.config.log_max_lines)
        if action == "创建":
            daemon_id = _require_arg(parts, 1, "节点ID")
            payload = _json_arg(_require_rest(parts, 2, "JSON配置"))
            return format_action_result("创建实例", await client.create_instance(daemon_id, payload))
        if action == "删除":
            daemon_id, instance_id = await self._resolve_instance_args(client, option_key, parts, 1)
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

    def _resolve_daemon_selector(self, option_key: str, selector: str) -> str:
        matched = _match_cached_daemon(self.daemon_options.get(option_key, []), selector)
        if matched is not None:
            return _daemon_id(matched)
        return selector.strip()

    async def _resolve_instance_args(
        self,
        client: MCSManagerClient,
        option_key: str,
        parts: list[str],
        index: int,
    ) -> tuple[str, str]:
        if len(parts) <= index:
            raise ConfigError("缺少参数：实例编号、实例名或实例ID。请先发送 /mcs 实例 查看可选项。")
        if len(parts) > index + 1:
            return parts[index].strip(), parts[index + 1].strip()
        selector = parts[index].strip()
        if not selector:
            raise ConfigError("缺少参数：实例编号、实例名或实例ID。")
        return await self._resolve_instance_selector(client, option_key, selector)

    async def _resolve_command_args(
        self,
        client: MCSManagerClient,
        option_key: str,
        parts: list[str],
    ) -> tuple[str, str, str]:
        if len(parts) < 3:
            raise ConfigError("缺少参数：实例编号/实例名 和 控制台命令。")

        cached = _match_cached_instance(self.instance_options.get(option_key, []), parts[1])
        if cached is not None:
            return _instance_daemon_id(cached), _instance_id(cached), _require_rest(parts, 2, "控制台命令")

        if len(parts) >= 4:
            return parts[1].strip(), parts[2].strip(), _require_rest(parts, 3, "控制台命令")

        daemon_id, instance_id = await self._resolve_instance_selector(client, option_key, parts[1].strip())
        return daemon_id, instance_id, _require_rest(parts, 2, "控制台命令")

    async def _resolve_instance_selector(
        self,
        client: MCSManagerClient,
        option_key: str,
        selector: str,
    ) -> tuple[str, str]:
        cached = _match_cached_instance(self.instance_options.get(option_key, []), selector)
        if cached is not None:
            return _instance_daemon_id(cached), _instance_id(cached)

        instances = await _load_instances(client)
        self.instance_options[option_key] = instances
        matched = _match_cached_instance(instances, selector)
        if matched is not None:
            return _instance_daemon_id(matched), _instance_id(matched)

        raise ConfigError("没有找到该实例。请先发送 /mcs 实例，然后用编号、实例名或简称操作。")


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


async def _load_instances(client: MCSManagerClient, daemon_id: str | None = None) -> list[dict[str, Any]]:
    if daemon_id:
        return _attach_daemon_id(await client.list_instances(daemon_id), daemon_id)

    instances: list[dict[str, Any]] = []
    for daemon in _data_items(await client.list_daemons()):
        current_daemon_id = _pick(daemon, "uuid", "id", "daemonId", "remoteServiceUuid")
        if not current_daemon_id:
            continue
        instances.extend(_attach_daemon_id(await client.list_instances(str(current_daemon_id)), str(current_daemon_id)))
    return instances


def _attach_daemon_id(data: Any, daemon_id: str) -> list[dict[str, Any]]:
    instances = []
    for instance in _data_items(data):
        item = dict(instance)
        item.setdefault("daemonId", daemon_id)
        instances.append(item)
    return instances


def _match_cached_instance(instances: list[dict[str, Any]], selector: str) -> dict[str, Any] | None:
    selector = selector.strip()
    if not selector:
        return None

    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(instances):
            return instances[index]

    exact_matches = [item for item in instances if selector in _instance_match_keys(item)]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        names = "、".join(_instance_name(item) for item in exact_matches[:5])
        raise ConfigError(f"匹配到多个实例：{names}。请使用列表编号。")

    selector_lower = selector.lower()
    fuzzy_matches = [
        item
        for item in instances
        if any(selector_lower in key.lower() for key in _instance_match_keys(item))
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    if len(fuzzy_matches) > 1:
        names = "、".join(_instance_name(item) for item in fuzzy_matches[:5])
        raise ConfigError(f"匹配到多个实例：{names}。请使用列表编号。")

    return None


def _match_cached_daemon(daemons: list[dict[str, Any]], selector: str) -> dict[str, Any] | None:
    selector = selector.strip()
    if not selector:
        return None

    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(daemons):
            return daemons[index]

    exact_matches = [item for item in daemons if selector in _daemon_match_keys(item)]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        names = "、".join(_daemon_name(item) for item in exact_matches[:5])
        raise ConfigError(f"匹配到多个节点：{names}。请使用节点列表编号。")

    selector_lower = selector.lower()
    fuzzy_matches = [
        item
        for item in daemons
        if any(selector_lower in key.lower() for key in _daemon_match_keys(item))
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    if len(fuzzy_matches) > 1:
        names = "、".join(_daemon_name(item) for item in fuzzy_matches[:5])
        raise ConfigError(f"匹配到多个节点：{names}。请使用节点列表编号。")

    return None


def _daemon_match_keys(item: dict[str, Any]) -> set[str]:
    keys = {
        str(_pick(item, "uuid")),
        str(_pick(item, "id")),
        str(_pick(item, "daemonId")),
        str(_pick(item, "remoteServiceUuid")),
        str(_pick(item, "remarks")),
        str(_pick(item, "name")),
        str(_pick(item, "ip")),
        str(_pick(item, "addr")),
        str(_pick(item, "address")),
    }
    return {key.strip() for key in keys if key.strip()}


def _daemon_name(item: dict[str, Any]) -> str:
    return str(_pick(item, "remarks", "name", "ip") or _daemon_id(item) or "未命名节点")


def _daemon_id(item: dict[str, Any]) -> str:
    daemon_id = str(_pick(item, "uuid", "id", "daemonId", "remoteServiceUuid") or "").strip()
    if not daemon_id:
        raise ConfigError("节点数据缺少节点ID。")
    return daemon_id


def _instance_match_keys(item: dict[str, Any]) -> set[str]:
    keys = {
        str(_pick(item, "uuid")),
        str(_pick(item, "instanceUuid")),
        str(_pick(item, "id")),
        str(_pick(item, "nickname")),
        str(_pick(item, "name")),
        str(_pick(item, "config.nickname")),
    }
    return {key.strip() for key in keys if key.strip()}


def _instance_name(item: dict[str, Any]) -> str:
    return str(_pick(item, "nickname", "name", "config.nickname") or _instance_id(item) or "未命名实例")


def _instance_id(item: dict[str, Any]) -> str:
    instance_id = str(_pick(item, "uuid", "instanceUuid", "id") or "").strip()
    if not instance_id:
        raise ConfigError("实例数据缺少实例ID。")
    return instance_id


def _instance_daemon_id(item: dict[str, Any]) -> str:
    daemon_id = str(_pick(item, "daemonId", "daemon_id", "remoteServiceUuid") or "").strip()
    if not daemon_id:
        raise ConfigError("实例数据缺少节点ID。")
    return daemon_id


def _option_key(event: AstrMessageEvent) -> str:
    return str(getattr(event, "unified_msg_origin", "") or getattr(getattr(event, "message_obj", None), "session_id", "") or "default")


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