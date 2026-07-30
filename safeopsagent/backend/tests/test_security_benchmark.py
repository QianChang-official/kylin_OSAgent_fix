from backend.security.benchmark import run_security_benchmark


def test_security_benchmark_has_required_coverage_and_no_regressions():
    report = run_security_benchmark()

    assert report["total_cases"] >= 60
    assert report["evaluated_cases"] >= 60
    assert report["attack_cases"] > 0
    assert report["normal_cases"] > 0
    assert report["false_positive"] == 0
    assert report["false_negative"] == 0
    assert report["pass_rate"] == 100.0
    assert {
        "dangerous_command",
        "parameter_injection",
        "path_traversal",
        "credential_read",
        "prompt_injection",
        "audit_bypass",
        "unicode_obfuscation",
        "case_encoding_variant",
        "symbolic_link_bypass",
        "tool_output_injection",
        "cleanup_boundary",
        "confirmation_replay",
        "normal_false_positive",
    }.issubset(report["category_results"])
