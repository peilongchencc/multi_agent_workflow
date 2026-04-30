"""上下文构建器 — 工作流 Stage 1 的前半部分。

负责从用户输入、工作空间文件系统等来源组装上下文信息，
供后续的意图解析和任务规划使用。
"""
from pathlib import Path

from loguru import logger

from config import WORKSPACE_DIR
from models import WorkflowContext


class ContextBuilder:
    """组装工作流上下文。"""

    async def build(
        self,
        user_input: str,
        workspace_path: str | None = None,
        include_files: list[str] | None = None,
    ) -> WorkflowContext:
        """构建工作流上下文。

        Args:
            user_input: 用户原始输入。
            workspace_path: 自定义工作空间路径，为空则使用默认路径。
            include_files: 需要预加载内容的文件列表（相对于工作空间）。

        Returns:
            组装完成的 WorkflowContext。
        """
        ws = Path(workspace_path) if workspace_path else WORKSPACE_DIR
        context = WorkflowContext(
            user_input=user_input,
            workspace_path=str(ws.resolve()),
        )

        context.directory_tree = self._build_tree(ws.resolve())
        logger.info(f"[context-builder] 工作空间目录树已构建: {ws}")

        if include_files:
            for rel_path in include_files:
                full = ws / rel_path
                if full.exists() and full.is_file():
                    try:
                        context.file_contents[rel_path] = full.read_text(encoding="utf-8")
                        logger.info(f"[context-builder] 已加载文件: {rel_path}")
                    except Exception as e:
                        logger.warning(f"[context-builder] 文件加载失败: {rel_path} - {e}")

        return context

    def _build_tree(self, root: Path, prefix: str = "", max_depth: int = 3) -> str:
        """递归构建目录树的文本表示。"""
        if max_depth <= 0 or not root.exists():
            return ""
        try:
            entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return f"{prefix}[权限不足]"

        entries = [e for e in entries if not e.name.startswith(".")]
        lines: list[str] = []
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                ext = "    " if is_last else "│   "
                subtree = self._build_tree(entry, prefix + ext, max_depth - 1)
                if subtree:
                    lines.append(subtree)
        return "\n".join(lines)
