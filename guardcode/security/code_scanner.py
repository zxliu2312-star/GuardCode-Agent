"""
代码静态扫描

逐行扫描 Python 代码，检测常见安全风险模式。
"""

import re
from typing import Dict, List, Any

# 风险模式：模式名 → 正则表达式
CODE_RISK_PATTERNS: Dict[str, str] = {
    # 代码执行类
    "eval": r"\beval\s*\(",
    "exec": r"\bexec\s*\(",
    "compile": r"\bcompile\s*\(",
    "__import__": r"__import__\s*\(",

    # 系统命令类
    "os.system": r"os\.system\s*\(",
    "os.popen": r"os\.popen\s*\(",
    "subprocess.shell_true": r"subprocess\..*\(.*shell\s*=\s*True",
    "os.exec": r"os\.exec[lv]p?e?\s*\(",

    # 反序列化类
    "pickle.loads": r"pickle\.loads?\s*\(",
    "yaml.unsafe_load": r"yaml\.unsafe_load\s*\(",
    "marshal.loads": r"marshal\.loads?\s*\(",

    # SQL 注入类
    "sql_fstring": r'(?:execute|cursor\.execute)\s*\(\s*f["\']',
    "sql_format": r'(?:execute|cursor\.execute)\s*\(\s*["\'].*\{.*\}.*["\'].*format\s*\(',
    "sql_percent": r'(?:execute|cursor\.execute)\s*\(\s*["\'].*%[sdf].*["\'].*%',

    # 硬编码密钥类
    "hardcoded_password": r'(?:password|passwd|pwd|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']',

    # 网络类
    "urllib_unverified": r"urllib\.request\.urlopen\s*\(",
    "requests_verify_false": r"verify\s*=\s*False",
}


def scan_python_code(content: str) -> List[Dict[str, Any]]:
    """
    逐行扫描 Python 代码，检测安全风险。

    Args:
        content: Python 代码内容

    Returns:
        风险列表，每项格式：
        {"pattern": str, "line": int, "content": str}
        line 从 1 开始计数
    """
    risks: List[Dict[str, Any]] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        # 跳过注释行（# 开头，去除前导空格后判断）
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        for pattern_name, regex in CODE_RISK_PATTERNS.items():
            if re.search(regex, line):
                risks.append({
                    "pattern": pattern_name,
                    "line": line_num,
                    "content": line.strip(),
                })

    return risks


def format_scan_results(risks: List[Dict[str, Any]]) -> str:
    """
    格式化扫描结果为可读字符串。

    Args:
        risks: scan_python_code 返回的风险列表

    Returns:
        格式化的警告文本
    """
    if not risks:
        return ""

    lines = [f"  ⚠ 发现 {len(risks)} 个安全风险："]
    for risk in risks:
        lines.append(
            f"    [{risk['pattern']}] Line {risk['line']}: {risk['content']}"
        )
    return "\n".join(lines)
