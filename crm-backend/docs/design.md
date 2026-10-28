# CRM 系统设计文档

> 版本：v0.2  
> 依据：`docs/requirements.md`（v0.1，来源：crm-requirements）  
> 范围：B2B 销售型 CRM（线索 → 客户 → 商机 → 合同 → 售后）  
> 交付形态假设：单租户可部署，表结构预留 `tenant_id` 以支持多租户扩展  
> 技术栈定稿：后端 **Python**，数据库 **SQLite**，**不使用 Redis**

---

## 0. 设计总览

### 0.1 技术栈与分层

| 层 | 选型 | 说明 |
|----|------|------|
| 开发语言 | **Python 3.11+** | 后端唯一开发语言 |
| Web 框架 | FastAPI（建议）或 Flask | REST + JSON；OpenAPI 自动文档；写路径幂等键 |
| ORM / 访问层 | SQLAlchemy 2.x + Alembic（建议） | 迁移管理；事务边界清晰 |
| 前端 | SPA（React/Vue 均可）+ REST | 桌面 Web 优先，列表/详情响应式 |
| 鉴权 | Bearer JWT（无状态） | 登出可选 `token_blacklist` 表；会话不落外部缓存 |
| 数据库 | **SQLite**（WAL 模式） | 单文件部署；业务写路径用事务保证一致；并发写用 `BEGIN IMMEDIATE` |
| 后台任务 | 进程内线程 / APScheduler | 公海回收、异步导入、通知推送；状态落库（如 `import_job`），**不引入 Redis 队列** |
| 对象存储 | 本地文件系统（可选 S3 兼容） | 附件默认本地目录 |

**SQLite 落地约定**

- 启用 WAL：`PRAGMA journal_mode=WAL;`，提高读并发。
- JSON 字段以 `TEXT` 存储合法 JSON（应用层校验）；布尔用 `INTEGER`（0/1）。
- 时间统一存 UTC ISO-8601 字符串（`TEXT`）或 `DATETIME`；展示默认 `Asia/Shanghai`。
- 金额用 `NUMERIC`/`DECIMAL` 语义在应用层约束，库内可用 `TEXT` 或定点数约定（推荐存分为 `INTEGER` 或 `NUMERIC` 字符串，避免浮点误差）。
- 配额、幂等、导入任务等原「缓存/队列」能力一律用 **SQLite 表 + 事务** 实现。

### 0.2 分期映射

| 模块 | MVP | 二期 |
|------|-----|------|
| 组织/RBAC/审计 | ✅ | 字段布局增强、SSO |
| 线索 / 公海 | ✅ | 高级评分规则 |
| 客户 / 联系人 / 跟进 | ✅ | 母子公司层级深化 |
| 商机管道 | ✅ | 复杂阶段审批策略 |
| 目标看板 | ✅ 简单 | 自定义报表引擎 |
| 合同 / 回款 / 开票 | 骨架可选 | ✅ 完整 |
| 工单 / SLA / 健康度 | — | ✅ |
| 市场活动 ROI | — | ✅ |
| 开放 API / Webhook | — | ✅ |

### 0.3 横切约定

- **软删除**：业务主数据用 `deleted_at`；审计日志物理保留。
- **负责人模型**：`owner_user_id` + `collaborators`（协作人可见）。
- **数据范围**：本人 / 本部门 / 本部门及下级 / 全公司（查询层强制过滤）。
- **金额**：应用层按两位小数约束；库内推荐 `NUMERIC`/`TEXT` 或分（`INTEGER`）；币种默认 `CNY`。
- **时间**：存储 UTC，展示默认 `Asia/Shanghai`。
- **幂等**：变更类写接口支持头 `Idempotency-Key`（结果可落 `idempotency_record` 表）。
- **错误体**：`{ "code": "...", "message": "...", "details": {} }`。
- **分页**：`page`（从 1）+ `pageSize`（默认 20，最大 100）或游标 `cursor`（大数据列表可选）。
- **部署**：单进程或多进程均可；SQLite 适合中小并发单机部署，写密集场景避免多写进程争用同一库文件。

---

## 1. 数据库 Schema

### 1.1 ER 关系（逻辑）

```
Tenant 1─* Department 1─* User
Role *─* Permission；User *─* Role
User 1─* Lead / Account / Opportunity / Contract / Ticket（作为 owner）
Lead *─1 Account（转化后）；Lead *─* Contact（转化可选）
Account 1─* Contact；Account 1─* Opportunity；Account 1─* Contract
Opportunity 1─* OpportunityLine；Opportunity 0─1 Contract（赢单后）
Account/Lead 1─* Activity（跟进）；*─* Attachment
ApprovalInstance *─1 业务单据（多态）
PoolRule → 公海回收；ClaimQuota → 领取配额
SalesTarget → 个人/团队目标
AuditLog / LoginLog → 审计
```

### 1.2 枚举与字典

业务状态优先用表内枚举字段 + `sys_dict` 可配置字典（来源、输单原因、行业等）。

| 字典类型 `dict_type` | 示例值 |
|----------------------|--------|
| `lead_source` | website, exhibition, referral, import |
| `lead_status` | new, assigned, following, converted, invalid, pooled |
| `account_level` | A, B, C |
| `account_lifecycle` | prospect, active, churn_risk, churned |
| `opp_stage` | qualify, needs, proposal, negotiation, won, lost（可配置） |
| `activity_type` | visit, call, email, wechat, other |
| `contract_status` | draft, approving, active, changed, void |
| `ticket_priority` | low, medium, high, urgent |
| `ticket_status` | open, in_progress, pending, resolved, closed |

### 1.3 表定义

> 通用列（除特别说明外多数业务表具备）：  
> `id INTEGER PK`（`AUTOINCREMENT`），`tenant_id INTEGER NOT NULL`，`created_at`，`updated_at`，`created_by`，`updated_by`，`deleted_at`  
> 类型映射（相对常见 SQL 方言）：`BIGINT`→`INTEGER`，`VARCHAR(n)`→`TEXT`，`JSONB`→`TEXT`（JSON），`TIMESTAMPTZ`→`TEXT`/`DATETIME`，`BOOL`→`INTEGER`  
> 索引约定：`(tenant_id, ...)` 复合索引；列表过滤字段建索引。

#### 1.3.1 组织与权限（MVP）

**tenant**

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| name | TEXT | 租户名 |
| status | TEXT | active / disabled |
| timezone | TEXT | 默认 Asia/Shanghai |
| settings | TEXT (JSON) | 附件上限、密码策略等 |

**department**

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| tenant_id | INTEGER | |
| parent_id | INTEGER NULL | 树 |
| name | TEXT | |
| path | TEXT | 物化路径，如 `/1/3/8/`，支撑「本部门及下级」 |
| sort_order | INTEGER | |

**user_account**

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| tenant_id | INTEGER | |
| dept_id | INTEGER | |
| username | TEXT | 唯一 (tenant_id, username) |
| password_hash | TEXT | |
| display_name | TEXT | |
| email / mobile | TEXT | 可脱敏展示 |
| status | TEXT | active / disabled / locked |
| last_login_at | TEXT/DATETIME | UTC |
| failed_login_count | INTEGER | |

**role** / **permission** / **role_permission** / **user_role**

- `permission`：`code`（如 `lead:read`、`lead:export`）、`resource`、`action`
- `role`：`data_scope` 枚举（self / dept / dept_and_below / company）；可被用户级覆盖
- `user_data_scope_override`（可选）：用户例外数据范围

**field_permission**（字段级）

| 列 | 说明 |
|----|------|
| role_id, object_type, field_name | 组合唯一 |
| access | hidden / masked / read / write |
| allow_export | INTEGER | 0/1 |

#### 1.3.2 线索（MVP）

**lead**

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| tenant_id | INTEGER | |
| name | TEXT | 线索名称/公司名 |
| contact_name | TEXT | |
| mobile / email | TEXT | 唯一性去重候选 |
| source | TEXT | 字典 |
| channel | TEXT | |
| industry / company_size | TEXT | |
| score | INTEGER | 可选评分 |
| status | TEXT | 见枚举 |
| owner_user_id | INTEGER NULL | 未分配可空 |
| pool_status | TEXT | private / pooled |
| pooled_at / last_followed_at | TEXT/DATETIME | 回收规则依据 |
| converted_account_id | INTEGER NULL | |
| invalid_reason | TEXT | |
| tags | TEXT (JSON) / 关联表 | |
| custom_fields | TEXT (JSON) | 自定义字段 |

索引：`(tenant_id, status)`，`(tenant_id, owner_user_id)`，`(tenant_id, mobile)`，`(tenant_id, pool_status, last_followed_at)`

**lead_assignment_rule**

| 列 | 说明 |
|----|------|
| name, priority, enabled | |
| condition_json | 来源/区域/行业等 |
| strategy | round_robin / fixed_user / dept_queue |
| target_json | 用户或部门队列 |

**lead_merge_log**：合并审计（from_ids → to_id）

#### 1.3.3 客户与联系人（MVP）

**account**

| 列 | 类型 | 说明 |
|----|------|------|
| name | TEXT | |
| industry / region | TEXT | |
| level | TEXT | A/B/C |
| lifecycle_status | TEXT | |
| owner_user_id | INTEGER | |
| parent_account_id | INTEGER NULL | 母子公司（可选） |
| pool_status | TEXT | private / pooled |
| locked | INTEGER | 0/1，锁定禁止编辑 |
| last_followed_at | TEXT/DATETIME | |
| custom_fields | TEXT (JSON) | |

**contact**

| 列 | 说明 |
|----|------|
| account_id | 所属客户 |
| name, title, mobile, email | |
| decision_role | 决策/影响/使用等 |
| is_primary | INTEGER（0/1） |

**account_collaborator** / **lead_collaborator** / **opportunity_collaborator**

| owner 对象 id | user_id | role（collaborator/watcher） |

#### 1.3.4 跟进与附件（MVP）

**activity**

| 列 | 说明 |
|----|------|
| object_type / object_id | 多态：lead / account / opportunity / ticket |
| type | visit / call / email / wechat / other |
| subject, content | |
| happened_at | |
| owner_user_id | |
| next_follow_at | 提醒 |

**attachment**

| object_type/id | file_name | mime | size | storage_key | uploaded_by |

**comment**（@提及）

| object_type/id | body | mentions TEXT(JSON) | author_id |

**timeline** 可不落表：由 activity + 状态变更审计 + comment 聚合查询。

#### 1.3.5 商机（MVP）

**pipeline** / **pipeline_stage**

| pipeline | name, is_default |
| pipeline_stage | pipeline_id, code, name, sort_order, win_probability, enter_required_fields TEXT(JSON), need_approval INTEGER |

**opportunity**

| 列 | 说明 |
|----|------|
| account_id | 必填 |
| name | |
| amount | NUMERIC / TEXT | 应用层金额约束 |
| currency | TEXT | 如 CNY |
| probability | INTEGER | 可覆盖阶段默认 |
| expected_close_date | TEXT | DATE |
| stage_id | INTEGER | |
| status | TEXT | open / won / lost |
| lost_reason | TEXT | 输单必填 |
| owner_user_id | INTEGER | |
| competitor | TEXT | |
| won_at / lost_at | TEXT/DATETIME | |

**opportunity_line**

| opportunity_id | product_name / sku | qty | unit_price | amount |

**opportunity_stage_history**：阶段进入/退出时间、操作人、备注（漏斗分析）

#### 1.3.6 公海与配额（MVP）

**pool_rule**

| object_type (lead/account) | idle_days | condition_json | enabled |

**claim_quota**

| user_id / dept_id | object_type | period (day/week) | max_count |

**pool_claim_log** / **pool_recycle_log**：领取与回收审计

#### 1.3.7 目标与报表（MVP 简单）

**sales_target**

| scope_type (user/dept) | scope_id | metric (amount/count) | period_type (month/quarter) | period_key | target_value |

报表以查询/物化视图实现，首期可不建宽表；二期可加 `report_snapshot`。

#### 1.3.8 合同与回款（二期，表可先建骨架）

**contract**：account_id, opportunity_id, code, title, amount, status, effective_at, expire_at, owner_user_id, version  
**contract_payment_plan**：due_date, amount, status  
**payment_record**：plan_id, paid_at, amount, method  
**invoice_request**：contract_id, amount, status, invoiced_at  

#### 1.3.9 市场活动（二期）

**campaign**：name, budget, start_at, end_at, status  
**campaign_member**：campaign_id, lead_id / account_id  

#### 1.3.10 工单（二期）

**ticket**：account_id, title, category, priority, status, sla_due_at, owner_user_id, requester_id  
**ticket_event**：状态流转与评论  
**account_health_score**：account_id, score, factors TEXT(JSON), computed_at  

#### 1.3.11 审批、自动化、通知（MVP 审批骨架 + 通知）

**approval_flow** / **approval_node**：object_type, 多级、会签/或签  
**approval_instance** / **approval_task**：业务多态引用、状态、处理人  
**automation_rule**：trigger, condition, action（二期强化）  
**notification**：user_id, channel (inbox/email/im), title, body, read_at, payload TEXT(JSON)  
**todo_task**：user_id, type, due_at, ref_object, status  

#### 1.3.12 系统配置与审计（MVP）

**sys_dict** / **sys_dict_item**  
**custom_field_def**：object_type, field_key, field_type, options TEXT(JSON), required  
**layout_def**：对象表单/详情布局 TEXT(JSON)  
**audit_log**：actor_id, action, object_type/id, before/after TEXT(JSON), ip, request_id, created_at  
**login_log**：user_id, success, ip, ua, created_at  
**export_audit**：user_id, object_type, filter_json TEXT, row_count, created_at  
**idempotency_record**（可选）：`key` 唯一、`response_json`、`created_at`，支撑写接口幂等  
**token_blacklist**（可选）：JWT `jti`、过期时间，支撑主动登出  

**import_job**（异步导入，状态机由后台 Worker 轮询/调度，不依赖外部队列）

| type | file_key | status | total/success/fail | error_report_key | created_by |

### 1.4 关键约束与一致性

1. 线索转化：SQLite 事务内写 `account`（+可选 `contact`）→ 更新 lead.status=converted → 写 audit。  
2. 商机赢单：校验阶段必填 → status=won → 可选创建合同草稿。  
3. 公海回收：APScheduler（或等价）定时扫描 `last_followed_at` + `pool_rule`，写 recycle_log。  
4. 领取配额：同一 SQLite 事务内（`BEGIN IMMEDIATE`）按周期统计 `pool_claim_log` 并插入领取记录，超限则回滚，防超领（**不使用 Redis 计数**）。  
5. 数据范围：所有列表/导出 API 经统一数据范围过滤器（如 FastAPI 依赖 / 中间件）。  
6. 异步导入/导出：创建 `import_job`/`export` 记录后由进程内 Worker 消费；进度与结果只读库表。

---

## 2. API 契约

### 2.1 通用

**Base**：`/api/v1`  
**鉴权**：`Authorization: Bearer <token>`  
**租户**：Token 内 `tenant_id`；禁止客户端篡改跨租户。  
**幂等**：`Idempotency-Key`（POST/PATCH 关键写）  
**列表响应**：

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

**统一错误码（节选）**

| code | HTTP | 含义 |
|------|------|------|
| UNAUTHORIZED | 401 | 未登录 |
| FORBIDDEN | 403 | 无权限/越权 |
| NOT_FOUND | 404 | |
| VALIDATION_ERROR | 400 | 字段校验 |
| CONFLICT | 409 | 去重冲突、状态机非法流转 |
| QUOTA_EXCEEDED | 429 | 公海领取配额 |
| IDEMPOTENCY_REPLAY | 200 | 返回首次结果 |

### 2.2 认证与会话

| Method | Path | 说明 |
|--------|------|------|
| POST | `/auth/login` | 用户名密码 → token + 用户/角色摘要 |
| POST | `/auth/logout` | 失效会话 |
| GET | `/auth/me` | 当前用户、菜单权限、数据范围 |
| POST | `/auth/password/change` | 改密 |

### 2.3 组织与权限（管理员）

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/departments` | 树列表 / 创建 |
| PATCH/DELETE | `/departments/{id}` | |
| GET/POST | `/users` | |
| PATCH | `/users/{id}` | 含启用停用 |
| POST | `/users/{id}/reset-password` | |
| GET/POST | `/roles` | |
| PUT | `/roles/{id}/permissions` | |
| PUT | `/roles/{id}/field-permissions` | |
| GET | `/permissions` | 权限目录 |

### 2.4 线索

| Method | Path | 说明 |
|--------|------|------|
| GET | `/leads` | 过滤：status, source, owner, pool, keyword, tags |
| POST | `/leads` | 新建 |
| GET/PATCH | `/leads/{id}` | 详情/编辑（字段级脱敏） |
| POST | `/leads/import` | 上传文件 → 返回 `jobId` |
| GET | `/import-jobs/{id}` | 导入进度 |
| POST | `/leads/assign` | body: `{ ids, userId }` 手动分配 |
| POST | `/leads/{id}/claim` | 公海认领 |
| POST | `/leads/{id}/convert` | → 客户/联系人 |
| POST | `/leads/{id}/invalidate` | 作废原因 |
| POST | `/leads/merge` | `{ primaryId, mergeIds[] }` |
| POST | `/leads/{id}/return-to-pool` | 退回公海 |

### 2.5 客户与联系人

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/accounts` | |
| GET/PATCH | `/accounts/{id}` | |
| POST | `/accounts/merge` | |
| POST | `/accounts/{id}/transfer` | 变更负责人 |
| POST | `/accounts/{id}/lock` | 锁定/解锁 |
| POST | `/accounts/{id}/claim` | 公海领取 |
| GET/POST | `/accounts/{id}/contacts` | |
| PATCH/DELETE | `/contacts/{id}` | |
| PUT | `/accounts/{id}/collaborators` | |

### 2.6 跟进 / 时间线 / 附件

| Method | Path | 说明 |
|--------|------|------|
| GET | `/activities` | query: objectType, objectId |
| POST | `/activities` | 写跟进；更新 last_followed_at |
| GET | `/objects/{type}/{id}/timeline` | 聚合时间线 |
| POST | `/attachments` | multipart |
| GET/DELETE | `/attachments/{id}` | |
| GET/POST | `/objects/{type}/{id}/comments` | 支持 @mentions |

### 2.7 商机

| Method | Path | 说明 |
|--------|------|------|
| GET | `/pipelines` | 含 stages |
| PUT | `/pipelines/{id}/stages` | 管理员配置 |
| GET/POST | `/opportunities` | |
| GET/PATCH | `/opportunities/{id}` | |
| POST | `/opportunities/{id}/stage` | `{ stageId }` 含必填校验/审批 |
| POST | `/opportunities/{id}/close` | `{ result: won\|lost, lostReason? }` |
| GET/PUT | `/opportunities/{id}/lines` | 产品明细 |
| PUT | `/opportunities/{id}/collaborators` | |

### 2.8 公海与规则

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/pool-rules` | |
| PATCH | `/pool-rules/{id}` | |
| GET | `/pool/leads` `/pool/accounts` | 公海列表 |
| GET/PUT | `/claim-quotas` | 配额配置 |
| GET | `/claim-quotas/me` | 当前剩余配额 |
| POST | `/pool/force-assign` | 经理强制分配 |

### 2.9 目标与看板（MVP）

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/sales-targets` | |
| PATCH | `/sales-targets/{id}` | |
| GET | `/dashboards/overview` | 漏斗、达成率摘要 |
| GET | `/dashboards/funnel` | 阶段聚合 |
| GET | `/dashboards/performance` | 排行；支持下钻 opportunity 列表 query |
| POST | `/reports/export` | 异步导出 → job；记 export_audit |

### 2.10 合同 / 回款（二期）

| Method | Path | 说明 |
|--------|------|------|
| CRUD | `/contracts` | 含提交审批、生效、作废 |
| CRUD | `/contracts/{id}/payment-plans` | |
| POST | `/payment-records` | |
| CRUD | `/invoice-requests` | |

### 2.11 工单 / 活动（二期）

| Method | Path | 说明 |
|--------|------|------|
| CRUD | `/tickets` | assign / transfer / close |
| CRUD | `/campaigns` | members、效果统计 |

### 2.12 审批 / 待办 / 通知

| Method | Path | 说明 |
|--------|------|------|
| GET | `/approvals/todo` | 我的审批 |
| POST | `/approvals/{taskId}/decide` | approve / reject |
| GET | `/todos` | |
| PATCH | `/todos/{id}` | complete |
| GET | `/notifications` | |
| POST | `/notifications/read` | |

### 2.13 系统配置与审计

| Method | Path | 说明 |
|--------|------|------|
| CRUD | `/dicts/{type}/items` | |
| CRUD | `/custom-fields` | objectType |
| GET/PUT | `/layouts/{objectType}` | |
| CRUD | `/approval-flows` | |
| GET | `/audit-logs` | 过滤 actor/action/object/时间 |
| GET | `/login-logs` | |
| GET | `/export-audits` | |

### 2.14 关键用例与 API 编排（验收对齐）

1. **UC-01**：`POST /leads/import` → 规则引擎或 `POST /leads/assign` → `POST /activities`  
2. **UC-02**：`POST /leads/{id}/convert`  
3. **UC-03**：`POST /accounts` + contacts + activities + timeline  
4. **UC-04**：`POST /opportunities` → `POST .../stage` → `POST .../close`  
5. **UC-06**：定时 recycle + `POST .../claim` + quota  
6. **UC-07**：`/sales-targets` + `/dashboards/*`  
7. **UC-09**：部门用户角色 + `/audit-logs`

---

## 3. 前端页面结构

### 3.1 信息架构（路由树）

```
/login
/app                          # 需登录 Layout：顶栏 + 侧栏 + 内容
  /dashboard                  # 首页仪表盘（可配置组件占位）
  /leads
    /                         # 线索列表（含公海 Tab）
    /new
    /:id                      # 详情：资料 / 跟进 / 协作
    /import                   # 导入向导
  /accounts
    /                         # 客户列表（含公海 Tab）
    /new
    /:id                      # 详情：联系人 / 商机 / 合同 / 时间线 / 附件
    /:id/contacts/:contactId
  /opportunities
    /                         # 列表 + 看板（管道视图）
    /new
    /:id
  /contracts                  # 二期；MVP 可隐藏菜单
    / ...
  /tickets                    # 二期
  /campaigns                  # 二期
  /targets                    # 目标设定
  /reports                    # 报表中心 / 导出
  /todos                      # 待办与审批入口
  /notifications
  /settings                   # 系统管理（管理员）
    /org                      # 组织与用户
    /roles
    /fields                   # 自定义字段与布局
    /pipelines                # 商机阶段
    /pool-rules               # 公海与配额
    /approvals                # 审批流
    /dicts
    /audit                    # 操作/登录/导出审计
/403 /404
```

菜单按 `auth/me` 返回的权限码动态渲染；无权限路由守卫跳转 403。

### 3.2 页面职责与关键组件

| 页面 | 一句话职责 | 关键交互/组件 |
|------|------------|----------------|
| Login | 登录 | 表单校验、锁定提示 |
| Dashboard | 漏斗与目标达成一览 | FunnelChart、TargetProgress、可下钻列表 |
| LeadList | 筛选/分配/认领/批量 | FilterBar、DataTable、BulkActions、PoolTabs |
| LeadDetail | 跟进与转化 | InfoForm、ActivityComposer、ConvertDialog、Timeline |
| LeadImport | 异步导入 | UploadStep、MappingStep、JobProgress |
| AccountList/Detail | 客户档案与时间线 | ContactPanel、TransferDialog、MergeWizard |
| OppBoard | 阶段管道推进 | KanbanBoard、StageChangeModal（必填校验） |
| OppDetail | 金额/产品行/结案 | LineEditor、CloseWonLostDialog |
| Targets | 目标分解 | TargetGrid（部门/人） |
| Reports | 导出与切片 | ReportBuilder（MVP 固定报表） |
| Todos | 审批+跟进提醒 | ApprovalCard、TodoList |
| Settings/* | 配置与审计 | TreeOrg、PermissionMatrix、StageEditor、AuditTable |

### 3.3 布局与体验约束（对齐 NFR）

- **关键路径 ≤ 3 次主点击**：侧栏「新建线索」→ 表单保存；详情页内「写跟进」「推进阶段」一级按钮。  
- **列表**：服务端分页 + 列设置；敏感列按 field_permission 掩码（如手机 `138****0000`）。  
- **空状态**：无数据引导「新建 / 从公海领取 / 导入」。  
- **全局**：顶栏搜索（客户/线索/商机）、通知铃铛、当前用户。  
- **响应式**：表格在窄屏降级为卡片列表；详情双栏变单栏。

### 3.4 前端模块划分（建议）

```
src/
  app/          # 路由、布局、权限守卫
  features/
    auth/
    leads/
    accounts/
    opportunities/
    activities/
    targets/
    dashboard/
    settings/
    todos/
  shared/       # DataTable、FilterBar、Timeline、Upload、Charts
  api/          # 与第二节契约一一对应的 client
```

状态：服务端状态以 API 缓存库（React Query / SWR 等）为主；跨页 UI 状态（侧栏折叠等）本地 store。

### 3.5 角色 × 默认落地页

| 角色 | 默认首页 | 侧重菜单 |
|------|----------|----------|
| 销售代表 | 我的待办 / 线索 | 线索、客户、商机 |
| 销售经理/总监 | Dashboard | 看板、目标、团队商机 |
| 市场专员 | 线索列表 | 导入、分配、活动（二期） |
| 客服 | 工单（二期）/ 客户 | 客户、工单 |
| 财务对接人 | 合同列表（二期） | 合同、回款只读/半写 |
| 只读观察者 | Dashboard | 报表，无写按钮 |
| 系统管理员 | 组织设置 | Settings 全量 |

---

## 4. 安全与审计设计要点

1. API 层先鉴权再校验数据范围，禁止仅靠前端藏按钮。  
2. 导出统一走 `/reports/export`，写 `export_audit`。  
3. 金额、手机号等字段：列表/详情/导出三处统一脱敏策略。  
4. 审批与阶段回退、合同作废等写 `audit_log`（before/after）。  
5. 登录失败计数与锁定；JWT 过期可配置；主动登出写 `token_blacklist`（可选）。  
6. SQLite 库文件与附件目录权限收紧；备份时拷贝库文件 + WAL/SHM（或先 `VACUUM INTO` / 在线 backup API）。

---

## 5. 落地顺序建议（研发）

1. Python 工程骨架（FastAPI + SQLAlchemy + SQLite WAL）+ 租户/用户/RBAC + 审计  
2. 线索 CRUD + 导入任务（DB 状态机 + 进程内 Worker）+ 分配  
3. 客户/联系人 + 跟进时间线  
4. 商机管道 + 赢输结案  
5. 公海规则 + 配额（事务内计数，无 Redis）  
6. 目标与 Dashboard  
7. 二期：合同回款、工单、活动、开放 API

---

## 6. 文档追溯

| 需求章节 | 设计落点 |
|----------|----------|
| §1 角色与权限 | Schema 1.3.1；API 2.2–2.3；前端菜单守卫 3.1 |
| §2 UC-01…09 | API 2.14；页面 3.2 |
| §3 功能列表 | Schema 1.3.2–1.3.12；API 2.4–2.13 |
| §4 NFR | 总览 0.1（Python/SQLite）；安全 §4；列表性能靠索引+分页 |
| §5 MVP 边界 | 0.2 分期；二期表/路由标注 |
| §6 验收要点 | 可用 2.14 + 页面角色矩阵做测试清单 |

---

*本设计为产品/研发基线（Python + SQLite，无 Redis）。表字段与接口可在详细设计阶段按迭代微调，但对象边界与状态机应保持稳定。*
