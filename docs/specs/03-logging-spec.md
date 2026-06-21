# SPEC: 结构化日志

## 调研

| 现状 | 问题 |
|------|------|
| `data/` 层 | 已用 `logging.getLogger(__name__).warning()` — 正确 |
| `tools/a2a_adapter.py` | 用 `print()` 输出信息 — 无级别、无格式 |
| `engine/` | 零日志 — 正确（零 I/O 约束） |
| 全局 | 无集中配置，各模块各自调用 `logging.basicConfig()` 或依赖默认行为 |

## 1. Objective

统一 Fortress 的日志输出为一致的 `[时间] [级别] 模块: 消息` 格式，全部输出到 stderr，替换混用的 `print()` 调用。

### 约束
- **所有日志必须输出到 stderr** — MCP 用 stdout 做 JSON-RPC 通信
- **不改 engine/** — engine 层零 I/O 是硬约束，不加日志
- **零新依赖** — 只用 stdlib `logging`

## 2. Commands

```bash
# 启动 server（日志在 stderr，JSON-RPC 在 stdout）
python -m src.tools.server 2> fortress.log

# 测试
pytest tests/ -v -k "not integration"

# Lint
ruff check src/
```

## 3. Project Structure

```
src/logging_config.py     # 新建 — 集中日志配置
src/tools/server.py       # 修改 — 启动时调用 setup()
src/tools/a2a_adapter.py  # 修改 — print() → logging.info()
```

不改：`src/engine/`、`src/data/`、`src/report/`、`src/agent/`

## 4. Code Style

```python
# src/logging_config.py
import logging
import sys

def setup(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
```

```python
# server.py 启动处
from src.logging_config import setup as setup_logging
setup_logging()
```

```python
# a2a_adapter.py — print → logging
import logging
logger = logging.getLogger(__name__)
logger.info("Fortress A2A server starting on port %d", port)
```

## 5. Testing Strategy

- `data/` 层已有 log 输出的测试，不改动
- 新增 `tests/test_logging_config.py`：验证 `setup()` 后 `logging` 输出到 stderr，格式正确
- 回归：86/86 现有测试必须全部通过

## 6. Boundaries

- **Always**: 用 `logger.info()` / `logger.warning()` / `logger.error()`，不用 `print()`
- **Ask first**: 加新日志语句、改日志级别
- **Never**: 在 engine/ 加日志、在 stdout 输出日志

## Success Criteria
- [ ] 所有 `print()` 调用从 `a2a_adapter.py` 移除
- [ ] `server.py` 启动时自动配置日志格式
- [ ] stderr 输出格式：`2026-06-22T10:30:00 [INFO ] src.tools.server: starting`
- [ ] 86/86 现有测试通过

## Open Questions
- 无
