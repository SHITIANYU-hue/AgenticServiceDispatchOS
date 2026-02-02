
---

# instruction.md

## Agent Dispatch OS – 开发指引（基于现有代码）

> 本文档用于指导你在 **已有代码框架** 上继续完善系统功能。
> 不需要重构目录，不需要引入新技术栈，只需要在**指定文件中补全逻辑**。

目标：
把当前的 scaffold，补成一个 **可以完整跑通一次“私厨派单成交流程”** 的 Agent 系统。

---

## 一、你现在手里的系统“已经有什么”

在开始写代码前，请你先明确一件事：

👉 **这个项目不是从 0 开始的，你是在“补系统能力”，不是“造系统”。**

当前系统已经具备：

* FastAPI 服务入口（`app/main.py`）
* InMemory Repo（`app/storage/memory.py`）
* 基础 Agent Runtime（`app/aim/runtime.py`）
* Tool Registry（`app/aim/tools.py`）
* 私厨领域（`app/domains/private_chef/`）的基本骨架
* 基础 Agents：Reception / Dispatch / Negotiation / Ops（部分是 stub）

你要做的事情是：
**把“能跑”升级为“能用”，把“演示”升级为“可成交”。**

---

## 二、整体工作原则（很重要）

在写代码时，请严格遵守以下原则：

1. **不要新增目录结构**（除非我单独说可以）
2. **业务规则写在 engine / policy / state_machine 里**
3. **Agent 不写复杂逻辑，只做三件事**

   * 读取状态
   * 调用 tools
   * 生成下一步话术
4. **所有状态变化必须写回 repo**
5. **所有用户输入和 agent 回复必须写入 ConversationMessage**
6. **任何退款 / 改期 / 保证承诺，都不能自由回答，必须走 policy / guardrails**

---

## 三、你需要完成的核心功能（按模块）

下面我按**代码目录**，逐个说明你需要“补什么”。

---

## 1️⃣ app/storage/models.py

### 你要做什么

补充几个**真实业务中一定需要的字段**，让系统可以记住“成交相关状态”。

### 具体任务

请在对应 model 中补充：

#### Lead

* `last_offer_id: Optional[str]`
* `last_booking_id: Optional[str]`

#### Offer

* `currency: str = "CNY"`
* `breakdown: dict`
  例如：

  ```python
  {
    "food": 220000,
    "service": 60000,
    "transport": 20000
  }
  ```

#### Booking

* `deposit_paid_at: Optional[datetime]`
* `confirmed_at: Optional[datetime]`

### 验收标准

* 创建 Offer / Booking 不报错
* 新字段能被 `.model_dump()` 正确序列化

---

## 2️⃣ app/storage/base.py + memory.py

### 你要做什么

让 repo **支持完整查询链路**，而不是只能“写不能查”。

### 具体任务

在 `Repo` 接口和 `InMemoryRepo` 中补充：

* `get_lead(lead_id)`
* `get_offer(offer_id)`
* `get_offer_by_lead(lead_id)`
* `list_bookings_by_lead(lead_id)`

并新增一个非常重要的能力：

#### Tool 调用日志（最小版）

* 在 `InMemoryRepo` 中维护一个 `tool_call_logs: list`
* 每条 log 包含：

  ```python
  {
    "ts": datetime,
    "lead_id": str,
    "tool_name": str,
    "args": dict,
    "result_summary": str
  }
  ```

### 验收标准

* 能通过 repo 拿到 lead → offer → booking
* tool 调用后有 log 可查

---

## 3️⃣ app/aim/tools.py

### 你要做什么

让 Tool Registry **像“真实系统里的工具层”**，而不是函数集合。

### 具体任务

改造 `ToolRegistry.call`：

1. 支持传入 `ctx: AgentContext`
2. 调用前：

   * 校验 ctx.role 是否有权限调用该 tool
3. 调用后：

   * 把调用记录写入 repo 的 tool_call_logs
4. 捕获异常：

   * 返回结构化错误（不要直接 throw）

> ⚠️ 注意：不要在这里写业务逻辑，只做“调用治理”。

### 验收标准

* 无权限调用会被拒绝
* tool_call_logs 有记录
* Agent 调用 tool 出错时系统不崩

---

## 4️⃣ app/aim/workflow.py

### 你要做什么

现在的 `route_agent(stage)` 太简单，你要让它**像一个真正的调度器**。

### 具体任务

把路由规则升级为：

* 如果 lead.req 缺少关键信息
  → `ReceptionAgent`
* 如果信息齐全，且还没生成 Offer
  → `ProposalAgent`
* 如果用户话术中出现砍价意图
  → `NegotiationAgent`
* 如果定金已付但尚未派单
  → `DispatchAgent`
* 如果已生成 booking 且待支付 / 履约
  → `OpsAgent`

建议你让 `route_agent` 返回：

```python
(agent_name, route_reason)
```

### 验收标准

* 同一个 lead，在不同输入文本下路由会变化
* route_reason 可用于 debug

---

## 5️⃣ app/aim/guardrails.py

### 你要做什么

把它从“关键词判断”升级为**最低可用风控**。

### 具体任务

扩展 `should_escalate`，识别以下情况：

* 绕平台（私下转账 / 加微信 / 线下联系）
* 强投诉 / 威胁（报警 / 曝光 / 起诉）
* 不当承诺（“包退”“绝对保证”）

返回：

```python
(flag, reason, action)
```

其中 action ∈：

* `OK`
* `SOFT_REFUSE`
* `HARD_REFUSE`
* `ESCALATE`

### 验收标准

* 不同文本能返回不同 action
* agent 能据此决定是否转人工

---

## 6️⃣ app/domains/private_chef/tools.py

### 你要做什么

这是**私厨领域的“执行能力核心”**，必须补实。

### 具体任务

#### 1. extract_requirement

从用户文本中抽取：

* 人数
* 预算（元）
* 时间（周六晚 / 明天 / 日期）
* 地点关键词

可以先用：

* 正则
* 规则
* 简单关键词

#### 2. create_booking

* 默认 hold 时间来自 config
* 写入 lead.last_booking_id

#### 3. 新增 tool：confirm_deposit

* 模拟支付成功
* 更新 booking.status
* 写入 deposit_paid_at

### 验收标准

* “周六晚 8 人 预算 3000” 能被抽出来
* booking 状态能从 HOLD → DEPOSIT_PAID

---

## 7️⃣ app/domains/private_chef/state_machine.py

### 你要做什么

让 Lead 的 stage 推进**可预测、可测试**。

### 具体任务

实现以下函数：

* `is_min_info_ready(req)`
* `apply_requirement_update(lead, extracted_req)`
* `advance_lead(lead, event)`

事件包括：

* INFO_UPDATED
* OFFER_CREATED
* BOOKING_CREATED
* DEPOSIT_PAID
* CANCELLED

### 验收标准

* stage 不会乱跳
* 所有 stage 转移都能写测试覆盖

---

## 8️⃣ app/domains/private_chef/dispatch_engine.py

### 你要做什么

让“推荐哪个厨师”**有理有据**。

### 具体任务

升级排序逻辑，至少考虑：

* 人数是否匹配
* 预算是否覆盖
* 评分
* 档期可用

返回：

```python
[
  {
    "chef": Chef,
    "score": float,
    "reasons": ["预算匹配", "评分高"]
  }
]
```

### 验收标准

* 排序稳定
* reasons 可直接用于 agent 回复

---

## 9️⃣ app/domains/private_chef/policy_engine.py

### 你要做什么

统一管理取消 / 改期 / 退款规则。

### 具体任务

实现：

```python
calc_refund(deposit, hours_before)
```

返回：

```python
{
  "refund_amount": int,
  "fee_rate": float,
  "policy_tag": "FULL_REFUND | PARTIAL_REFUND | NO_REFUND"
}
```

### 验收标准

* 边界时间正确
* agent 不自行编造规则

---

## 🔟 app/domains/private_chef/agents/*

### 总体原则（必须遵守）

Agent 不做业务判断，只负责：

* 调用 engine / policy / tools
* 组织回复话术
* 推进状态

#### ReceptionAgent

* 补齐缺失信息
* 每次最多问 2 个问题
* 信息齐全后推进 stage

#### ProposalAgent

* 调用 proposal_engine
* 生成 Offer
* create_booking
* 给出“可成交”的回复（价格 + 锁档 + 支付）

#### DispatchAgent

* 调用 dispatch_engine
* 连接方案与厨师、确认可履约

#### NegotiationAgent

* 调用 pricing_rules
* 不低于底价
* 给替代方案
* 必要时触发 guardrails

#### OpsAgent

* 处理支付确认
* 改期 / 取消 / 退款走 policy_engine

### 验收标准

* 一轮对话能明显推动成交
* 不出现“只聊天不推进”的情况

---

## 四、你交付代码时必须包含

1. 代码本身
2. 至少 **5–10 个单元测试**
3. 一段 **完整对话示例**（request / response）

---

## 五、你现在在做什么（认知校准）

你不是在写：

* 聊天机器人
* 客服脚本

你在写的是：

> **一个可以替代“人工接线 + 派单 + 议价 + 锁档”的 Agent 系统**
