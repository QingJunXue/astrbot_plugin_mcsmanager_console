from collections.abc import Iterable
from typing import Any


HELP_TEXT = """MCSManager Console
先看节点：
/mcs 节点

再用节点编号、节点名或节点ID查看实例：
/mcs 实例 <节点编号|节点名|节点ID>

然后直接用实例编号、实例名或简称操作：
/mcs 详情 <实例编号|实例名>
/mcs 启动 <实例编号|实例名>
/mcs 停止 <实例编号|实例名>
/mcs 重启 <实例编号|实例名>
/mcs 日志 <实例编号|实例名>
/mcs 命令 <实例编号|实例名> <命令>

其他命令：
/mcs 概览：查看仪表盘图片
/mcs 实例：查看所有实例
/mcs 强杀 <实例编号|实例名>
/mcs 删除 <实例编号|实例名>
/mcs 创建 <节点ID> <JSON配置>
/mcs 配置 <节点ID> <实例ID> <JSON配置>

示例：
/mcs 概览
/mcs 节点
/mcs 实例 1
/mcs 启动 1
/mcs 日志 生存服
/mcs 命令 2 say hello"""


def format_daemons(data: Any, *, numbered: bool = False, show_ids: bool = True) -> str:
    items = _as_items(data)
    if not items:
        return "没有获取到节点。"
    lines = ["MCSManager 节点"]
    for index, item in enumerate(items, start=1):
        daemon_id = _pick(item, "uuid", "id", "daemonId", "remoteServiceUuid")
        name = _pick(item, "remarks", "name", "ip", default="未命名节点")
        status = _pick(item, "available", "status", "state", default="未知")
        address = _pick(item, "ip", "addr", "address", default="")
        prefix = f"[{index}] " if numbered else "- "
        id_part = f" | ID: {daemon_id or '未知'}" if show_ids else ""
        lines.append(f"{prefix}{name}{id_part} | 状态: {_status_text(status)}{_suffix(address)}")
    if numbered:
        lines.append("\n可直接用节点编号、节点名或节点ID查看实例，例如：/mcs 实例 1")
    return "\n".join(lines)


def format_instances(data: Any, *, numbered: bool = False, show_ids: bool = True) -> str:
    items = _as_items(data)
    if not items:
        return "没有获取到实例。"
    lines = ["MCSManager 实例"]
    for index, item in enumerate(items, start=1):
        daemon_id = _pick(item, "daemonId", "daemon_id", "remoteServiceUuid")
        instance_id = _pick(item, "uuid", "instanceUuid", "id")
        name = _pick(item, "nickname", "name", "config.nickname", default="未命名实例")
        status = _pick(item, "status", "started", "state", default="未知")
        prefix = f"[{index}] " if numbered else "- "
        id_part = f" | ID: {instance_id or '未知'}" if show_ids else ""
        daemon_part = f" | 节点: {daemon_id}" if show_ids and daemon_id else ""
        lines.append(f"{prefix}{name} | 状态: {_instance_status_text(status)}{id_part}{daemon_part}")
    if numbered:
        lines.append("\n可直接使用编号、实例名或简称操作，例如：/mcs 启动 1")
    return "\n".join(lines)


def format_instance_detail(data: Any, *, show_ids: bool = True) -> str:
    item = _first_dict(data)
    if not item:
        return "没有获取到实例详情。"
    name = _pick(item, "nickname", "name", "config.nickname", default="未命名实例")
    instance_id = _pick(item, "uuid", "instanceUuid", "id", default="未知")
    status = _pick(item, "status", "started", "state", default="未知")
    end_time = _pick(item, "endTime", "config.endTime", default="")
    lines = [
        "实例详情",
        f"名称: {name}",
    ]
    if show_ids:
        lines.append(f"ID: {instance_id}")
    lines.append(f"状态: {_instance_status_text(status)}")
    if end_time:
        lines.append(f"到期/结束时间: {end_time}")
    return "\n".join(lines)


def format_action_result(action: str, data: Any) -> str:
    if isinstance(data, dict):
        message = _pick(data, "message", "msg")
        if message:
            return f"{action}已提交：{message}"
    return f"{action}已提交。"


def format_logs(data: Any, max_lines: int) -> str:
    text = _log_text(data)
    if not text.strip():
        return "没有获取到日志。"
    lines = text.splitlines()[-max_lines:]
    return "实例日志\n" + "\n".join(lines)


def _as_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "list", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    return []


def _first_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return {}


def _pick(item: dict[str, Any], *keys: str, default: str = "") -> Any:
    for key in keys:
        current: Any = item
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, ""):
            return current
    return default


def _status_text(value: Any) -> str:
    if value is True:
        return "在线"
    if value is False:
        return "离线"
    text = str(value)
    mapping = {
        "running": "运行中",
        "busy": "忙碌",
        "stopped": "已停止",
        "offline": "离线",
        "online": "在线",
    }
    return mapping.get(text.lower(), text)


def _instance_status_text(value: Any) -> str:
    if value is True:
        return "运行中"
    if value is False:
        return "已停止"
    text = str(value).strip()
    mapping = {
        "-1": "忙碌",
        "0": "已停止",
        "1": "停止中",
        "2": "启动中",
        "3": "运行中",
        "busy": "忙碌",
        "stopped": "已停止",
        "stopping": "停止中",
        "starting": "启动中",
        "running": "运行中",
        "offline": "已停止",
        "online": "运行中",
    }
    return mapping.get(text.lower(), text)


def _suffix(value: Any) -> str:
    text = str(value or "").strip()
    return f" | 地址: {text}" if text else ""


def _log_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("text", "log", "logs", "output", "content"):
            value = data.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
                return "\n".join(str(item) for item in value)
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return ""