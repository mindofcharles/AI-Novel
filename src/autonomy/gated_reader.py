import os
import logging
from typing import Optional

class GatedFileReader:
    """
    Safely reads files with paginated chunks and outline fallbacks
    to protect the LLM context window from massive log or data dumps.
    """
    def __init__(self, large_threshold_kb: int = 50, max_chunk: int = 100):
        self.large_threshold_kb = large_threshold_kb
        self.max_chunk = max_chunk
        self.logger = logging.getLogger("GatedFileReader")

    def read_file(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        """
        Reads a file. If file exceeds the size threshold and no end_line is specified,
        returns a structured outline warning instead of content.
        """
        if not os.path.exists(path):
            return f"Error: File '{path}' does not exist."

        try:
            size_kb = os.path.getsize(path) / 1024.0
            if size_kb > self.large_threshold_kb and end_line is None:
                # Return structured outline fallback
                total_lines = self._count_lines(path)
                first_lines = self._read_lines(path, 1, 5)
                return (
                    f"### LARGE FILE WARNING\n"
                    f"- **File**: {os.path.basename(path)}\n"
                    f"- **Size**: {size_kb:.1f} KB (Exceeds threshold of {self.large_threshold_kb} KB)\n"
                    f"- **Total Lines**: {total_lines}\n\n"
                    f"Direct reading of large files is gated to protect the context window.\n"
                    f"Please read specific parts using the paginated `read_file_chunk(path, start_line, end_line)` tool.\n\n"
                    f"**First 5 Lines Sample**:\n"
                    f"```text\n"
                    f"{first_lines}"
                    f"```\n"
                )

            # Standard paginated read
            target_end = end_line if end_line is not None else (start_line + self.max_chunk - 1)
            # Cap read size
            if (target_end - start_line + 1) > self.max_chunk:
                target_end = start_line + self.max_chunk - 1

            return self._read_lines(path, start_line, target_end)
        except Exception as e:
            self.logger.error(f"Error reading file '{path}': {e}")
            return f"Error reading file '{path}': {e}"

    def read_file_tail(self, path: str, line_count: int = 50) -> str:
        """Reads and returns the last line_count lines of a file."""
        if not os.path.exists(path):
            return f"Error: File '{path}' does not exist."

        try:
            total_lines = self._count_lines(path)
            start_line = max(1, total_lines - line_count + 1)
            return self._read_lines(path, start_line, total_lines)
        except Exception as e:
            self.logger.error(f"Error tailing file '{path}': {e}")
            return f"Error tailing file '{path}': {e}"

    def _count_lines(self, path: str) -> int:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)

    def _read_lines(self, path: str, start: int, end: int) -> str:
        lines = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, start=1):
                if start <= idx <= end:
                    lines.append(f"{idx}: {line}")
                if idx > end:
                    break
        return "".join(lines)
