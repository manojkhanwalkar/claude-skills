# Python project layout

`src/` layout, uv for environments and locking, one distribution per repo unless the Java
project had independently deployable services (then one package per service under `src/`
and one `[project.scripts]` entry per entry point).

```
<Name>/
  .github/                     # see github-setup.md
  .idea/  <Name>.iml           # see intellij.md
  src/<pkg>/
    __init__.py
    __main__.py                # `python -m <pkg>` if the Java project had a main()
    py.typed
    ...
  tests/
    conftest.py
    golden/                    # captured Java outputs for parity tests
    test_*.py
  pyproject.toml
  uv.lock                      # committed
  README.md  LICENSE  SECURITY.md  .gitignore
  Dockerfile                   # only if the Java project shipped an image
```

`<pkg>` is the snake_case of the project name, or a meaningful name from the Java base
package (`com.acme.calculator` → `calculator`).

## pyproject.toml

```toml
[project]
name = "<dist-name>"
version = "0.1.0"
description = "Python port of <JavaName>"
readme = "README.md"
license = "<SPDX id from the Java project, e.g. MIT>"
requires-python = ">=<X.Y>"
dependencies = []          # added with `uv add`

[project.scripts]
# <command> = "<pkg>.__main__:main"

[dependency-groups]
dev = ["pytest", "pytest-cov", "pytest-asyncio", "mypy", "ruff"]   # added with `uv add --dev`

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py3XX"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "S", "SIM", "RUF", "PL", "PT", "ASYNC", "C4", "RET"]
ignore = ["PLR2004"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR0913"]

[tool.mypy]
strict = true
files = ["src", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --cov=<pkg> --cov-branch --cov-report=term-missing --cov-report=xml"
asyncio_mode = "auto"

[tool.coverage.report]
fail_under = 95
show_missing = true
exclude_also = ["if TYPE_CHECKING:", "if __name__ == .__main__.:"]
```

Add dev dependencies with `uv add --dev pytest pytest-cov pytest-asyncio mypy ruff` rather than
writing version pins by hand, so uv picks current releases and writes `uv.lock`.

## .gitignore

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/
dist/
build/
*.egg-info/
.env
.idea/workspace.xml
.idea/shelf/
.idea/usage.statistics.xml
```

## README skeleton

- One paragraph: what it does; "Python port of [<JavaName>](<java repo url>) at `<sha>`".
- Requirements (Python version, uv).
- Setup: `uv sync`.
- Run: the exact commands for each entry point (and MCP client config JSON if it's an MCP server).
- Test: `uv run pytest`.
- Differences from the Java version (intentional ones only).
- Links: design doc, system diagram.
