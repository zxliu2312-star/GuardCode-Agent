"""
上下文压缩率量化实验

测试不同场景下的压缩效果：
1. 文件读写密集型任务
2. 命令执行密集型任务
3. 混合型任务
4. 长对话任务

指标：
- 压缩前后消息数量
- 压缩前后字符数
- 压缩率（字符数减少百分比）
- 压缩耗时
"""

import json
import time
from pathlib import Path
from typing import Any

# 添加项目根目录到 sys.path
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from guardcode.context.compressor import compress_history
from guardcode.context.manager import estimate_context_size


# PLACEHOLDER_FOR_HELPER_FUNCTIONS


def run_compression_benchmark(scenario_name: str, messages: list[dict[str, Any]], keep_recent: int = 5):
    """运行单个场景的压缩基准测试"""
    print(f"\n{'='*70}")
    print(f"场景: {scenario_name}")
    print(f"{'='*70}")
    
    # 原始指标
    original_count = len(messages)
    original_size = estimate_context_size(messages)
    
    print(f"原始消息数量: {original_count}")
    print(f"原始上下文大小: {original_size:,} 字符")
    
    # 执行压缩
    start_time = time.time()
    compressed = compress_history(messages, keep_recent=keep_recent, use_llm_summary=False)
    compression_time = time.time() - start_time
    
    # 压缩后指标
    compressed_count = len(compressed)
    compressed_size = estimate_context_size(compressed)
    
    # 计算压缩率
    count_reduction = ((original_count - compressed_count) / original_count * 100) if original_count > 0 else 0
    size_reduction = ((original_size - compressed_size) / original_size * 100) if original_size > 0 else 0
    
    print(f"\n压缩后消息数量: {compressed_count} (-{count_reduction:.1f}%)")
    print(f"压缩后上下文大小: {compressed_size:,} 字符 (-{size_reduction:.1f}%)")
    print(f"压缩耗时: {compression_time*1000:.2f} ms")
    
    # 验证压缩策略效果
    print(f"\n压缩策略验证:")
    
    # 检查写后失效
    invalidated_reads = 0
    for msg in compressed:
        if msg.get("role") == "tool":
            try:
                content = json.loads(msg["content"])
                if content.get("_tool_name") == "read_file" and content.get("compressed"):
                    if "was modified later" in content.get("result", ""):
                        invalidated_reads += 1
            except:
                pass
    
    print(f"  - 写后失效: {invalidated_reads} 个过期读取被标记")
    
    # 检查按需重读
    compressed_reads = 0
    for msg in compressed:
        if msg.get("role") == "tool":
            try:
                content = json.loads(msg["content"])
                if content.get("_tool_name") == "read_file" and content.get("compressed"):
                    if "<content:" in content.get("result", ""):
                        compressed_reads += 1
            except:
                pass
    
    print(f"  - 按需重读: {compressed_reads} 个大型读取被压缩为元信息")
    
    # 检查工作集保留
    recent_count = min(keep_recent, len(messages))
    recent_preserved = compressed[-recent_count:] if len(compressed) >= recent_count else compressed
    print(f"  - 工作集保留: 最近 {len(recent_preserved)} 轮完整保留")
    
    return {
        "scenario": scenario_name,
        "original_count": original_count,
        "original_size": original_size,
        "compressed_count": compressed_count,
        "compressed_size": compressed_size,
        "count_reduction_percent": count_reduction,
        "size_reduction_percent": size_reduction,
        "compression_time_ms": compression_time * 1000,
        "invalidated_reads": invalidated_reads,
        "compressed_reads": compressed_reads,
    }


def main():
    """运行所有压缩基准测试"""
    # 设置 UTF-8 输出编码
    import sys
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 70)
    print("GuardCode Agent - 上下文压缩率量化实验")
    print("=" * 70)
    
    results = []
    
    # 场景 1-4
    from experiments.compression_scenarios import (
        create_file_intensive_messages,
        create_command_intensive_messages,
        create_mixed_messages,
        create_long_conversation_messages
    )
    
    results.append(run_compression_benchmark("文件读写密集型", create_file_intensive_messages()))
    results.append(run_compression_benchmark("命令执行密集型", create_command_intensive_messages()))
    results.append(run_compression_benchmark("混合型任务", create_mixed_messages()))
    results.append(run_compression_benchmark("长对话任务 (50轮)", create_long_conversation_messages()))
    
    # 汇总报告
    print(f"\n{'='*70}")
    print("汇总报告")
    print(f"{'='*70}\n")
    
    print(f"{'场景':<20} {'原始大小':<12} {'压缩后':<12} {'压缩率':<10} {'耗时':<10}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['scenario']:<20} "
              f"{r['original_size']:>10,}  "
              f"{r['compressed_size']:>10,}  "
              f"{r['size_reduction_percent']:>8.1f}%  "
              f"{r['compression_time_ms']:>8.2f}ms")
    
    avg_reduction = sum(r['size_reduction_percent'] for r in results) / len(results)
    avg_time = sum(r['compression_time_ms'] for r in results) / len(results)
    
    print("-" * 70)
    print(f"{'平均':<20} {'':<12} {'':<12} {avg_reduction:>8.1f}%  {avg_time:>8.2f}ms")
    
    # 保存结果
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "compression_benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "summary": {
                "avg_size_reduction_percent": avg_reduction,
                "avg_compression_time_ms": avg_time,
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")
    print("\n✅ 实验完成！")


if __name__ == "__main__":
    main()
