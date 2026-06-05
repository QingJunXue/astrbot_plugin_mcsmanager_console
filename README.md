# MCSManager Console

AstrBot 插件：通过 `/mcs` 聊天命令管理 MCSManager。

## 配置

- `base_url`：MCSManager 面板地址，例如 `http://127.0.0.1:23333`
- `api_key`：MCSManager API Key
- `admin_whitelist`：允许执行管理命令的用户 ID / 群 ID / 平台 ID
- `log_max_lines`：日志命令最多返回行数

## 简单用法

先查看节点选项：

```text
/mcs 节点
```

再用节点编号、节点名或节点 ID 查看实例：

```text
/mcs 实例 <节点编号|节点名|节点ID>
```

插件会返回带编号的实例列表。之后可以直接用实例编号、实例名或实例名简称操作：

```text
/mcs 详情 <实例编号|实例名>
/mcs 启动 <实例编号|实例名>
/mcs 停止 <实例编号|实例名>
/mcs 重启 <实例编号|实例名>
/mcs 日志 <实例编号|实例名>
/mcs 命令 <实例编号|实例名> <命令>
```

示例：

```text
/mcs 节点
/mcs 实例 1
/mcs 启动 1
/mcs 日志 生存服
/mcs 命令 2 say hello
```

## 其他命令

```text
/mcs 节点
/mcs 实例
/mcs 实例 <节点编号|节点名|节点ID>
/mcs 强杀 <实例编号|实例名>
/mcs 删除 <实例编号|实例名>
/mcs 创建 <节点ID> <JSON配置>
/mcs 配置 <节点ID> <实例ID> <JSON配置>
/mcs 帮助
```

`实例`、`实列`、`list`、`ls` 都可以用于查看实例。

API Key 不会在聊天消息中回显。当前版本不提供默认节点 ID，不做高危操作二次确认。