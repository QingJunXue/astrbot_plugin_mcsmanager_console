from typing import Any

import httpx

from .errors import MCSManagerAPIError, readable_api_error


class MCSManagerClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "astrbot-plugin-mcsmanager-console/1.0.0",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def list_daemons(self) -> Any:
        return await self.get("/api/service/remote_services")

    async def list_instances(self, daemon_id: str) -> Any:
        last_error: MCSManagerAPIError | None = None
        for params in _instance_list_param_sets(daemon_id):
            try:
                return await self.get("/api/service/remote_service_instances", **params)
            except MCSManagerAPIError as exc:
                last_error = exc
                if "参数" not in str(exc):
                    raise
        if last_error is not None:
            raise last_error
        return []

    async def instance_detail(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/instance", daemonId=daemon_id, uuid=instance_id)

    async def start_instance(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/protected_instance/open", daemonId=daemon_id, uuid=instance_id)

    async def stop_instance(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/protected_instance/stop", daemonId=daemon_id, uuid=instance_id)

    async def restart_instance(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/protected_instance/restart", daemonId=daemon_id, uuid=instance_id)

    async def kill_instance(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/protected_instance/kill", daemonId=daemon_id, uuid=instance_id)

    async def send_command(self, daemon_id: str, instance_id: str, command: str) -> Any:
        return await self.get(
            "/api/protected_instance/command",
            daemonId=daemon_id,
            uuid=instance_id,
            command=command,
        )

    async def instance_log(self, daemon_id: str, instance_id: str) -> Any:
        return await self.get("/api/protected_instance/outputlog", daemonId=daemon_id, uuid=instance_id)

    async def create_instance(self, daemon_id: str, payload: dict[str, Any]) -> Any:
        return await self.post("/api/instance", json=payload, daemonId=daemon_id)

    async def delete_instance(self, daemon_id: str, instance_id: str) -> Any:
        return await self.delete("/api/instance", daemonId=daemon_id, uuid=instance_id)

    async def update_instance(self, daemon_id: str, instance_id: str, payload: dict[str, Any]) -> Any:
        return await self.put("/api/instance", json=payload, daemonId=daemon_id, uuid=instance_id)

    async def get(self, path: str, **params: Any) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, *, json: dict[str, Any] | None = None, **params: Any) -> Any:
        return await self.request("POST", path, params=params, json=json)

    async def put(self, path: str, *, json: dict[str, Any] | None = None, **params: Any) -> Any:
        return await self.request("PUT", path, params=params, json=json)

    async def delete(self, path: str, **params: Any) -> Any:
        return await self.request("DELETE", path, params=params)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        query = {k: v for k, v in (params or {}).items() if v is not None}
        query["apikey"] = self.api_key

        try:
            response = await self._client.request(method, path, params=query, json=json)
        except httpx.RequestError as exc:
            raise MCSManagerAPIError("无法连接 MCSManager 面板，请检查 base_url。") from exc

        payload = _decode_response(response)
        if response.status_code >= 400 or _is_failed_payload(payload):
            raise MCSManagerAPIError(
                readable_api_error(response.status_code, payload),
                status_code=response.status_code,
            )
        return _unwrap_payload(payload)


def _decode_response(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _is_failed_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    code = payload.get("code")
    if status in {False, "error", "failed", "failure"}:
        return True
    if isinstance(code, int) and code not in {0, 200}:
        return True
    return False


def _instance_list_param_sets(daemon_id: str) -> list[dict[str, Any]]:
    return [
        {"daemonId": daemon_id, "page": 1, "page_size": 100, "status": ""},
        {"daemonId": daemon_id, "page": 1, "page_size": 100, "status": "running"},
        {"daemonId": daemon_id, "page": 1, "page_size": 100, "status": "stopped"},
        {"daemonId": daemon_id, "page": 1, "pageSize": 100, "status": ""},
        {"remote_uuid": daemon_id, "page": 1, "page_size": 100, "status": ""},
        {"uuid": daemon_id, "page": 1, "page_size": 100, "status": ""},
    ]


def _unwrap_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload