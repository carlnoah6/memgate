# Lark/飞书 API 最佳实践：批量操作、性能优化、错误处理

> 研究日期：2026-02-08
> 来源：飞书开放平台官方文档、官方 SDK 源码、社区实践
> 目的：为集成飞书 API 的系统提供可执行的工程指南

---

## 一、批量操作策略

### 1.1 飞书原生 Batch API 汇总

飞书为高频场景提供了原生批量接口，**应优先使用这些 batch 接口而非循环单条调用**：

| 模块 | 批量接口 | 单次上限 | 频控等级 |
|------|---------|---------|---------|
| 多维表格 (Bitable) | `batch_create` 批量创建记录 | 500 条/次 | 等级 4 (1000次/分, 50次/秒) |
| 多维表格 (Bitable) | `batch_update` 批量更新记录 | 500 条/次 | 等级 4 |
| 多维表格 (Bitable) | `batch_delete` 批量删除记录 | 500 条/次 | 等级 4 |
| 多维表格 (Bitable) | `batch_create` 批量创建数据表 | - | 等级 4 |
| 消息 (IM) | `batch_send` 批量发送消息 | 200 用户/次 | 特殊频控 |
| 通讯录 (Contact) | 批量获取用户信息 | 50 用户/次 | 等级 7 |
| 文档 (Docx) | `batch_update` 批量更新文档块 | 多个 block 操作 | 等级 4 |

**实操建议：**

```typescript
// ❌ 错误做法：循环单条创建
for (const record of records) {
  await client.bitable.appTableRecord.create({ data: { fields: record } });
}

// ✅ 正确做法：分批使用 batch_create
const BATCH_SIZE = 500;
for (let i = 0; i < records.length; i += BATCH_SIZE) {
  const batch = records.slice(i, i + BATCH_SIZE);
  await client.bitable.appTableRecord.batchCreate({
    path: { app_token, table_id },
    data: { records: batch.map(r => ({ fields: r })) }
  });
}
```

### 1.2 分页查询策略

飞书 API 分页查询使用 `page_token` + `has_more` 模式。关键参数：

- `page_size`：每页返回条数（通常 10-500，默认 20）
- `page_token`：分页标记，首页为空字符串
- `has_more`：是否还有更多数据

**三种分页遍历方式（以 Python 为例）：**

```python
# 方式一：while 循环（推荐，最清晰）
page_token = ""
all_records = []
while True:
    resp = client.bitable.v1.app_table_record.list(
        app_token=app_token,
        table_id=table_id,
        page_size=500,
        page_token=page_token
    )
    all_records.extend(resp.data.items)
    if not resp.data.has_more:
        break
    page_token = resp.data.page_token

# 方式二：使用官方 SDK 迭代器（Node.js SDK 推荐）
# SDK 内置 listWithIterator 方法自动处理分页
for await (const items of await client.contact.user.listWithIterator({
    params: { department_id: '0', page_size: 20 }
})) {
    console.log(items);
}
```

**分页最佳实践：**

1. **page_size 尽量设大**：减少请求次数，通常设为接口允许的最大值（如 500）
2. **不要并发分页**：分页是串行依赖的（下一页的 token 来自上一页），不要尝试并发分页
3. **注意数据一致性**：分页过程中数据可能变化（新增/删除），对一致性要求高的场景应在业务层做去重
4. **page_token 有时效性**：不要长时间缓存 page_token，获取后尽快使用

### 1.3 无原生 Batch API 时的批量策略

对于没有原生 batch 接口的操作（如单条发送消息、单个创建日历事件），需要自行实现批量：

```typescript
// 受控并发批量执行
async function batchExecute<T, R>(
  items: T[],
  fn: (item: T) => Promise<R>,
  concurrency: number = 5,
  delayMs: number = 100
): Promise<R[]> {
  const results: R[] = [];
  for (let i = 0; i < items.length; i += concurrency) {
    const batch = items.slice(i, i + concurrency);
    const batchResults = await Promise.all(batch.map(fn));
    results.push(...batchResults);
    if (i + concurrency < items.length) {
      await sleep(delayMs); // 控制速率，避免触发频控
    }
  }
  return results;
}
```

---

## 二、性能优化

### 2.1 Token 缓存策略

飞书的访问凭证体系：

| Token 类型 | 有效期 | 获取方式 | 适用场景 |
|-----------|--------|---------|---------|
| `app_access_token` | 2 小时 | app_id + app_secret | 应用级操作 |
| `tenant_access_token` | 2 小时 | app_id + app_secret (自建) | 租户级操作（最常用） |
| `user_access_token` | ~6900 秒 (~1.9h) | OAuth 授权码 | 用户级操作 |

**Token 缓存关键规则：**

1. **有效期内重复获取返回相同 token**：不会生成新 token
2. **剩余有效期 < 30 分钟时获取，返回新 token**，但旧 token 仍有效直到过期
3. **官方 SDK 内置 token 缓存**：`@larksuiteoapi/node-sdk` 默认自动缓存 token
4. **可自定义缓存器**：SDK 支持传入 `cache` 参数实现 Redis 等外部缓存

```typescript
// 官方 Node.js SDK 自动管理 token 缓存
const client = new lark.Client({
  appId: 'xxx',
  appSecret: 'xxx',
  // disableTokenCache: false  // 默认启用缓存
});

// 自定义缓存（适用于多实例/分布式场景）
const client = new lark.Client({
  appId: 'xxx',
  appSecret: 'xxx',
  cache: {
    set: async (key, value, expire) => {
      await redis.set(key, value, 'EX', expire);
    },
    get: async (key) => {
      return await redis.get(key);
    }
  }
});
```

**不使用官方 SDK 时的 Token 管理：**

```typescript
class TokenManager {
  private token: string | null = null;
  private expiresAt: number = 0;
  private refreshing: Promise<string> | null = null;

  async getToken(): Promise<string> {
    // 提前 5 分钟刷新，留出安全边际
    if (this.token && Date.now() < this.expiresAt - 5 * 60 * 1000) {
      return this.token;
    }
    // 防止并发刷新（多个请求同时发现 token 过期）
    if (!this.refreshing) {
      this.refreshing = this.refresh();
    }
    return this.refreshing;
  }

  private async refresh(): Promise<string> {
    try {
      const resp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET })
      });
      const data = await resp.json();
      this.token = data.tenant_access_token;
      this.expiresAt = Date.now() + data.expire * 1000;
      return this.token;
    } finally {
      this.refreshing = null;
    }
  }
}
```

### 2.2 请求合并与并发控制

**原则：在频控限制内最大化吞吐量。**

飞书频控的核心维度是 **每个 API × 每个应用 × 每个租户**。不同 API 的频控等级不同：

- 等级 4（最常见）：1000 次/分 且 50 次/秒
- 等级 7：10 次/秒
- 等级 9：50 次/秒
- 等级 11：100 次/秒

**并发控制器实现：**

```typescript
class RateLimiter {
  private queue: Array<() => void> = [];
  private running = 0;

  constructor(
    private maxPerSecond: number = 40,  // 留 20% 余量
    private maxConcurrent: number = 10
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }

  private acquire(): Promise<void> {
    return new Promise(resolve => {
      if (this.running < this.maxConcurrent) {
        this.running++;
        resolve();
      } else {
        this.queue.push(() => {
          this.running++;
          resolve();
        });
      }
    });
  }

  private release() {
    this.running--;
    // 延迟释放，控制速率
    setTimeout(() => {
      const next = this.queue.shift();
      if (next) next();
    }, 1000 / this.maxPerSecond);
  }
}
```

### 2.3 数据缓存策略

对于读多写少的数据（如用户信息、部门列表），建议加缓存：

```typescript
// 简单的 TTL 缓存
class SimpleCache<T> {
  private cache = new Map<string, { data: T; expiresAt: number }>();

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry || Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }
    return entry.data;
  }

  set(key: string, data: T, ttlMs: number = 300_000) { // 默认 5 分钟
    this.cache.set(key, { data, expiresAt: Date.now() + ttlMs });
  }
}

// 用于缓存用户信息、部门信息等变化频率低的数据
const userCache = new SimpleCache<UserInfo>();
```

**缓存时机建议：**
- 用户信息：TTL 15-30 分钟
- 部门列表：TTL 30-60 分钟
- 日历事件列表：TTL 5-10 分钟（变化频繁）
- 多维表格数据：不建议缓存或 TTL < 1 分钟（可能随时变更）

---

## 三、错误处理与重试

### 3.1 飞书错误码体系

飞书 API 返回结构统一为：
```json
{
  "code": 0,          // 0 表示成功，非 0 表示错误
  "msg": "success",   // 错误描述
  "data": {}          // 业务数据
}
```

**关键错误码分类与处理策略：**

| 错误码 | 含义 | 处理策略 |
|-------|------|---------|
| `0` | 成功 | - |
| `99991400` | 频控限制 (Rate Limit) | 等待 `x-ogw-ratelimit-reset` 秒后重试 |
| `99991663` | tenant_access_token 无效 | 刷新 token 后重试 |
| `99991661` | app_access_token 无效 | 刷新 token 后重试 |
| `20005` | 无效 access_token | 检查 token 是否正确/过期 |
| `20006` | user_access_token 过期 | 用 refresh_token 刷新 |
| `1500` / `2200` / `5000` | 内部服务错误 | 指数退避重试 |
| `11232` / `11233` / `11247` | 消息发送频控 | 等待后重试，避开整点 |
| `4001` | Token 无效 | 刷新 token |
| `9499` / `10003` | 参数错误 | 不重试，修正参数 |

### 3.2 频控限制处理

飞书触发限流时返回 HTTP 429（部分旧接口返回 400），响应头包含：

```
x-ogw-ratelimit-limit: 100    // 窗口期上限
x-ogw-ratelimit-reset: 52     // 恢复时间（秒）
```

**标准处理流程：**

```typescript
async function callWithRateLimitHandling<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fn();
      // 检查业务层错误码
      if (response.code === 99991400) {
        const resetSeconds = response.headers?.['x-ogw-ratelimit-reset'] || 60;
        console.warn(`Rate limited, waiting ${resetSeconds}s...`);
        await sleep(resetSeconds * 1000);
        continue;
      }
      return response;
    } catch (error) {
      if (error.status === 429) {
        const retryAfter = parseInt(error.headers['x-ogw-ratelimit-reset'] || '60');
        await sleep(retryAfter * 1000);
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded for rate limit');
}
```

**频控注意事项：**
- 自定义机器人频控独立：100 次/分钟，5 次/秒
- **避开整点/半点时间**（如 10:00、17:30）发送消息，系统压力大时可能出现 11232 限流
- 写入接口频控通常低于读取接口
- 基础版和商业版的频控等级相同，但可联系 CSM 临时提升

### 3.3 通用重试策略

```typescript
interface RetryConfig {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
  retryableErrors: number[];  // 可重试的飞书错误码
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelayMs: 1000,
  maxDelayMs: 30000,
  retryableErrors: [
    99991400,  // rate limit
    99991663,  // tenant token invalid
    99991661,  // app token invalid
    1500,      // internal error
    2200,      // internal error (频繁调用)
    5000,      // internal error
    10101,     // internal error
  ]
};

async function retryableCall<T>(
  fn: () => Promise<{ code: number; msg: string; data: T }>,
  tokenManager: TokenManager,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<T> {
  let lastError: any;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      const resp = await fn();

      if (resp.code === 0) {
        return resp.data;
      }

      // Token 过期：刷新后立即重试
      if ([99991663, 99991661, 20005, 20006, 4001].includes(resp.code)) {
        await tokenManager.refresh();
        continue;
      }

      // 频控：按响应头等待
      if (resp.code === 99991400) {
        // 理想情况下从响应头读取 x-ogw-ratelimit-reset
        const waitMs = Math.min(
          config.baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000,
          config.maxDelayMs
        );
        await sleep(waitMs);
        continue;
      }

      // 内部错误：指数退避
      if (config.retryableErrors.includes(resp.code)) {
        const waitMs = Math.min(
          config.baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000,
          config.maxDelayMs
        );
        await sleep(waitMs);
        lastError = new Error(`Lark API error ${resp.code}: ${resp.msg}`);
        continue;
      }

      // 不可重试的错误
      throw new Error(`Lark API error ${resp.code}: ${resp.msg}`);

    } catch (error) {
      // 网络错误：指数退避重试
      if (isNetworkError(error) && attempt < config.maxRetries) {
        const waitMs = config.baseDelayMs * Math.pow(2, attempt);
        await sleep(waitMs);
        lastError = error;
        continue;
      }
      throw error;
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

function isNetworkError(error: any): boolean {
  return (
    error.code === 'ECONNRESET' ||
    error.code === 'ETIMEDOUT' ||
    error.code === 'ECONNREFUSED' ||
    error.code === 'ENOTFOUND' ||
    error.message?.includes('socket hang up')
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

### 3.4 错误日志最佳实践

飞书 API 响应头中包含 `x-tt-logid`，这是飞书内部的请求追踪 ID。**在遇到难以排查的错误时，应记录此值并提供给飞书技术支持。**

```typescript
async function callWithLogging(fn: () => Promise<any>): Promise<any> {
  const startTime = Date.now();
  try {
    const resp = await fn();
    const duration = Date.now() - startTime;
    if (resp.code !== 0) {
      console.error('[Lark API Error]', {
        code: resp.code,
        msg: resp.msg,
        logId: resp.headers?.['x-tt-logid'],
        duration,
        timestamp: new Date().toISOString()
      });
    }
    return resp;
  } catch (error) {
    console.error('[Lark API Exception]', {
      error: error.message,
      logId: error.response?.headers?.['x-tt-logid'],
      duration: Date.now() - startTime
    });
    throw error;
  }
}
```

---

## 四、实际场景最佳实践

### 4.1 多维表格批量写入

**场景：** 向 Bitable 批量写入 10,000 条记录

```typescript
async function bulkInsertRecords(
  client: LarkClient,
  appToken: string,
  tableId: string,
  records: Record<string, any>[]
) {
  const BATCH_SIZE = 500;  // 单次上限
  const DELAY_BETWEEN_BATCHES = 200;  // ms，避免频控
  const results = [];

  for (let i = 0; i < records.length; i += BATCH_SIZE) {
    const batch = records.slice(i, i + BATCH_SIZE);
    const resp = await retryableCall(() =>
      client.bitable.appTableRecord.batchCreate({
        path: { app_token: appToken, table_id: tableId },
        data: { records: batch.map(r => ({ fields: r })) }
      })
    );
    results.push(...resp.records);

    // 进度日志
    console.log(`Inserted ${Math.min(i + BATCH_SIZE, records.length)}/${records.length}`);

    // 批次间延迟
    if (i + BATCH_SIZE < records.length) {
      await sleep(DELAY_BETWEEN_BATCHES);
    }
  }

  return results;
}
```

### 4.2 全量数据同步（分页 + 增量）

**场景：** 定期同步 Bitable 数据到本地数据库

```typescript
async function syncAllRecords(
  client: LarkClient,
  appToken: string,
  tableId: string,
  lastSyncTime?: number
) {
  let pageToken = '';
  let allRecords = [];

  // 使用 filter 实现增量同步
  const filter = lastSyncTime
    ? `CurrentValue.[最后修改时间] > ${lastSyncTime}`
    : undefined;

  do {
    const resp = await retryableCall(() =>
      client.bitable.appTableRecord.list({
        path: { app_token: appToken, table_id: tableId },
        params: {
          page_size: 500,
          page_token: pageToken || undefined,
          filter
        }
      })
    );

    allRecords.push(...(resp.items || []));
    pageToken = resp.page_token || '';

    // 串行分页，每页间适当延迟
    if (resp.has_more) {
      await sleep(100);
    }
  } while (pageToken);

  return allRecords;
}
```

### 4.3 批量发送消息

**场景：** 向多个用户发送通知

```typescript
async function batchNotify(
  client: LarkClient,
  userIds: string[],
  content: string
) {
  // 方式一：使用原生 batch_send（最多 200 用户/次）
  if (userIds.length <= 200) {
    return await client.im.message.batchSend({
      data: {
        open_ids: userIds,
        msg_type: 'text',
        content: JSON.stringify({ text: content })
      }
    });
  }

  // 方式二：超过 200 人，分批调用 batch_send
  const BATCH = 200;
  for (let i = 0; i < userIds.length; i += BATCH) {
    const batch = userIds.slice(i, i + BATCH);
    await retryableCall(() =>
      client.im.message.batchSend({
        data: {
          open_ids: batch,
          msg_type: 'text',
          content: JSON.stringify({ text: content })
        }
      })
    );
    await sleep(1000); // batch_send 频控较严，间隔 1 秒
  }
}
```

### 4.4 日历事件查询

```typescript
async function getUpcomingEvents(
  client: LarkClient,
  calendarId: string,
  days: number = 7
) {
  const now = Math.floor(Date.now() / 1000);
  const end = now + days * 86400;

  let pageToken = '';
  let events = [];

  do {
    const resp = await retryableCall(() =>
      client.calendar.calendarEvent.list({
        path: { calendar_id: calendarId },
        params: {
          start_time: String(now),
          end_time: String(end),
          page_size: 500,
          page_token: pageToken || undefined
        }
      })
    );

    events.push(...(resp.items || []));
    pageToken = resp.page_token || '';
  } while (pageToken);

  return events;
}
```

---

## 五、官方 SDK 使用建议

### 5.1 推荐使用官方 SDK

飞书提供了多语言官方 SDK，**强烈建议使用**，已内置以下能力：

| 能力 | 说明 |
|------|------|
| Token 自动管理 | 自动获取、缓存、刷新 token |
| 类型安全 | TypeScript/Java 完整类型支持 |
| 分页迭代器 | `listWithIterator` 自动处理分页 |
| 文件上下传 | 内置文件流处理 |
| 数据加解密 | 事件回调自动解密验签 |

**官方 SDK 列表：**
- Node.js: `@larksuiteoapi/node-sdk` (npm)
- Python: `lark-oapi` (pypi) / `larksuite/oapi-sdk-python` (GitHub)
- Go: `larksuite/oapi-sdk-go`
- Java: `larksuite/oapi-sdk-java`

### 5.2 SDK 高级配置

```typescript
import * as lark from '@larksuiteoapi/node-sdk';
import axios from 'axios';

// 自定义 HTTP 实例（添加超时、拦截器等）
const httpInstance = axios.create({
  timeout: 30000,  // 30 秒超时
});

// 请求拦截器：添加日志
httpInstance.interceptors.request.use(config => {
  console.log(`[Lark] ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

// 响应拦截器：记录 logid
httpInstance.interceptors.response.use(
  response => {
    if (response.data?.code !== 0) {
      console.warn(`[Lark Error] code=${response.data.code} logid=${response.headers['x-tt-logid']}`);
    }
    return response;
  },
  error => {
    console.error(`[Lark HTTP Error] ${error.message} logid=${error.response?.headers?.['x-tt-logid']}`);
    throw error;
  }
);

const client = new lark.Client({
  appId: 'xxx',
  appSecret: 'xxx',
  domain: lark.Domain.Feishu,
  httpInstance,
  loggerLevel: lark.LoggerLevel.warn,
});
```

---

## 六、关键数字速查

| 指标 | 数值 |
|------|------|
| tenant_access_token 有效期 | 2 小时 |
| app_access_token 有效期 | 2 小时 |
| user_access_token 有效期 | ~6900 秒 |
| Token 提前刷新窗口 | 剩余 < 30 分钟开始生成新 token |
| Bitable 批量操作上限 | 500 条/次 |
| 消息批量发送上限 | 200 用户/次 |
| 分页 page_size 通常上限 | 500 |
| 自定义机器人频控 | 100 次/分，5 次/秒 |
| 常见等级 4 频控 | 1000 次/分，50 次/秒 |
| 频控响应码 | HTTP 429 / code 99991400 |
| 推荐并发请求数 | 5-10（保守），30-40（激进） |
| 建议 Token 提前刷新时间 | 过期前 5-10 分钟 |

---

## 七、常见坑与避免方法

1. **Token 不做缓存导致频繁获取**：获取 token 的接口本身也有频控，必须缓存
2. **分页 page_token 缓存太久**：page_token 应即取即用，不要跨请求/跨时间段使用
3. **整点发消息被限流**：10:00、17:30 等时段系统压力大，建议错开 1-2 分钟
4. **不区分可重试和不可重试错误**：参数错误（9499/10003）重试无意义，只有临时性错误才重试
5. **并发太高触发频控**：先查目标 API 的频控等级，留 20% 余量
6. **忽略 x-tt-logid**：这是排查问题的关键，建议所有错误响应都记录此值
7. **商店应用忘传 tenant_key**：商店应用必须在请求时指定 tenant_key
8. **旧版 API 频控返回 400 而非 429**：部分旧接口的频控返回 HTTP 400 + code 99991400，需要同时判断

---

*本文档基于 2026 年 2 月飞书开放平台文档整理，具体频控数值可能随平台更新而变化，请以官方文档为准。*
