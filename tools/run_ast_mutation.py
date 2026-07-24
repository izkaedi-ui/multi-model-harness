"""
Lightweight custom AST-based mutation testing engine for security & gate code.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


TARGET_FILE = Path("evaluators/evaluation_integrity.py")
TEST_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "tests/unit/test_evaluation_integrity_suite.py",
    "tests/unit/test_evaluation_integrity_extended.py",
    "tests/unit/test_evaluation_integrity_e2e.py",
    "-q",
]


def run_tests() -> bool:
    res = subprocess.run(TEST_COMMAND, capture_output=True)
    return res.returncode == 0


def main() -> None:
    original_code = TARGET_FILE.read_text(encoding="utf-8")
    print(f"[*] Testing baseline on {TARGET_FILE}...")
    if not run_tests():
        print("[!] Baseline test suite failed!")
        sys.exit(1)

    print("[*] Generating AST mutations...")
    tree = ast.parse(original_code)

    mutations_tested = 0
    mutants_killed = 0
    mutants_survived = []

    # Mutate comparison operators (e.g. >= -> >, == -> !=)
    class ComparisonMutant(ast.NodeTransformer):
        def __init__(self, target_idx: int):
            self.current_idx = 0
            self.target_idx = target_idx
            self.applied = False

        def visit_Compare(self, node: ast.Compare) -> ast.Compare:
            new_ops = []
            for op in node.ops:
                if self.current_idx == self.target_idx:
                    self.applied = True
                    if isinstance(op, ast.GtE):
                        new_ops.append(ast.Gt())
                    elif isinstance(op, ast.LtE):
                        new_ops.append(ast.Lt())
                    elif isinstance(op, ast.Eq):
                        new_ops.append(ast.NotEq())
                    elif isinstance(op, ast.NotEq):
                        new_ops.append(ast.Eq())
                    else:
                        new_ops.append(op)
                else:
                    new_ops.append(op)
                self.current_idx += 1
            return ast.Compare(left=self.visit(node.left), ops=new_ops, comparators=[self.visit(c) for c in node.comparators])

    # Count comparisons
    class CompareCounter(ast.NodeVisitor):
        def __init__(self):
            self.count = 0
        def visit_Compare(self, node: ast.Compare):
            self.count += len(node.ops)
            self.generic_visit(node)

    counter = CompareCounter()
    counter.visit(tree)

    print(f"[*] Found {counter.count} comparison operators to mutate.")

    for i in range(counter.count):
        mutator = ComparisonMutant(i)
        mutated_ast = mutator.visit(ast.parse(original_code))
        ast.fix_missing_locations(mutated_ast)
        mutated_code = ast.unparse(mutated_ast)
        TARGET_FILE.write_text(mutated_code, encoding="utf-8")
        mutations_tested += 1

        if run_tests():
            print(f"[!] Mutant {i+1} SURVIVED! Code:\n{mutated_code}\n")
            mutants_survived.append(f"Comparison mutant {i+1}")
        else:
            mutants_killed += 1
    # Restore original file
    TARGET_FILE.write_text(original_code, encoding="utf-8")

    print("\n=== AST Mutation Testing Results ===")
    print(f"Mutations Tested: {mutations_tested}")
    print(f"Mutants Killed: {mutants_killed}")
    print(f"Mutants Survived: {len(mutants_survived)}")

    if mutants_survived:
        sys.exit(1)
    else:
        print("[SUCCESS] 100% Mutation Kill Rate on evaluators/evaluation_integrity.py!")


if __name__ == "__main__":
    main()
