#!/usr/bin/env python3
"""
Test Report Generator with Coverage

Generates a formal HTML report from pytest test results and code coverage.
"""
import subprocess
import sys
import json
import os
from datetime import datetime
from pathlib import Path


def run_tests():
    """Run pytest with coverage and capture verbose text output."""
    cmd = [
        sys.executable, "-m", "pytest",
        ".",                  # Автопоиск тестов, как в терминале
        "-v",
        "--tb=short",
        "--color=no",         # Отключаем ANSI-цвета для стабильного парсинга
        "--cov=.",            # <-- Считаем покрытие для текущей директории
        "--cov-report=json:coverage.json",
        "--cov-report=term-missing"  # Дублируем в консоль для удобства отладки
    ]
    
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.getcwd(),
    )
    return result


def parse_test_output(output):
    """Parse pytest verbose output to extract test results."""
    tests = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
            
        if any(kw in line for kw in ("PASSED", "FAILED", "ERROR", "SKIPPED")):
            parts = line.split()
            if len(parts) < 2:
                continue
                
            test_id = parts[0]
            status_raw = parts[-1].upper()
            
            if "FAILED" in status_raw:
                status = "failed"
            elif "ERROR" in status_raw:
                status = "error"
            elif "SKIPPED" in status_raw:
                status = "skipped"
            else:
                status = "passed"
                
            tests.append({"name": test_id, "status": status})
            
    return tests


def parse_coverage(cov_json_path="coverage.json"):
    """Parse pytest-cov JSON report."""
    if not Path(cov_json_path).exists():
        return None
    try:
        with open(cov_json_path, encoding="utf-8") as f:
            data = json.load(f)
        totals = data.get("totals", {})
        return {
            "percent": totals.get("percent_covered", 0),
            "covered_lines": totals.get("covered_lines", 0),
            "missing_lines": totals.get("missing_lines", 0),
            "total_lines": totals.get("num_statements", 0)
        }
    except Exception:
        return None


def generate_html_report(tests, summary, duration, coverage_data=None):
    """Generate HTML report with test results and coverage."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errors = summary.get("errors", 0)
    skipped = summary.get("skipped", 0)
    total = passed + failed + errors + skipped
    
    success_rate = (passed / total * 100) if total > 0 else 0
    
    if failed > 0 or errors > 0:
        overall_status = "FAILED"
        status_color = "#dc3545"
    else:
        overall_status = "PASSED"
        status_color = "#28a745"

    # Coverage formatting
    cov_percent = coverage_data["percent"] if coverage_data else 0
    cov_color = "#28a745" if cov_percent >= 80 else ("#ffc107" if cov_percent >= 50 else "#dc3545")
    cov_display = f"{coverage_data['covered_lines']}/{coverage_data['total_lines']}" if coverage_data else "N/A"
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчёт о тестировании</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .summary-card {{ padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
        .summary-card .value {{ font-size: 36px; font-weight: bold; }}
        .total {{ background-color: #e3f2fd; }} .total .value {{ color: #1976d2; }}
        .passed {{ background-color: #e8f5e9; }} .passed .value {{ color: #388e3c; }}
        .failed {{ background-color: #ffebee; }} .failed .value {{ color: #d32f2f; }}
        .errors {{ background-color: #fff3e0; }} .errors .value {{ color: #f57c00; }}
        .skipped {{ background-color: #f3e5f5; }} .skipped .value {{ color: #7b1fa2; }}
        .coverage {{ background-color: #e0f7fa; }} .coverage .value {{ color: #0097a7; }}
        .status-banner {{ padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; font-size: 24px; font-weight: bold; color: white; background-color: {status_color}; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .status-passed {{ color: #28a745; font-weight: bold; }}
        .status-failed, .status-error {{ color: #dc3545; font-weight: bold; }}
        .status-skipped {{ color: #6c757d; font-weight: bold; }}
        .metadata {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .metadata p {{ margin: 5px 0; color: #666; }}
        .progress-bar {{ height: 20px; background-color: #e9ecef; border-radius: 10px; overflow: hidden; margin: 10px 0; }}
        .progress-fill {{ height: 100%; transition: width 0.3s; }}
        .fill-success {{ background-color: #28a745; }}
        .fill-coverage {{ background-color: {cov_color}; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Отчёт о тестировании</h1>
        <div class="status-banner">{overall_status}</div>
        <div class="metadata">
            <p><strong>Дата и время:</strong> {timestamp}</p>
            <p><strong>Длительность тестирования:</strong> {duration:.2f} сек.</p>
            <p><strong>Процент успешных тестов:</strong> {success_rate:.1f}%</p>
        </div>
        <div class="summary">
            <div class="summary-card total"><h3>ВСЕГО ТЕСТОВ</h3><div class="value">{total}</div></div>
            <div class="summary-card passed"><h3>УСПЕШНО</h3><div class="value">{passed}</div></div>
            <div class="summary-card failed"><h3>ПРОВАЛЕНО</h3><div class="value">{failed}</div></div>
            <div class="summary-card errors"><h3>ОШИБКИ</h3><div class="value">{errors}</div></div>
            <div class="summary-card skipped"><h3>ПРОПУЩЕНО</h3><div class="value">{skipped}</div></div>
            <div class="summary-card coverage">
                <h3>ПОКРЫТИЕ КОДА</h3>
                <div class="value">{cov_percent:.1f}%</div>
                <div style="font-size: 12px; color: #666; margin-top: 5px;">{cov_display} строк</div>
            </div>
        </div>
        
        <h3>Успешность тестов</h3>
        <div class="progress-bar"><div class="progress-fill fill-success" style="width: {success_rate}%;"></div></div>
        
        <h3>Покрытие кода</h3>
        <div class="progress-bar"><div class="progress-fill fill-coverage" style="width: {cov_percent}%;"></div></div>

        <h2>📋 Детали тестов</h2>
        <table>
            <thead><tr><th>№</th><th>Тест</th><th>Статус</th></tr></thead>
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
    
    # Проверка наличия pytest-cov
    try:
        import coverage  # noqa: F401
    except ImportError:
        print("⚠️  Пакет pytest-cov не установлен. Покрытие кода будет пропущено.")
        print("💡 Установите: pip install pytest-cov coverage\n")

    start_time = datetime.now()
    result = run_tests()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    tests = parse_test_output(result.stdout)
    
    summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for test in tests:
        if test["status"] in summary:
            summary[test["status"]] += 1
            
    coverage_data = parse_coverage("coverage.json")
    html_report = generate_html_report(tests, summary, duration, coverage_data)
    
    report_path = Path("test_report.html")
    report_path.write_text(html_report, encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"ВСЕГО ТЕСТОВ: {sum(summary.values())}")
    print(f"УСПЕШНО: {summary['passed']}")
    print(f"ПРОВАЛЕНО: {summary['failed']}")
    print(f"ОШИБКИ: {summary['errors']}")
    print(f"ПРОПУЩЕНО: {summary['skipped']}")
    if coverage_data:
        print(f"ПОКРЫТИЕ: {coverage_data['percent']:.1f}%")
    print(f"{'='*60}")
    print(f"\nОтчёт сохранён в: {report_path}")
    
    json_summary = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "summary": summary,
        "coverage": coverage_data,
        "tests": tests
    }
    
    json_path = Path("test_results.json")
    json_path.write_text(json.dumps(json_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON результаты сохранены в: {json_path}")
    
    return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())