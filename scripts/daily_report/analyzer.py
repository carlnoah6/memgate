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
        "严禁编造数据：只能使用明确提供的数据进行分析，不得推断或虚构任何事件、数字或事实。"
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
        # 代码审查已禁用（kimi-k2.5 审查速度太慢，会超时）
        log("  ⏭️ 代码审查已跳过")
        self.file_reviews = {}
        self._skipped_files = []
        # self._review_files()  # 已禁用
        self._cross_module_analysis()
        self._time_allocation()
        self._reflection()
        self._memory_leak_check()
        log("🤖 LLM 分析完成")

    def _review_file_chunks(self, path: str, content: str) -> str:
        """分块审查大文件，每块最多 5000 字符"""
        CHUNK_SIZE = 5000
        OVERLAP = 200  # 块间重叠，避免边界遗漏

        if len(content) <= CHUNK_SIZE:
            # 小文件直接审查
            return self._call_review_llm(path, content, is_chunk=False)

        # 超大文件跳过详细审查（只返回统计）
        if len(content) > 50000:
            log(f"    📄 文件过大 ({len(content)} 字符)，跳过详细审查")
            return f"[文件过大，仅统计: {len(content)} 字符，{content.count(chr(10))} 行]"

        # 大文件分块审查
        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(content):
            end = min(start + CHUNK_SIZE, len(content))
            # 尝试在换行处截断
            if end < len(content):
                next_newline = content.find('\n', end - 30, end + 30)
                if next_newline != -1:
                    end = next_newline + 1

            chunk = content[start:end]
            chunks.append((chunk_idx, chunk))
            chunk_idx += 1
            start = end - OVERLAP if end < len(content) else end

        log(f"    📄 文件较大 ({len(content)} 字符)，分成 {len(chunks)} 块审查")

        # 分别审查每块（带超时保护）
        chunk_reviews = []
        for idx, chunk in chunks:
            log(f"    📄   块 {idx+1}/{len(chunks)}...")
            review = self._call_review_llm(
                path, chunk, is_chunk=True,
                chunk_idx=idx, total_chunks=len(chunks)
            )
            if review.startswith("[LLM"):
                # 超时或失败，跳过这块
                log(f"    ⚠️   块 {idx+1} 审查失败，跳过")
                continue
            chunk_reviews.append(f"## 第 {idx+1} 块\n{review}")

        # 如果没有成功审查的块，返回提示
        if not chunk_reviews:
            return "[代码审查超时，未获取结果]"

        # 合并审查结果
        if len(chunk_reviews) == 1:
            return chunk_reviews[0]

        merge_prompt = f"""以下是文件 `{path}` 的分块审查结果，请合并为一份完整的审查报告。

{chr(10).join(chunk_reviews)}

请合并以上分块审查结果，去除重复问题，生成一份完整的审查报告：
1. **缺陷/Bug**: 列出所有发现的问题（去重）
2. **安全风险**: 安全问题汇总
3. **代码质量**: 质量问题汇总
4. **可改进处**: 重构建议（最重要的 3 条）
5. **总结**: 缺陷 X 个，安全问题 X 个

格式要求：
- 每个问题用 • 开头
- 标注严重程度 [🔴高/🟡中/🟢低]"""

        return call_llm(merge_prompt, max_tokens=2000, system=self.SYSTEM_PROMPT, timeout=60)

    def _call_review_llm(self, path: str, content: str, is_chunk: bool = False,
                         chunk_idx: int = 0, total_chunks: int = 1) -> str:
        """调用 LLM 审查代码块（使用 kimi-k2.5）"""
        chunk_info = f" (第 {chunk_idx+1}/{total_chunks} 块)" if is_chunk else ""

        prompt = f"""请对以下代码文件{chunk_info}进行审查。

文件路径: {path}
代码内容:
```
{content}
```

请从以下维度审查（只报告发现的问题，没问题的维度跳过）：

1. **缺陷/Bug**: 逻辑错误、边界条件、异常处理缺失
2. **安全风险**: 硬编码密钥、路径遍历、注入风险、权限问题
3. **代码质量**: 冗余代码、命名不清晰、硬编码魔法值
4. **可改进处**: 具体的重构建议（简短）

格式要求：
- 每个问题用 • 开头
- 标注严重程度 [🔴高/🟡中/🟢低]
- 如果代码没有明显问题，回复"无明显问题"即可"""

        # 使用默认模型 kimi-k2.5 进行代码审查
        return call_llm(prompt, max_tokens=1500, system=self.SYSTEM_PROMPT, timeout=60)

    def _review_files(self):
        """逐文件 Code Review（大文件自动分块）"""
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
            log(f"  📝 [{i+1}/{len(sorted_files)}] 审查 {path} ({len(content)} 字符)...")

            # 使用分块审查
            review = self._review_file_chunks(path, content)
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
        """时间分配分析 — 纯日历数据驱动，禁止编造"""
        log("  ⏰ 时间分配分析...")

        # 检查日历数据是否可用
        has_error = any(e.get("error") for e in self.data.calendar_events)
        has_events = self.data.calendar_events and not has_error

        if not has_events:
            # 日历为空或 API 失败 → 直接输出，不调 LLM
            auth_url = ""
            error_msg = ""
            for e in self.data.calendar_events:
                if e.get("error"):
                    error_msg = e["error"]
                    if e.get("auth_url"):
                        auth_url = e["auth_url"]
                    break
            if auth_url:
                self.time_analysis = f"⚠️ 无日历数据（{error_msg}）\n授权链接: {auth_url}"
            elif error_msg:
                self.time_analysis = f"⚠️ 无日历数据（{error_msg}）"
            else:
                self.time_analysis = "⚠️ 无日历数据（当天无日历事件）"
            log(f"  ⏰ {self.time_analysis}")
            return

        # 有日历事件 → 构建事件文本
        cal_text = ""
        for evt in self.data.calendar_events:
            cal_text += (f"• {evt.get('start', '?')}-{evt.get('end', '?')} "
                         f"{evt.get('summary', '无标题')}\n")

        # 加载分类定义
        categories = read_file(f"{WORKSPACE}/data/calendar-categories.md", max_lines=30)

        # 日期和星期由代码传入，LLM 不需要自己计算
        prompt = f"""分析以下日历事件的时间分配。

日期: {self.data.date_str}（{self.data.day_name}）— 此日期由系统提供，请直接使用，不要自行计算。

日历事件（共 {len(self.data.calendar_events)} 个）：
{cal_text}

分类参考：
{categories[:1500]}

⚠️ 严格规则：
- 只能分析上面列出的日历事件，禁止编造、推断或添加任何未列出的事件
- 如果某个时段没有日历事件，不要猜测该时段的活动
- 时长计算必须基于事件的开始和结束时间

请：
1. 按分类统计时间（用 emoji + 分类名 + 时长）
2. 列出主要活动
3. 一句话总结时间分配特点"""

        self.time_analysis = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT, timeout=120)

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

        self.memory_check = call_llm(prompt, max_tokens=2000, system=self.SYSTEM_PROMPT, timeout=120)
