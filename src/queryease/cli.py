"""Entry point for the `queryease` CLI command when installed via pip."""

import sys
import os

# When installed as a package, src/ is already on the path.
# When running locally (python3 main.py), main.py adds it manually.
# This file handles the pip-installed case.

def main():
    # Import here so path is already set up by setuptools
    from queryease.config import validate_config
    from queryease.schema import (
        get_schema, format_schema_for_prompt, cache_exists, get_dialect,
        build_join_graph, format_join_hints, load_descriptions,
    )
    from queryease.generator import (
        generate_sql, generate_sql_with_context, explain_sql,
        regenerate_sql, MAX_CORRECTIONS,
    )
    from queryease.validator import (
        validate, ValidationError, InjectionError,
        check_prompt_injection, is_write_query, is_complex_query,
    )
    from queryease.judge import judge_sql
    from queryease.executor import execute, ExecutionError
    from queryease import formatter
    from queryease.history import save_query, get_history

    # Re-use all logic from main.py by importing it
    # We add the project root to sys.path so .env is found correctly
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Dynamically find and run main() from wherever main.py is
    import importlib.util
    main_path = os.path.join(project_root, "main.py")
    if os.path.exists(main_path):
        spec = importlib.util.spec_from_file_location("__main__", main_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    else:
        print("Error: main.py not found. Run queryease from your project directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
