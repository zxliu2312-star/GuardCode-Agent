# Review 记录

记录开发过程中用户 review 发现的问题、设计决策变更和改进意见。
每条记录包含：问题描述、原始方案、用户意见、最终修改。

---

## 1. Windows 路径分隔符导致测试失败

- **类型**：硬性 Bug
- **时间**：Phase 1 - 1.5 文件操作工具
- **问题**：`test_list_subdirectory` 断言 `"src/main.py" in result`，但 Windows 返回 `"src\\main.py"`
- **原始方案**：精确匹配路径字符串
- **用户意见**：无（测试失败自动发现）
- **最终修改**：改为 `any("main.py" in item for item in result["result"])`，兼容两种分隔符

---

## 2. Git 邮箱隐私

- **类型**：用户习惯
- **时间**：Phase 1 初期
- **问题**：Git 提交使用学校邮箱，可能暴露个人信息
- **原始方案**：用学校邮箱配置 git
- **用户意见**：GitHub 本身实名注册，导师不会特意查提交者邮箱，但同意改为 noreply
- **最终修改**：改为 GitHub noreply 邮箱

---

## 3. Agent 循环终止条件讨论

- **类型**：设计讨论
- **时间**：Phase 1 - 1.8 Agent 核心循环
- **问题**：用户质疑"没有 tool_calls 就认为任务完成"是否可靠
- **原始方案**：`if not response["tool_calls"]: return content`
- **用户意见**：会不会有任务没完成但工具不足所以不调用的情况？
- **讨论结论**：分析了 5 种情况，确认"没有 tool_calls 就终止"在工程上合理，因为有 max_iterations 和 consecutive_failures 兜底
- **最终修改**：保持原设计，但补充了 `finish_reason` 字段做双保险

---

## 4. finish_reason 冗余判断

- **类型**：代码优化
- **时间**：Phase 1 - 1.8
- **问题**：`if response["finish_reason"] == "stop" and not response["tool_calls"]` 中 `and not` 是冗余的
- **原始方案**：加双保险判断
- **用户意见**：追问 OpenAI API 是否可能同时返回 stop 和 tool_calls
- **讨论结论**：OpenAI API 中 finish_reason 和 tool_calls 互斥，`and not` 是冗余但无害
- **最终修改**：保留冗余判断作为防御性编程，防止非标准 API 不遵守约定

---

## 5. execute_tool fail-open 安全隐患

- **类型**：安全设计
- **时间**：Phase 2 - 2.4 集成风险判定
- **问题**：`execute_tool` 不传 config 时跳过所有安全检查（fail-open）
- **原始方案**：`if config is not None:` 才检查风险
- **用户意见**：不传 config 会不会成为安全隐患？
- **讨论结论**：fail-open 是安全反模式，应改为 fail-safe
- **最终修改**：改为始终执行风险检查，config 为 None 时用空配置，classify_risk 对未知操作默认判为 DANGEROUS

---

## 6. 配置优先级：JSON > 环境变量

- **类型**：设计决策变更
- **时间**：Phase 2 - 2.4 之后
- **问题**：环境变量优先级高于 `.guardcode.json`，导致旧 key 覆盖新 key
- **原始方案**：环境变量最高优先级（标准做法）
- **用户意见**：建议改优先级，JSON 配置文件优先，方便项目级定制化
- **讨论结论**：项目级配置应该覆盖环境变量，这样别人 clone 项目后直接能用
- **最终修改**：优先级改为 默认 < 全局配置 < 环境变量 < 项目配置 < 命令行 --config

---

## 7. 静态扫描定位为 PoC

- **类型**：答辩策略
- **时间**：Phase 2 - 2.5/2.6
- **问题**：正则匹配不够全面，只检测 Python，没有沙箱测试
- **用户意见**：答辩时说"只是提出了思想和倾向，扩展方式有很多"是否可行？
- **讨论结论**：完全可行。创新点在"写入前检查"的流程，不在扫描引擎本身。扫描器可插拔，后续可替换为 Bandit/Semgrep
- **最终修改**：无代码修改，确认答辩话术

---

## 8. Web 前端可行性

- **类型**：项目规划
- **时间**：Phase 2 完成后
- **问题**：助手认为 Web 前端不可能在截止日期前完成
- **用户意见**：前端完全交给 AI 生成，以能用正确为核心目标，完全没问题
- **讨论结论**：用户正确，核心逻辑已全部就绪，前端只是 UI 层，AI 生成半天到一天足够
- **最终修改**：调整评估，开始规划 Web 前端实现

---

## 9. 上下文压缩：从逐轮压缩到两级架构

- **类型**：架构重构
- **时间**：Phase 3 - 3.2 设计阶段
- **问题**：助手第一版实现"逐轮压缩"（每轮工具执行后都压缩），理解有偏差：
  - 缺少写后失效（Write Invalidation）——核心功能缺失
  - 缺少按需重读（Lazy Re-reading）——只做了简单截断
  - 压缩时机错误——每轮后压缩而非阈值触发
  - 没有三层架构概念（Execution State / Context / Workspace）
  - 没有修改 `_format_tool_result()` 增加工具元信息
  - 压缩标记用内容字符串检测而非 `"compressed": True` 字段
- **原始方案**：逐轮即时压缩，纯规则，每轮后调用 `compress_round()`
- **用户意见**：提供完整的 Phase 1 架构审查文档，明确三层架构和两级压缩设计
- **讨论结论**：采用用户的架构设计：
  - 三层架构：Execution State（不可压缩）→ Context/messages（易失性记忆）→ Workspace（Source of Truth）
  - 两级压缩：Level 1 规则压缩（写后失效 + 按需重读 + 工作集保留）+ Level 2 LLM 摘要（可选）
  - 压缩时机：下一轮调用模型前检查 `should_compress()` 阈值触发
  - 前置修改：`_format_tool_result()` 增加 `tool_name` 参数和规范化路径
  - 无 File Cache 层：依赖操作系统页缓存
  - 幂等性：content JSON 中 `"compressed": True` 标记
- **最终修改**：
  - 用 `git revert` 回退第一版实现（保留完整提交历史）
  - 重写 PLAN.md Phase 3 为两级压缩架构
  - 重写 TASKS.md Phase 3 任务清单（3.2 前置修改 → 3.3 Level 1 → 3.4 Level 2 → 3.5 集成）
  - 重写 SPEC.md 4.5 节（修复编码 + 三层架构 + 两级压缩 + 6 个子节）
  - SPEC.md 目录结构 `summarizer.py` → `compressor.py`
