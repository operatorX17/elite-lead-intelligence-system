import ast
from pathlib import Path
from typing import List


SERVER_PATH = Path(__file__).resolve().parents[1] / "src" / "api" / "server.py"


def _load_discovery_functions():
    source = SERVER_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted_assignments = {"OSINT_FIRST_NICHES"}
    wanted_functions = {
        "is_clinic_style_niche",
        "should_use_osint_discovery",
        "build_osint_queries",
    }

    selected_nodes = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted_assignments:
                    selected_nodes.append(node)
                    break
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            selected_nodes.append(node)

    mini_module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(mini_module)
    namespace = {"List": List}
    exec(compile(mini_module, str(SERVER_PATH), "exec"), namespace)
    return namespace["build_osint_queries"], namespace["should_use_osint_discovery"]


def test_clinic_style_niches_use_osint_discovery():
    _, should_use_osint_discovery = _load_discovery_functions()
    assert should_use_osint_discovery("premium skin and aesthetic clinics")
    assert should_use_osint_discovery("dermatology clinic")


def test_clinic_style_osint_queries_are_clinic_specific():
    build_osint_queries, _ = _load_discovery_functions()
    queries = build_osint_queries("premium skin and aesthetic clinics", "Bangalore", 10)

    assert queries
    joined = " ".join(queries).lower()
    assert "bangalore" in joined
    assert any(token in joined for token in ["aesthetic clinic", "skin clinic", "dermatology clinic"])
    assert "book appointment" in joined or "book consultation" in joined or "whatsapp" in joined
