# Privacy Guard 通用插件化设计

## 1. 背景
目前 Privacy Guard 是一个独立运行的 Python 脚本 (`scripts/privacy-check.py`)，通过 CLI 方式被 Agent 调用。为了提升通用性和集成度，我们将其重构为 OpenClaw 的标准 TypeScript 插件 (`openclaw-plugin-privacy-guard`)。

## 2. 架构设计

插件遵循 OpenClaw 的生命周期钩子（Lifecycle Hooks）设计，介入 Agent 的感知、思考和行动阶段。

### 核心模块
1.  **Context Injector (上下文注入)**
    *   **阶段**: Session Start / Context Loading
    *   **功能**: 根据当前会话类型（私聊/群聊）和参与者，注入 System Prompt。
    *   **逻辑**:
        *   私聊 (DM) -> 允许访问所有 Public + Private 知识。
        *   群聊 (Group) -> 仅允许访问参与者的 Public 知识，严禁 Private。

2.  **Memory Filter (记忆过滤器)**
    *   **阶段**: Tool Execution (memory_search)
    *   **功能**: 拦截知识库搜索工具的返回结果，过滤掉当前上下文无权访问的文件路径。
    *   **逻辑**: 检查文件路径是否包含 `private.jsonl` 且当前环境为 Group。

3.  **Output Reviewer (输出审查器)**
    *   **阶段**: Agent Response (Pre-send)
    *   **功能**: 在消息发送给用户前进行正则匹配和实体检测。
    *   **逻辑**:
        *   Regex Layer: 扫描手机号、邮箱、金融关键词、日程关键词。
        *   Entity Layer: (高级) 扫描知识库中定义的私有实体名称。

## 3. 核心接口定义 (TypeScript)

```typescript
export interface PrivacyGuardConfig {
  knowledgePath: string; // 知识库根目录
  patterns?: Record<string, { description: string; patterns: string[] }>;
  enabled?: boolean;
}

export interface SessionContext {
  channelType: 'dm' | 'group';
  participants: string[]; // User IDs
}

export interface PluginHooks {
  onSessionStart(context: SessionContext): string; // 返回 System Prompt 片段
  onToolResult(toolName: string, result: any, context: SessionContext): any; // 过滤工具结果
  onOutput(message: string, context: SessionContext): Promise<ReviewResult>; // 审查输出
}
```

## 4. 目录结构

```text
openclaw-plugin-privacy-guard/
├── package.json          # 依赖与元数据
├── tsconfig.json         # TS 配置
├── README.md             # 使用文档
└── src/
    ├── index.ts          # 插件入口类
    ├── config.ts         # 配置加载
    ├── context.ts        # 上下文逻辑
    ├── reviewer.ts       # 正则与审查逻辑
    └── utils.ts          # 工具函数
```

## 5. 迁移策略

1.  **逻辑移植**: 将 `privacy/privacy_context.py` 的逻辑移植到 `src/context.ts`。
2.  **正则库迁移**: 将 `privacy/patterns/` 下的 JSON 规则转换为 TS 对象或独立 JSON 资源。
3.  **测试**: 编写 Jest 测试用例，模拟 DM 和 Group 场景，验证 Prompt 注入和结果过滤是否符合预期。
4.  **发布**: 发布到 npm registry 或作为本地 git submodule 引入 OpenClaw。

## 6. 使用示例

```typescript
const privacyGuard = new PrivacyGuardPlugin({
  knowledgePath: '/data/knowledge',
  enabled: true
});

// Agent 初始化时注册
agent.use(privacyGuard);
```
