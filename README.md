# MCSManager Console

AstrBot 插件：通过 `/mcs` 或 `mcs` 聊天命令管理 MCSManager。

## 配置

- `base_url`：MCSManager 面板地址，例如 `http://127.0.0.1:23333`
- `api_key`：MCSManager API Key
- `admin_users`：管理员用户 ID 列表；管理员可在私聊和已启用群聊执行管理命令
- `enabled_groups`：启用插件的群 ID 列表；只控制哪些群聊会响应 `mcs` 命令，不代表群成员是管理员
- `log_max_lines`：日志命令最多返回行数
- `show_ids`：是否在节点列表、实例列表、实例详情中显示 ID；关闭后实例列表中的节点 ID 也会隐藏
- `overview_font`：仪表盘图片字体选项；全系统均从插件 `Fonts`/`fonts` 目录选择，默认 `微软雅黑`

## 权限模型

- 私聊：普通查询命令可用；管理命令仅 `admin_users` 中的管理员用户可用。
- 群聊：群 ID 必须加入 `enabled_groups`，插件才会响应该群的 `mcs` 命令。
- 已启用群聊中：普通成员只能使用查询命令；`admin_users` 中的管理员用户可以执行管理命令。
- 群 ID 只表示该群是否启用，不会让群内所有成员获得管理员权限。

兼容说明：旧配置 `admin_whitelist` 仍可作为 `admin_users` 的兼容来源，但建议迁移到 `admin_users` 和 `enabled_groups`。

## 简单用法

先查看节点选项：

```text
/mcs 节点
```

再用节点编号、节点名或节点 ID 查看实例：

```text
/mcs 实例 <节点编号|节点名|节点ID>
```

插件会返回带编号的实例列表。普通用户可以继续查看实例详情；管理员可以继续执行启动、停止、重启、日志、命令等管理操作。

## 普通用户命令

普通用户不需要加入 `admin_users`，只能查看信息，不会改变实例状态。群聊中还需要当前群 ID 已加入 `enabled_groups`。

```text
/mcs 帮助
/mcs 概览
/mcs 节点
/mcs 实例
/mcs 实例 <节点编号|节点名|节点ID>
/mcs 详情 <实例编号|实例名|实例ID>
```

## 管理员命令

管理员需要在 `admin_users` 中配置用户 ID。管理员可以在私聊和已启用群聊使用普通用户命令，也可以执行以下管理命令：

```text
/mcs 启动 <实例编号|实例名|实例ID>
/mcs 停止 <实例编号|实例名|实例ID>
/mcs 重启 <实例编号|实例名|实例ID>
/mcs 强杀 <实例编号|实例名|实例ID>
/mcs 日志 <实例编号|实例名|实例ID>
/mcs 命令 <实例编号|实例名|实例ID> <命令>
/mcs 删除 <实例编号|实例名|实例ID>
/mcs 创建 <节点ID> <JSON配置>
/mcs 配置 <节点ID> <实例ID> <JSON配置>
```

示例：

```text
/mcs 概览
mcs 概览
/mcs 节点
/mcs 实例 1
/mcs 启动 1
/mcs 日志 生存服
/mcs 命令 2 say hello
```

`概览`、`仪表盘`、`overview`、`dashboard` 都可以用于查看仪表盘图片。

`实例`、`实列`、`list`、`ls` 都可以用于查看实例。

API Key 不会在聊天消息中回显。当前版本不提供默认节点 ID，不做高危操作二次确认。