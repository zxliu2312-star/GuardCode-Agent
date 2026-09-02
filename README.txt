GuardCode Agent：一款专注可信软件开发的 AI 编程助手，核心特色是上下文压缩和安全防护

Git 仓库地址：https://github.com/zxliu2312-star/GuardCode-Agent

一、如何运行

环境要求：Python 3.10+，需安装 openai、rich 依赖。

命令行模式：
```bash
export OPENAI_API_KEY="your-key"
python -m guardcode "implement quicksort in Python with tests"
```

Web 界面模式：
```bash
cd api && python server.py
cd frontend && npm install && npm start
```

访问 http://localhost:3000，支持 PLAN（先生成计划审批后执行）、WORK（自主执行）、FEEDBACK（关键点暂停）、RESEARCH（只读调查）四种工作模式。

二、特色功能

1. 上下文压缩机制
针对长对话 token 快速消耗的痛点，实现三种自创压缩策略：写后失效（write_file 后旧 read_file 结果标记过期）、按需重读（大型结果压缩为元信息）、工作集保留（最近5轮完整）。量化实验显示平均 35.4% 压缩率，文件密集场景最高 65.2%，耗时仅 0.26ms。

2. 安全防护机制
针对误执行危险脚本的风险，实现三层防护：路径校验（所有文件操作限制在 workspace 内）、命令风险分级（SAFE/DANGEROUS/BLOCKED，支持黑白名单配置）、代码静态扫描（检测 eval/exec/os.system 等危险模式）。量化实验显示命令分级 100% 准确率。

3. 多工作模式
- PLAN 模式：生成结构化计划，用户审批后执行
- WORK 模式：自主执行，危险操作需确认
- FEEDBACK 模式：关键决策点暂停等待反馈
- RESEARCH 模式：只读调查，不修改文件

4. 用户友好（任务管理，自定义规则）
Web 界面支持按工作区分类管理任务，支持列表视图和分组视图切换，任务持久化到 SQLite，同时支持用户自定义输出规则。界面美观简约，过程可视化，可展开工具调用，了解过程和调用结果。

三、开发历程

这个项目源于我之前的研究（CodeAgent Bench，目前一作身份在投）和软工三课设的积累。我在日常使用 agent 时发现两个痛点：token 耗量太快，新开对话又会丧失记忆降智；以及可能误执行危险脚本。

开发流程参考暑期学校学习的 Superpowers，先用 brainstorm 功能落地详细设计文档（SPEC.md），然后按 task 逐步开发。工具和模板由 AI 完成，核心逻辑（如 agent 循环）由我写出想法框架，AI 补充完善。压缩策略是我针对痛点自己设计的（事件驱动 + 阈值驱动混合触发），代码扫描选择轻量方案（若工程需要可引入 CodeQL、Semgrep 等成熟工具）。

过程中对架构有多次调整，对 AI 建议也有反驳和新的讨论（详见 docs/review_log.md，含答辩要点速查）。前端设计受 TRAE 启发。完整 brainstorm 过程见 docs/brainstormProcess.md。

四、技术亮点

- 工程化思维：先落地PLAN，SPEC，TASK文档
- 三层架构：Execution State（当前轮）/ Context（历史）/ Workspace（文件系统），Source of Truth 在磁盘
- 事件驱动压缩：写操作立即失效旧读取，避免过期内容
- 完整测试：所有测试全通过，量化实验验证压缩率和准确率

五、量化数据

- 测试覆盖：281/281 通过（100%）
- 上下文压缩：平均 35.4%，最高 65.2%
- 安全准确率：85.7%，精确率 100%
- 命令防护：100% 准确率

特别致谢：TRAE 提供的界面设计灵感，Superpowers 提供的开发流程指导。

