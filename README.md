# MCSManager Console

AstrBot 插件：通过 `/mcs` 聊天命令管理 MCSManager。

## 配置

- `base_url`：MCSManager 面板地址，例如 `http://127.0.0.1:23333`
- `api_key`：MCSManager API Key
- `admin_whitelist`：允许执行管理命令的用户 ID / 群 ID / 平台 ID
- `log_max_lines`：日志命令最多返回行数

## 常用命令

- `/mcs 节点`：查看节点
- `/mcs 实例`：查看所有实例
- `/mcs 实例 <节点ID>`：查看指定节点实例
- `/mcs 详情 <实例ID>`：查看实例详情
- `/mcs 启动 <实例ID>`：启动实例
- `/mcs 停止 <实例ID>`：停止实例
- `/mcs 重启 <实例ID>`：重启实例
- `/mcs 日志 <实例ID>`：查看实例日志
- `/mcs 命令 <实例ID> <命令>`：发送控制台命令
- `/mcs 帮助`：查看说明

`实例`、`实列`、`list`、`ls` 都可以用于查看实例。

## 完整写法

- `/mcs 详情 <节点ID> <实例ID>`
- `/mcs 启动|停止|重启|强杀 <节点ID> <实例ID>`
- `/mcs 日志 <节点ID> <实例ID>`
- `/mcs 命令 <节点ID> <实例ID> <命令>`
- `/mcs 创建 <节点ID> <JSON配置>`
- `/mcs 删除 <实例ID>`
- `/mcs 配置 <节点ID> <实例ID> <JSON配置>`

API Key 不会在聊天消息中回显。当前版本不提供默认节点 ID，不做高危操作二次确认。