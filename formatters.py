from collections.abc import Iterable
from typing import Any


HELP_TEXT = """MCSManager Console
常用命令：
/mcs 节点：查看节点
/mcs 实例：查看所有实例
/mcs 实例 <节点ID>：查看指定节点实例
/mcs 详情 <实例ID>：查看实例详情
/mcs 启动 <实例ID>：启动实例
/mcs 停止 <实例ID>：停止实例
/mcs 重启 <实例ID>：重启实例
/mcs 日志 <实例ID>：查看实例日志
/mcs 命令 <实例ID> <命令>：发送控制台命令

完整写法：
/mcs 详情 <节点ID> <实例ID>
/mcs 启动|停止|重启|强杀 <节点ID> <实例ID>
/mcs 日志 <节点ID> <实例ID>
/mcs 命令 <节点ID> <实例ID> <命令>
/mcs 创建 <节点ID> <JSON配置>
/mcs 删除 <实例ID>
/mcs 配置 <节点ID> <实例ID> <JSON配置>

提示：实例、实列、list、ls 都可以查看实例。"""


def format_daemons(data: Any) -> str:
    items = _as_items(data)
    if not items:
        return "没有获取到节点。"
    lines = ["MCSManager 节点"]
    for item in items:
        daemon_id = _pick(item, "uuid", "id", "daemonId", "remoteServiceUuid")
        name = _pick(item, "remarks", "name", "ip", default="未命名节点")
        status = _pick(item, "available", "status", "state", default="未知")
        address = _pick(item, "ip", "addr", "address", default="")
        lines.append(f"- {name} | ID: {daemon_id or '未知'} | 状态: {_status_text(status)}{_suffix(address)}")
    return "\n".join(lines)


def format_instances(data: Any) -> str:
    items = _as_items(data)
    if not items:
        return "没有获取到实例。"
    lines = ["MCSManager 实例"]
    for item in items:
        daemon_id = _pick(item, "daemonId", "daemon_id", "remoteServiceUuid")
        instance_id = _pick(item, "uuid", "instanceUuid", "id")
        name = _pick(item, "nickname", "name", "config.nickname", default="未命名实例")
        status = _pick(item, "status", "started", "state", default="未知")
        daemon_part = f" | 节点: {daemon_id}" if daemon_id else ""
        lines.append(f"- {name} | ID: {instance_id or '未知'} | 状态: {_status_text(status)}{daemon_part}")
    return "\n".join(lines)


def format_instance_detail(data: Any) -> str:
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
        f"ID: {instance_id}",
        f"状态: {_status_text(status)}",
    ]
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
        "1": "运行中",
        "0": "已停止",
        "-1": "未知",
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