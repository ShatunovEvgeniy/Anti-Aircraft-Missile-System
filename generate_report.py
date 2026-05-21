#!/usr/bin/env python3
"""
Test Report Generator

Generates a formal HTML report from pytest test results.
"""
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path


def run_tests_with_json():
    """Run pytest and capture JSON output."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--json-report",
        "--json-report-file=none",
    ]
    
    env = {"QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, **env},
        cwd="/workspace"
    )
    
    return result


def parse_test_output(output):
    """Parse pytest output to extract test results."""
    tests = []
    lines = output.split("\n")
    
    for line in lines:
        if "PASSED" in line or "FAILED" in line or "ERROR" in line or "SKIPPED" in line:
            parts = line.strip().split()
            if len(parts) >= 2:
                test_name = parts[0]
                status = "passed"
                if "FAILED" in line:
                    status = "failed"
                elif "ERROR" in line:
                    status = "error"
                elif "SKIPPED" in line:
                    status = "skipped"
                
                # Extract full test name
                if "::" in test_name:
                    file_part = test_name.split("::")[0].replace("tests/", "")
                    test_id = test_name
                else:
                    file_part = ""
                    test_id = test_name
                
                tests.append({
                    "name": test_id,
                    "status": status,
                })
    
    return tests


def generate_html_report(tests, summary, duration):
    """Generate HTML report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errors = summary.get("errors", 0)
    skipped = summary.get("skipped", 0)
    total = passed + failed + errors + skipped
    
    success_rate = (passed / total * 100) if total > 0 else 0
    
    # Determine overall status
    if failed > 0 or errors > 0:
        overall_status = "FAILED"
        status_color = "#dc3545"
    else:
        overall_status = "PASSED"
        status_color = "#28a745"
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчёт о тестировании</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #666;
        }}
        .summary-card .value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .total {{ background-color: #e3f2fd; }}
        .total .value {{ color: #1976d2; }}
        .passed {{ background-color: #e8f5e9; }}
        .passed .value {{ color: #388e3c; }}
        .failed {{ background-color: #ffebee; }}
        .failed .value {{ color: #d32f2f; }}
        .errors {{ background-color: #fff3e0; }}
        .errors .value {{ color: #f57c00; }}
        .skipped {{ background-color: #f3e5f5; }}
        .skipped .value {{ color: #7b1fa2; }}
        .status-banner {{
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            color: white;
            background-color: {status_color};
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-passed {{
            color: #28a745;
            font-weight: bold;
        }}
        .status-failed, .status-error {{
            color: #dc3545;
            font-weight: bold;
        }}
        .status-skipped {{
            color: #6c757d;
            font-weight: bold;
        }}
        .metadata {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .metadata p {{
            margin: 5px 0;
            color: #666;
        }}
        .progress-bar {{
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background-color: {status_color};
            transition: width 0.3s;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Отчёт о тестировании</h1>
        
        <div class="status-banner">
            {overall_status}
        </div>
        
        <div class="metadata">
            <p><strong>Дата и время:</strong> {timestamp}</p>
            <p><strong>Длительность тестирования:</strong> {duration:.2f} сек.</p>
            <p><strong>Процент успешных тестов:</strong> {success_rate:.1f}%</p>
        </div>
        
        <div class="summary">
            <div class="summary-card total">
                <h3>ВСЕГО ТЕСТОВ</h3>
                <div class="value">{total}</div>
            </div>
            <div class="summary-card passed">
                <h3>УСПЕШНО</h3>
                <div class="value">{passed}</div>
            </div>
            <div class="summary-card failed">
                <h3>ПРОВАЛЕНО</h3>
                <div class="value">{failed}</div>
            </div>
            <div class="summary-card errors">
                <h3>ОШИБКИ</h3>
                <div class="value">{errors}</div>
            </div>
            <div class="summary-card skipped">
                <h3>ПРОПУЩЕНО</h3>
                <div class="value">{skipped}</div>
            </div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {success_rate}%;"></div>
        </div>
        
        <h2>📋 Детали тестов</h2>
        <table>
            <thead>
                <tr>
                    <th>№</th>
                    <th>Тест</th>
                    <th>Статус</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for i, test in enumerate(tests, 1):
        status_class = f"status-{test['status']}"
        status_text = {
            "passed": "✓ Успешно",
            "failed": "✗ Провалено",
            "error": "⚠ Ошибка",
            "skipped": "⊘ Пропущено"
        }.get(test["status"], test["status"])
        
        html += f"""                <tr>
                    <td>{i}</td>
                    <td>{test['name']}</td>
                    <td class="{status_class}">{status_text}</td>
                </tr>
"""
    
    html += """            </tbody>
        </table>
        
        <div class="metadata">
            <p><em>Отчёт сгенерирован автоматически системой тестирования на основе pytest.</em></p>
        </div>
    </div>
</body>
</html>
"""
    
    return html


def main():
    print("Запуск тестов...")
    
    # Run tests
    start_time = datetime.now()
    result = run_tests_with_json()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Parse output
    tests = parse_test_output(result.stdout + result.stderr)
    
    # Calculate summary
    summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for test in tests:
        if test["status"] in summary:
            summary[test["status"]] += 1
    
    # Generate report
    html_report = generate_html_report(tests, summary, duration)
    
    # Save report
    report_path = Path("/workspace/test_report.html")
    report_path.write_text(html_report, encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"ВСЕГО ТЕСТОВ: {sum(summary.values())}")
    print(f"УСПЕШНО: {summary['passed']}")
    print(f"ПРОВАЛЕНО: {summary['failed']}")
    print(f"ОШИБКИ: {summary['errors']}")
    print(f"ПРОПУЩЕНО: {summary['skipped']}")
    print(f"{'='*60}")
    print(f"\nОтчёт сохранён в: {report_path}")
    
    # Also create JSON summary
    json_summary = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "summary": summary,
        "tests": tests
    }
    
    json_path = Path("/workspace/test_results.json")
    json_path.write_text(json.dumps(json_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON результаты сохранены в: {json_path}")
    
    return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
