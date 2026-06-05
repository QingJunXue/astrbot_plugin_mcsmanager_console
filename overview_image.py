from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

CARD_WIDTH = 1200
PADDING = 44
BG = (17, 24, 39)
CARD = (31, 41, 55)
CARD_ALT = (15, 23, 42)
TEXT = (248, 250, 252)
MUTED = (148, 163, 184)
BLUE = (59, 130, 246)
GREEN = (34, 197, 94)
YELLOW = (245, 158, 11)
RED = (239, 68, 68)
PURPLE = (168, 85, 247)


def render_overview_image(data: Any, *, font_path: str = "", font_download_url: str = "") -> str:
    _ = font_download_url
    overview = data if isinstance(data, dict) else {}
    remote = _list(overview.get("remote"))
    height = 720 + max(0, len(remote) - 1) * 150
    image = Image.new("RGB", (CARD_WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    fonts = _fonts(font_path)

    _draw_header(draw, overview, fonts)
    _draw_summary(draw, overview, remote, fonts)
    _draw_panel_card(draw, overview, fonts)
    _draw_remote_cards(draw, remote, fonts)

    path = Path(gettempdir()) / f"mcsmanager-overview-{uuid4().hex}.png"
    image.save(path, "PNG", optimize=True)
    return str(path)


def _draw_header(draw: ImageDraw.ImageDraw, overview: dict[str, Any], fonts: dict[str, ImageFont.ImageFont]) -> None:
    version = _text(overview.get("version"), "未知版本")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((PADDING, 34), "MCSManager 仪表盘", fill=TEXT, font=fonts["title"])
    draw.text((PADDING, 88), f"Panel {version} · {now}", fill=MUTED, font=fonts["body"])


def _draw_summary(
    draw: ImageDraw.ImageDraw,
    overview: dict[str, Any],
    remote: list[dict[str, Any]],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    remote_count = overview.get("remoteCount") if isinstance(overview.get("remoteCount"), dict) else {}
    available = _number(remote_count.get("available"), sum(1 for item in remote if item.get("available") is True))
    total = _number(remote_count.get("total"), len(remote))
    running = sum(_number(_dict(item.get("instance")).get("running"), 0) for item in remote)
    instances = sum(_number(_dict(item.get("instance")).get("total"), 0) for item in remote)

    latest_chart = _latest_chart_item(_dict(overview.get("chart")).get("system"))
    system = _dict(overview.get("system"))
    cpu = _percent(latest_chart.get("cpu", system.get("cpu")))
    mem = _mem_usage_percent(system.get("totalmem"), system.get("freemem"), latest_chart.get("mem"))

    cards = [
        ("节点", f"{available}/{total}", "在线 / 总数", GREEN if available == total and total else BLUE),
        ("实例", f"{running}/{instances}", "运行 / 总数", BLUE),
        ("CPU", _percent_text(cpu), "面板主机", YELLOW if cpu >= 70 else GREEN),
        ("内存", _percent_text(mem), "面板主机", RED if mem >= 85 else PURPLE),
    ]
    x = PADDING
    y = 145
    width = 264
    for title, value, desc, color in cards:
        _round_rect(draw, (x, y, x + width, y + 132), CARD, 22)
        draw.text((x + 24, y + 22), title, fill=MUTED, font=fonts["body"])
        draw.text((x + 24, y + 52), value, fill=TEXT, font=fonts["metric"])
        draw.text((x + 24, y + 102), desc, fill=color, font=fonts["small"])
        x += width + 24


def _draw_panel_card(draw: ImageDraw.ImageDraw, overview: dict[str, Any], fonts: dict[str, ImageFont.ImageFont]) -> None:
    system = _dict(overview.get("system"))
    process = _dict(overview.get("process"))
    record = _dict(overview.get("record"))
    x, y, w, h = PADDING, 320, CARD_WIDTH - PADDING * 2, 150
    _round_rect(draw, (x, y, x + w, y + h), CARD_ALT, 24)
    draw.text((x + 24, y + 20), "面板状态", fill=TEXT, font=fonts["subtitle"])
    rows = [
        ("主机", _text(system.get("hostname"), "未知")),
        ("系统", f"{_text(system.get('type'), '未知')} {_text(system.get('release'), '')}".strip()),
        ("Node", _text(system.get("node"), "未知")),
        ("运行时长", _duration(system.get("uptime"))),
        ("面板内存", _bytes(process.get("memory"))),
        ("登录/失败", f"{_number(record.get('logined'), 0)} / {_number(record.get('loginFailed'), 0)}"),
    ]
    _draw_key_values(draw, rows, x + 24, y + 62, fonts, columns=3, column_width=350)


def _draw_remote_cards(draw: ImageDraw.ImageDraw, remote: list[dict[str, Any]], fonts: dict[str, ImageFont.ImageFont]) -> None:
    y = 510
    draw.text((PADDING, y), "节点概览", fill=TEXT, font=fonts["subtitle"])
    y += 44
    if not remote:
        _round_rect(draw, (PADDING, y, CARD_WIDTH - PADDING, y + 96), CARD, 22)
        draw.text((PADDING + 24, y + 32), "暂无节点数据", fill=MUTED, font=fonts["body"])
        return

    for index, item in enumerate(remote, start=1):
        x, w, h = PADDING, CARD_WIDTH - PADDING * 2, 128
        _round_rect(draw, (x, y, x + w, y + h), CARD, 22)
        status_color = GREEN if item.get("available") is True else RED
        name = _text(item.get("remarks") or item.get("hostname") or item.get("ip"), "未命名节点")
        system = _dict(item.get("system"))
        instance = _dict(item.get("instance"))
        cpu = _percent(system.get("cpuUsage"))
        mem = _percent(system.get("memUsage"))

        draw.text((x + 24, y + 18), f"[{index}] {name}", fill=TEXT, font=fonts["subtitle"])
        draw.text((x + 24, y + 58), f"{_text(item.get('ip'), '未知地址')}:{_text(item.get('port'), '')}", fill=MUTED, font=fonts["small"])
        draw.text((x + 24, y + 88), "在线" if item.get("available") is True else "离线", fill=status_color, font=fonts["body"])

        stats = [
            ("实例", f"{_number(instance.get('running'), 0)}/{_number(instance.get('total'), 0)}"),
            ("CPU", _percent_text(cpu)),
            ("内存", _percent_text(mem)),
            ("系统", _text(system.get("platform") or system.get("type"), "未知")),
        ]
        sx = x + 410
        for label, value in stats:
            draw.text((sx, y + 30), value, fill=TEXT, font=fonts["metric_small"])
            draw.text((sx, y + 76), label, fill=MUTED, font=fonts["small"])
            sx += 155
        y += h + 22


def _draw_key_values(
    draw: ImageDraw.ImageDraw,
    rows: list[tuple[str, str]],
    x: int,
    y: int,
    fonts: dict[str, ImageFont.ImageFont],
    *,
    columns: int,
    column_width: int,
) -> None:
    for index, (label, value) in enumerate(rows):
        col = index % columns
        row = index // columns
        px = x + col * column_width
        py = y + row * 42
        draw.text((px, py), label, fill=MUTED, font=fonts["small"])
        draw.text((px + 90, py), value[:28], fill=TEXT, font=fonts["body"])


def _round_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int], radius: int) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=color)


def _fonts(font_path: str = "") -> dict[str, ImageFont.ImageFont]:
    candidates = [
        font_path,
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    def load(size: int) -> ImageFont.ImageFont:
        for path in candidates:
            try:
                if Path(path).exists():
                    return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    return {
        "title": load(42),
        "subtitle": load(28),
        "metric": load(40),
        "metric_small": load(30),
        "body": load(22),
        "small": load(18),
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _latest_chart_item(value: Any) -> dict[str, Any]:
    items = _list(value)
    return items[-1] if items else {}


def _text(value: Any, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value)


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _percent(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if 0 <= number <= 1:
        return number * 100
    return number


def _mem_usage_percent(totalmem: Any, freemem: Any, fallback: Any) -> float:
    if fallback not in (None, ""):
        return _percent(fallback)
    total = float(totalmem or 0)
    free = float(freemem or 0)
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (total - free) / total * 100))


def _percent_text(value: float) -> str:
    return f"{value:.1f}%"


def _bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "未知"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def _duration(value: Any) -> str:
    seconds = _number(value, 0)
    if seconds <= 0:
        return "未知"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}天 {hours}小时"
    if hours:
        return f"{hours}小时 {minutes}分"
    return f"{minutes}分钟"