"""文件操作工具集，提供读写、目录列举、内容搜索等能力。"""
from pathlib import Path
from typing import Any

from config import WORKSPACE_DIR
from tools.registry import BaseTool


def _safe_resolve(relative_path: str) -> Path:
    """将相对路径解析为绝对路径，并确保不逃逸出工作空间。

    Raises:
        ValueError: 路径逃逸出工作空间。
    """
    resolved = (WORKSPACE_DIR / relative_path).resolve()
    workspace_resolved = WORKSPACE_DIR.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise ValueError(f"路径安全校验失败，禁止访问工作空间以外的文件: {relative_path}")
    return resolved


class ReadFileTool(BaseTool):
    """读取文件内容。"""

    name = "read_file"
    description = "读取工作空间中指定文件的内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对于工作空间根目录）"},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, **_: Any) -> str:
        try:
            file_path = _safe_resolve(path)
        except ValueError as e:
            return f"错误: {e}"
        if not file_path.exists():
            return f"错误: 文件 '{path}' 不存在"
        if not file_path.is_file():
            return f"错误: '{path}' 不是文件"
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            return f"文件 '{path}' ({len(lines)} 行):\n{content}"
        except Exception as e:
            return f"错误: 读取文件失败 - {e}"


class WriteFileTool(BaseTool):
    """创建或覆盖写入文件。"""

    name = "write_file"
    description = "在工作空间中创建或覆盖写入文件"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对于工作空间根目录）"},
            "content": {"type": "string", "description": "要写入的文件内容"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, **_: Any) -> str:
        try:
            file_path = _safe_resolve(path)
        except ValueError as e:
            return f"错误: {e}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            file_path.write_text(content, encoding="utf-8")
            return f"成功: 已写入文件 '{path}' ({len(content)} 字符, {len(content.splitlines())} 行)"
        except Exception as e:
            return f"错误: 写入文件失败 - {e}"


class ListDirectoryTool(BaseTool):
    """列出目录内容。"""

    name = "list_directory"
    description = "列出工作空间中指定目录下的文件和子目录"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径（相对于工作空间根目录），默认为根目录",
            },
        },
        "required": [],
    }

    async def execute(self, path: str = ".", **_: Any) -> str:
        try:
            dir_path = _safe_resolve(path)
        except ValueError as e:
            return f"错误: {e}"
        if not dir_path.exists():
            return f"错误: 目录 '{path}' 不存在"
        if not dir_path.is_dir():
            return f"错误: '{path}' 不是目录"

        entries = []
        for entry in sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
            prefix = "[DIR] " if entry.is_dir() else "[FILE]"
            rel = entry.relative_to(WORKSPACE_DIR.resolve())
            size_info = f" ({entry.stat().st_size} bytes)" if entry.is_file() else ""
            entries.append(f"  {prefix} {rel}{size_info}")

        if not entries:
            return f"目录 '{path}' 为空"
        return f"目录 '{path}' 的内容 ({len(entries)} 项):\n" + "\n".join(entries)


class SearchFilesTool(BaseTool):
    """在文件中搜索关键词。"""

    name = "search_files"
    description = "在工作空间的文件中搜索包含指定关键词的行"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "要搜索的关键词"},
            "file_extension": {
                "type": "string",
                "description": "限定搜索的文件扩展名（如 .py, .csv），留空搜索所有文件",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, file_extension: str = "", **_: Any) -> str:
        results: list[str] = []
        ws_resolved = WORKSPACE_DIR.resolve()
        for file_path in ws_resolved.rglob("*"):
            if not file_path.is_file():
                continue
            if file_extension and file_path.suffix != file_extension:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                if pattern.lower() in line.lower():
                    rel = file_path.relative_to(ws_resolved)
                    results.append(f"  {rel}:{line_no}: {line.strip()}")

        if not results:
            return f"未找到包含 '{pattern}' 的内容"
        truncated = results[:50]
        header = f"搜索 '{pattern}' 的结果 ({len(results)} 处匹配):"
        if len(results) > 50:
            header += " (仅显示前50条)"
        return header + "\n" + "\n".join(truncated)
