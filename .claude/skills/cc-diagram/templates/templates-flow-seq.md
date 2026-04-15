# 一、流程图模板（flowchart）

## 骨架模板

```mermaid
flowchart TD
    classDef newAdd fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724
    classDef modified fill:#cce5ff,stroke:#0d6efd,stroke-width:2px,color:#084298
    classDef deleted fill:#f8d7da,stroke:#dc3545,stroke-width:2px,color:#721c24
    classDef core fill:#e2d5f1,stroke:#6f42c1,stroke-width:2px,color:#3b1f6e
    classDef external fill:#ffe0b2,stroke:#e65100,stroke-width:1px,color:#bf360c

    A[开始] --> B{条件判断}
    B -->|是| C[处理A]
    B -->|否| D[处理B]
    C --> E[结束]
    D --> E
```

---

## 业务流程模板（含 subgraph）

```mermaid
flowchart TD
    classDef newAdd fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724
    classDef modified fill:#cce5ff,stroke:#0d6efd,stroke-width:2px,color:#084298
    classDef deleted fill:#f8d7da,stroke:#dc3545,stroke-width:2px,color:#721c24
    classDef core fill:#e2d5f1,stroke:#6f42c1,stroke-width:2px,color:#3b1f6e
    classDef external fill:#ffe0b2,stroke:#e65100,stroke-width:1px,color:#bf360c

    subgraph input["输入"]
        A[用户请求]
    end

    subgraph process["处理"]
        B{参数校验}:::core
        C[业务处理]:::core
        D[(数据存储)]
    end

    subgraph output["输出"]
        E[返回结果]:::newAdd
    end

    A --> B
    B -->|通过| C
    B -->|失败| F[返回错误]:::warn
    C --> D
    D --> E
```

---

## 语法速查

| 语法 | 形状 | 用途 |
|------|------|------|
| `[文本]` | 矩形 | 普通步骤 |
| `(文本)` | 圆角矩形 | 柔和步骤 |
| `{文本}` | 菱形 | 判断条件 |
| `((文本))` | 圆形 | 开始/结束 |
| `[(文本)]` | 圆柱形 | 数据库 |
| `[[文本]]` | 子流程框 | 子流程调用 |
| `-->` | 实线箭头 | 连线 |
| `-.->` | 虚线箭头 | 弱连线 |
| `==>` | 粗线箭头 | 强调连线 |
| `-->\|标签\|` | 带标签 | 条件说明 |

**方向**：`TD`(上到下)、`LR`(左到右)、`BT`(下到上)、`RL`(右到左)

---

# 二、序列图模板（sequenceDiagram）

## 骨架模板

```mermaid
sequenceDiagram
    participant C as 客户端
    participant S as 服务端

    C->>S: 请求
    S-->>C: 响应
```

---

## 业务示例（含 alt/loop/par）

```mermaid
sequenceDiagram
    participant C as 客户端
    participant A as API服务
    participant Q as 消息队列
    participant W as Worker
    participant N as 通知服务

    C->>A: 提交任务
    A->>Q: 发送消息
    A-->>C: 202 Accepted (任务ID)

    Note over Q,W: 异步处理

    Q--)W: 消费消息
    W->>W: 执行任务

    alt 成功
        W->>N: 发送成功通知
        N--)C: 推送结果
    else 失败
        W->>Q: 重试/死信队列
    end
```

---

## 语法速查

| 语法 | 用途 |
|------|------|
| `->>` / `-->>` | 同步请求 / 响应 |
| `--)` / `---)` | 异步消息 / 响应 |
| `-x` | 失败/错误 |
| `alt/else/end` | 条件分支 |
| `opt/end` | 可选操作 |
| `loop/end` | 循环 |
| `par/and/end` | 并行 |
| `critical/end` | 关键区域 |
| `rect rgb()/end` | 高亮区域 |
| `Note over A,B:` | 说明文字 |
