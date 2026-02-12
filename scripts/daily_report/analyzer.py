import os
from . import config
from .config import log, call_llm, read_file, WORKSPACE, REVIEWABLE_EXTS, MAX_REVIEW_FILES
from .data_collector import DataCollector

# ════════════════════════════════════════════════════════════════════
# 阶段 2：分步调用 LLM（代码控制循环）
# ════════════════════════════════════════════════════════════════════

class LLMAnalyzer:
    """分步调用 LLM 进行智能分析"""

    SYSTEM_PROMPT = (
        "你是 Luna 的代码审查和分析引擎。请用简洁中文回答。"
        "使用 • 列表格式，数字大于 1000 用 K/M 缩写。"
        "不要使用 markdown 表格（目标平台不支持）。"
    )

    def __init__(self, data: DataCollector, max_review_files: int = MAX_REVIEW_FILES):
        self.data = data
        self.max_review_files = max_review_files
        self.file_reviews = {}     # path -> review text
        self.cross_module = ""
        self.time_analysis = ""
        self.reflection = ""
        self.memory_check = ""
        self._skipped_files = []

    def analyze_all(self):
        """执行所有 LLM 分析步骤"""
        log("🤖 阶段 2: LLM 分析开始")
        self._review_files()
        self._cross_module_analysis()
        self._time_allocation()
        self._reflection()
        self._memory_leak_check()
        log("🤖 LLM 分析完成")

    def _review_files(self):
        """逐文件 Code Review"""
        code_files = {p: c for p, c in self.data.modified_files.items()
                      if os.path.splitext(p)[1] in REVIEWABLE_EXTS}

        if not code_files:
            log("  📝 没有代码文件需要审查")
            return

        # 按文件大小排序，优先审查实质性文件
        sorted_files = sorted(code_files.items(),
                              key=lambda x: len(x[1]), reverse=True)

        if len(sorted_files) > self.max_review_files:
            log(f"  📝 代码文件 {len(sorted_files)} 个超过上限 {self.max_review_files}，"
                f"只审查前 {self.max_review_files} 个")
            self._skipped_files = [p for p, _ in sorted_files[self.max_review_files:]]
            sorted_files = sorted_files[:self.max_review_files]
        else:
            self._skipped_files = []

        log(f"  📝 开始逐文件 Code Review ({len(sorted_files)} 个文件)...")

        for i, (path, content) in enumerate(sorted_files):
            log(f"  📝 [{i+1}/{len(sorted_files)}] 审查 {path}...")

            # 截断过大文件的内容给 LLM
            review_content = content[:15000]
            if len(content) > 15000:
                review_content += "\n[... 内容已截断]"

            prompt = f"""请对以下代码文件进行审查。

文件路径: {path}
文件内容:
```
{review_content}
```

请从以下维度审查（只报告发现的问题，没问题的维度跳过）：

1. **缺陷/Bug**: 逻辑错误、边界条件、异常处理缺失
2. **安全风险**: 硬编码密钥、路径遍历、注入风险、权限问题
3. **代码质量**: 冗余代码、命名不清晰、硬编码魔法值
4. **可改进处**: 具体的重构建议（简短，一句话描述）

格式要求：
- 每个问题用 • 开头
- 标注严重程度 [🔴高/🟡中/🟢低]
- 如果代码没有明显问题，简短说明即可（一行）
- 总结: 缺陷 X 个，安全问题 X 个"""

            review = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)
            self.file_reviews[path] = review

    def _cross_module_analysis(self):
        """跨模块分析"""
        if not self.file_reviews:
            self.cross_module = "无代码文件变更，跳过跨模块分析。"
            return

        log("  🔗 跨模块分析...")
        reviews_text = "\n\n".join(
            f"### {path}\n{review}"
            for path, review in self.file_reviews.items()
        )

        prompt = f"""以下是今天修改的所有代码文件的审查结果：

{reviews_text}

请进行跨模块分析：
1. **重复代码**: 多个文件中是否存在相似的逻辑？可以抽取为公共函数吗？
2. **依赖关系**: 文件间的依赖是否合理？有没有循环依赖？
3. **重构建议**: 最值得改进的 1-3 个方向（具体可操作的建议）
4. **总体评估**: 今天的代码变更质量如何？（一句话总结）

如果文件较少或相互独立，简短说明即可。"""

        self.cross_module = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)

    def _time_allocation(self):
        """时间分配分析"""
        log("  ⏰ 时间分配分析...")

        # 准备日历数据
        cal_text = ""
        if self.data.calendar_events and not any(
            e.get("error") for e in self.data.calendar_events
        ):
            for evt in self.data.calendar_events:
                cal_text += (f"• {evt.get('start', '?')}-{evt.get('end', '?')} "
                             f"{evt.get('summary', '无标题')}\n")
        else:
            cal_text = "⚠️ 日历 API 不可用（token 过期）"

        # 准备 memory 中的活动记录
        memory_excerpt = self.data.memory_content[:5000] if self.data.memory_content else "无 memory 文件"

        # 加载分类定义
        categories = read_file(f"{WORKSPACE}/data/calendar-categories.md", max_lines=30)

        prompt = f"""分析 {self.data.date_str}（{self.data.day_name}）的时间分配。

日历事件：
{cal_text}

当日 memory 记录（前 5000 字）：
{memory_excerpt}

分类参考（来自日历分类体系）：
{categories[:1500]}

请：
1. 按分类统计时间（用 emoji + 分类名 + 估算时长）
2. 列出主要活动
3. 如果日历数据不可用，基于 memory 内容推断主要活动（标注"基于记录推断"）
4. 一句话总结今天的时间分配特点"""

        self.time_analysis = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)

    def _reflection(self):
        """七维度反思"""
        log("  🧠 七维度反思...")

        # 准备工作日志
        memory_text = self.data.memory_content[:8000] if self.data.memory_content else "无 memory 文件"

        # 用户消息摘要（取前 30 条）
        user_msgs = "\n".join(
            f"• {msg[:150]}" for msg in self.data.session_summaries[:30]
        )

        prompt = f"""基于以下 {self.data.date_str}（{self.data.day_name}）的工作记录，进行复盘反思。

Memory 记录：
{memory_text}

用户消息摘要（{len(self.data.session_summaries)} 条）：
{user_msgs or '无用户消息记录'}

请从以下维度反思（每个维度 2-4 个要点，没有内容的维度可跳过）：

1. **📋 今日工作回顾**: 区分主动工作 vs 被动响应
2. **🔧 问题与解法**: 遇到什么困难？怎么解决的？
3. **💡 经验与规律**: 从具体问题中抽象出通用规律（格式：规律: XXX → 因为 YYY → 以后 ZZZ）
4. **🤖 自我进化**: 工具使用效率、响应质量、知识盲区
5. **🔺 信念升级**: 是否有需要写入 SOUL.md 的新规律？"""

        self.reflection = call_llm(prompt, max_tokens=4000, system=self.SYSTEM_PROMPT)

    def _memory_leak_check(self):
        """记忆遗漏检查"""
        log("  🔍 记忆遗漏检查...")

        # 取最近用户消息
        user_msgs = "\n".join(
            f"• {msg[:200]}" for msg in self.data.session_summaries[:50]
        )

        if not user_msgs:
            self.memory_check = "无用户消息记录，跳过遗漏检查。"
            return

        memory_text = self.data.memory_content[:5000] if self.data.memory_content else "无 memory 文件"

        prompt = f"""检查以下用户消息中是否有重要信息未被持久化到 memory 文件中。

用户消息（{self.data.date_str}）：
{user_msgs}

当日 Memory 文件内容（前 5000 字）：
{memory_text}

请检查：
1. 是否有用户提到的重要信息（人名、地点、日期、偏好、决定）未被记录？
2. 是否有 TODO/承诺未被追踪？
3. 每个遗漏用 • ⚠️ 标注

如果所有重要信息已持久化，说明 "遗漏检测: 0 条"。"""

        self.memory_check = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT)
