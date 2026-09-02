"""
运行所有量化实验

包括：
1. 上下文压缩率测试
2. 安全拦截准确率测试
3. 工具测试（pytest）
"""

import sys
import subprocess
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def run_tool_tests():
    """运行工具测试（pytest）"""
    print("\n" + "=" * 70)
    print("运行工具测试（pytest）")
    print("=" * 70 + "\n")
    
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_file_tools.py", "tests/test_command_tools.py", "-v"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n✅ 工具测试通过")
        else:
            print("\n❌ 工具测试失败")
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行测试时出错: {e}")
        return False


def run_compression_benchmark():
    """运行上下文压缩率测试"""
    print("\n" + "=" * 70)
    print("运行上下文压缩率测试")
    print("=" * 70 + "\n")
    
    try:
        from experiments.context_compression_benchmark import main as compression_main
        compression_main()
        return True
    except Exception as e:
        print(f"❌ 压缩测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_security_benchmark():
    """运行安全拦截准确率测试"""
    print("\n" + "=" * 70)
    print("运行安全拦截准确率测试")
    print("=" * 70 + "\n")
    
    try:
        from experiments.security_accuracy_benchmark import main as security_main
        security_main()
        return True
    except Exception as e:
        print(f"❌ 安全测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有实验"""
    print("=" * 70)
    print("GuardCode Agent - 完整量化实验套件")
    print("=" * 70)
    
    results = {}
    
    # 1. 工具测试
    results['tool_tests'] = run_tool_tests()
    
    # 2. 上下文压缩测试
    results['compression'] = run_compression_benchmark()
    
    # 3. 安全准确率测试
    results['security'] = run_security_benchmark()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("实验结果汇总")
    print("=" * 70)
    
    print(f"\n工具测试:          {'✅ 通过' if results['tool_tests'] else '❌ 失败'}")
    print(f"上下文压缩测试:    {'✅ 完成' if results['compression'] else '❌ 失败'}")
    print(f"安全准确率测试:    {'✅ 完成' if results['security'] else '❌ 失败'}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "=" * 70)
        print("🎉 所有实验完成！")
        print("=" * 70)
        print("\n结果文件位置:")
        print("  - experiments/results/compression_benchmark_results.json")
        print("  - experiments/results/security_accuracy_results.json")
    else:
        print("\n" + "=" * 70)
        print("⚠️  部分实验失败，请检查错误信息")
        print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
