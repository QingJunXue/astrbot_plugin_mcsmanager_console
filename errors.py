class MCSManagerConsoleError(Exception):
    """Base error for user-facing plugin failures."""


class ConfigError(MCSManagerConsoleError):
    pass


class PermissionDenied(MCSManagerConsoleError):
    pass


class MCSManagerAPIError(MCSManagerConsoleError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def readable_api_error(status_code: int | None, payload: object) -> str:
    text = _extract_message(payload)
    lowered = text.lower()

    if status_code in {401, 403} or "apikey" in lowered or "api key" in lowered or "unauthorized" in lowered:
        return "MCSManager 鉴权失败，请检查 API Key。"
    if status_code == 404 or "not found" in lowered:
        if "daemon" in lowered or "node" in lowered:
            return "节点不存在或不可访问。"
        if "instance" in lowered or "uuid" in lowered:
            return "实例不存在或不可访问。"
        return "请求的资源不存在。"
    if status_code in {400, 422}:
        return f"参数错误：{text}" if text else "参数错误，请检查命令参数。"
    if status_code is not None and status_code >= 500:
        return "MCSManager 服务端错误，请稍后再试或检查面板日志。"
    return text or "MCSManager 请求失败。"


def _extract_message(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = payload.get("data")
        if isinstance(data, dict):
            return _extract_message(data)
    if isinstance(payload, str):
        return payload.strip()
    return ""