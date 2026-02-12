# Kimi (Moonshot) API 消费监控方案研究报告

## 研究任务
研究 Kimi (Moonshot) API 的消费监控方案，获取每日消耗金额、余额和 Token 消耗信息。

---

## 一、官方 API 端点分析

### 1.1 基础信息
| 项目 | 内容 |
|------|------|
| **中国端点** | `https://api.moonshot.cn/v1` |
| **国际端点** | `https://api.moonshot.ai/v1` |
| **Coding 端点** | `https://api.kimi.com/coding/v1` |
| **认证方式** | `Authorization: Bearer {API_KEY}` |
| **协议** | OpenAI 兼容格式 |

### 1.2 标准 API 端点列表
| 端点 | 方法 | 功能 |
|------|------|------|
| `/v1/models` | GET | 获取可用模型列表 |
| `/v1/chat/completions` | POST | 聊天完成 |
| `/v1/files` | POST/GET/DELETE | 文件管理 |
| `/v1/embeddings` | POST | 文本嵌入 |

### 1.3 关于余额/用量查询 API
**⚠️ 重要发现**: 经过全面搜索，**Kimi 官方目前没有提供直接的余额或用量查询 API 端点**（如 `/v1/balance` 或 `/v1/usage`）。

官方文档中提到的 `/docs/api/balance` 页面存在，但主要用于展示计费说明，而非提供程序化查询接口。

---

## 二、官网后台功能

### 2.1 控制台地址
- **主控制台**: https://platform.moonshot.cn/
- **API Keys 管理**: https://platform.moonshot.cn/console/api-keys
- **充值中心**: https://platform.moonshot.cn/console/pay

### 2.2 后台可查看的信息
登录官网后台后，可以查看：
1. **账户余额** - 当前剩余金额（元）
2. **消费记录** - 历史充值和使用记录
3. **API Key 管理** - 创建、删除、查看 Key
4. **限速信息** - 当前账户的速率限制

### 2.3 计费模式
- **预付费模式**: 需要先充值后使用
- **新用户福利**: 注册赠送 15 元代金券
- **计费单位**: 按千 tokens 计费
- **最低充值**: Tier 0 从 $1 起充

---

## 三、Token 用量监控方案

### 3.1 方案一：实时获取用量（推荐）
Kimi API 的响应中**已包含 Token 用量信息**，可以在每次调用时实时记录：

#### API 响应示例
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "kimi-k2-0711",
  "choices": [...],
  "usage": {
    "prompt_tokens": 137,
    "completion_tokens": 914,
    "total_tokens": 1051
  }
}
```

#### Python 监控脚本示例
```python
import json
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="https://api.moonshot.cn/v1"
)

def chat_with_monitoring(message):
    response = client.chat.completions.create(
        model="kimi-k2-0711",
        messages=[{"role": "user", "content": message}]
    )
    
    # 提取用量信息
    usage = response.usage
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "model": response.model
    }
    
    # 保存到日志文件或数据库
    with open("kimi_usage_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return response.choices[0].message.content

# 定期统计
def daily_summary():
    # 读取日志并计算每日用量
    pass
```

**优点**:
- 实时获取，数据准确
- 无需额外认证
- 可自定义统计维度

**缺点**:
- 需要拦截 API 调用
- 无法获取历史数据
- 无法获取账户余额

---

### 3.2 方案二：浏览器自动化获取余额（可行）
由于官网后台提供了完整的余额和消费信息，可以使用浏览器自动化工具（如 Playwright/Selenium）定期登录获取。

#### 实现思路
```python
from playwright.sync_api import sync_playwright

def get_kimi_balance():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # 登录
        page.goto("https://platform.moonshot.cn/")
        page.fill("input[name='phone']", "your-phone")
        page.fill("input[name='code']", "sms-code")  # 需要处理短信验证码
        page.click("button[type='submit']")
        
        # 等待登录完成并获取余额
        page.wait_for_selector(".balance-display")
        balance = page.inner_text(".balance-display")
        
        browser.close()
        return balance
```

**优点**:
- 可以获取账户余额
- 可以获取消费记录

**缺点**:
- 需要处理短信验证码（中国手机号）
- 页面结构变化会导致脚本失效
- 需要定期维护
- 有被封禁风险

---

### 3.3 方案三：邮件/消息提醒（简单方案）
设置定期提醒，手动登录后台查看余额和用量。

#### 实现方式
```bash
# 使用 cron 定时提醒
0 9 * * * /usr/local/bin/send-notification.sh "记得检查 Kimi API 余额"
```

**优点**:
- 实现简单
- 无需技术开发

**缺点**:
- 需要人工操作
- 无法实现自动化监控

---

## 四、价格参考（当前）

| 模型 | 输入价格 (元/百万 tokens) | 输出价格 (元/百万 tokens) |
|------|------------------------|------------------------|
| Kimi K2 | ~6 | ~25 |
| Kimi K2 Thinking | ~12 | ~50 |
| Context Caching | 24/百万 tokens | - |

> 注：价格可能变动，请以官方最新定价为准。

---

## 五、推荐实现方案

### 综合方案：API 用量拦截 + 定期人工检查

1. **API 用量监控**
   - 封装 Kimi API 调用，自动记录 Token 用量
   - 每日生成用量报告
   - 设置用量阈值提醒

2. **余额监控**
   - 设置每周提醒，人工登录后台查看余额
   - 或使用浏览器自动化（如验证码问题可解决）

3. **预警机制**
   - Token 用量异常增长时发送提醒
   - 余额低于阈值时提醒充值

---

## 六、结论

| 功能 | API 支持 | 备注 |
|------|----------|------|
| **实时 Token 用量** | ✅ 支持 | 在 API 响应中 |
| **账户余额查询** | ❌ 不支持 | 需登录后台或浏览器自动化 |
| **消费记录查询** | ❌ 不支持 | 需登录后台 |
| **历史用量统计** | ❌ 不支持 | 需自行记录 |

**最终建议**:
1. 在应用层封装 Kimi API，实时记录 Token 用量
2. 定期（如每周）人工登录后台查看余额
3. 如需自动化余额查询，可考虑浏览器自动化方案（需处理验证码）

---

## 参考链接
- 官方平台：https://platform.moonshot.cn/
- API 文档：https://platform.moonshot.cn/docs/guide/start-using-kimi-api
- 定价页面：https://platform.moonshot.cn/docs/pricing/chat
- 充值与限速：https://platform.moonshot.cn/docs/pricing/limits

---

*报告生成时间: 2026-02-12*
*任务 ID: tid-0212-26*
