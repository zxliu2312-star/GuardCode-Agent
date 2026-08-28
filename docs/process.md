# (cursor claude-sonnet-4-6)
## prompt:
/add-plugin superpowers

我想构建一个编程智能体（coding agent），项目名叫 GuardCode Agent。

背景：这是南京大学软件学院预推免考核项目。要求从零自己实现一个编程智能体，
通过与大语言模型交互，能自主读写文件、执行命令，完成编程任务。
类似简化的 Claude Code / Codex / OpenCode。

硬性约束：
1. 不允许使用任何 agent 框架/SDK（LangChain、LlamaIndex、OpenAI Agents SDK、
   Claude Agent SDK、AutoGen、CrewAI 等）
2. 允许使用模型厂商的 API 客户端库和原生 tool calling 接口
3. 不得依赖 API 服务端托管的代码执行或文件工具
4. 以下逻辑必须自己实现：对话历史与上下文管理、工具定义与本地执行、
   模型输出解析、循环终止条件、错误处理

我的定位：面向可信软件开发的编程智能体，在基础代码生成之上加入：
- 安全检查（静态风险检测，轻量级规则匹配即可）
- 执行反馈（测试驱动修复，跑测试 → 看结果 → 修正）

我希望项目小而精：核心功能完整可用，不堆砌功能。编程语言用 Python。
API key 通过环境变量提供。

请帮我 brainstorm 这个项目的设计。

## answer:

