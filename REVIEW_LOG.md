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
