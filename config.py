from dataclasses import dataclass
from typing import Any

from .errors import ConfigError, PermissionDenied


@dataclass(frozen=True)
class PluginConfig:
    base_url: str
    api_key: str
    admin_users: frozenset[str]
    enabled_groups: frozenset[str]
    log_max_lines: int
    show_ids: bool
    overview_font: str

    @classmethod
    def from_astrbot(cls, config: Any) -> "PluginConfig":
        base_url = _read_config(config, "base_url", "").strip().rstrip("/")
        api_key = _read_config(config, "api_key", "").strip()
        legacy_admin_whitelist = _read_config(config, "admin_whitelist", [])
        admin_users = _normalize_id_list(_read_config(config, "admin_users", legacy_admin_whitelist))
        enabled_groups = _normalize_id_list(_read_config(config, "enabled_groups", []))
        log_max_lines = _normalize_log_lines(_read_config(config, "log_max_lines", 50))
        show_ids = _normalize_bool(_read_config(config, "show_ids", True))
        overview_font = str(_read_config(config, "overview_font", "微软雅黑")).strip()

        return cls(
            base_url=base_url,
            api_key=api_key,
            admin_users=frozenset(admin_users),
            enabled_groups=frozenset(enabled_groups),
            log_max_lines=log_max_lines,
            show_ids=show_ids,
            overview_font=overview_font,
        )

    def require_ready(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("base_url")
        if not self.api_key:
            missing.append("api_key")
        if missing:
            raise ConfigError(f"插件配置不完整：请先设置 {', '.join(missing)}。")

    def require_admin(self, user_identities: set[str]) -> None:
        if not self.admin_users.intersection(user_identities):
            raise PermissionDenied("无权限执行该命令。")

    def is_group_enabled(self, group_identities: set[str]) -> bool:
        return bool(self.enabled_groups.intersection(group_identities))


def collect_event_user_identities(event: Any) -> set[str]:
    message_obj = getattr(event, "message_obj", None)
    sender = getattr(message_obj, "sender", None)

    values = {
        _call_or_attr(event, "get_sender_id"),
        getattr(sender, "user_id", None),
    }
    return _normalize_identity_values(values)


def collect_event_group_identities(event: Any) -> set[str]:
    message_obj = getattr(event, "message_obj", None)

    values = {
        _call_or_attr(event, "get_group_id"),
        getattr(message_obj, "group_id", None),
    }
    return _normalize_identity_values(values)


def _read_config(config: Any, key: str, default: Any) -> Any:
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    getter = getattr(config, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(config, key, default)


def _normalize_id_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        items = value.replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]
    return _normalize_identity_values(items)


def _normalize_identity_values(values: Any) -> set[str]:
    return {str(value).strip() for value in values if str(value or "").strip()}


def _normalize_log_lines(value: Any) -> int:
    try:
        lines = int(value)
    except (TypeError, ValueError):
        lines = 50
    return min(max(lines, 1), 500)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "关闭", "否"}
    return bool(value)


def _call_or_attr(target: Any, name: str) -> Any:
    value = getattr(target, name, None)
    if callable(value):
        try:
            return value()
        except TypeError:
            return None
    return value