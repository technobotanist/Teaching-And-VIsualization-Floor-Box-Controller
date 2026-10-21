from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from html import escape

from .config import ControllerConfig
from .field_session import FieldTestSession


def build_field_report(
    session: FieldTestSession,
    config: ControllerConfig,
) -> dict[str, object]:
    input_mappings = [
        session.input_mappings[source_name].model_dump(mode="json")
        for source_name in sorted(session.input_mappings)
    ]
    projector_results = []
    for projector in config.outputs.projectors:
        result = session.projector_tests[projector.id]
        projector_results.append(
            {
                "projector_id": projector.id,
                "label": projector.label,
                "source_name": projector.source_name,
                "monitor_index": projector.monitor_index,
                "enabled": projector.enabled,
                **result.model_dump(mode="json", exclude={"projector_id"}),
            }
        )

    failed_inputs = [
        mapping["source_name"]
        for mapping in input_mappings
        if mapping["signal_status"] != "pass"
    ]
    failed_projectors = [
        result["projector_id"]
        for result in projector_results
        if result["status"] != "pass"
    ]
    incomplete_checks = [
        check_id for check_id, checked in session.checks.items() if not checked
    ]
    config_json = config.model_dump_json()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "session_id": session.id,
        "room": config.room.model_dump(mode="json"),
        "session": {
            "status": session.status,
            "current_phase": session.current_phase,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "completed_at": session.completed_at.isoformat()
            if session.completed_at
            else None,
            "notes": session.notes,
        },
        "summary": {
            "inputs_passed": len(input_mappings) - len(failed_inputs),
            "input_count": len(input_mappings),
            "projectors_passed": len(projector_results) - len(failed_projectors),
            "projector_count": len(projector_results),
            "checks_passed": len(session.checks) - len(incomplete_checks),
            "check_count": len(session.checks),
            "failed_inputs": failed_inputs,
            "failed_projectors": failed_projectors,
            "incomplete_checks": incomplete_checks,
        },
        "config_sha256": sha256(config_json.encode("utf-8")).hexdigest(),
        "input_mappings": input_mappings,
        "projector_results": projector_results,
        "mode_exercise": session.mode_exercise.model_dump(mode="json"),
        "soak": session.soak.model_dump(mode="json"),
        "checks": session.checks,
        "snapshots": [snapshot.model_dump(mode="json") for snapshot in session.snapshots],
    }


def _status_label(value: object) -> str:
    return str(value or "untested").replace("_", " ").title()


def render_field_report(report: dict[str, object]) -> str:
    room = report["room"]
    session = report["session"]
    summary = report["summary"]
    mode_exercise = report["mode_exercise"]
    soak = report["soak"]
    inputs = report["input_mappings"]
    projectors = report["projector_results"]
    checks = report["checks"]

    input_rows = "".join(
        "<tr>"
        f"<td><strong>{escape(item['source_name'])}</strong><small>{escape(item['floor_label'] or 'Unlabeled')}</small></td>"
        f"<td>{escape(item['capture_device'] or 'Not recorded')}</td>"
        f"<td>{escape(item['capture_channel'] or 'Not recorded')}</td>"
        f"<td class=\"status {escape(item['signal_status'])}\">{escape(_status_label(item['signal_status']))}</td>"
        f"<td>{escape(item['notes'])}</td>"
        "</tr>"
        for item in inputs
    )
    projector_rows = "".join(
        "<tr>"
        f"<td><strong>{escape(item['label'])}</strong><small>{escape(item['source_name'] or '')}</small></td>"
        f"<td>{escape(str(item['monitor_index']) if item['monitor_index'] is not None else 'Unassigned')}</td>"
        f"<td class=\"status {escape(item['status'])}\">{escape(_status_label(item['status']))}</td>"
        f"<td>{escape(item['observed_display'] or '')}</td>"
        f"<td>{escape(item['notes'])}</td>"
        "</tr>"
        for item in projectors
    )
    check_rows = "".join(
        f"<li class=\"{'pass' if checked else 'fail'}\"><span>{'PASS' if checked else 'OPEN'}</span>{escape(check_id.replace('-', ' ').title())}</li>"
        for check_id, checked in checks.items()
    )
    notes = escape(session["notes"] or "No session notes recorded.")
    title = escape(room["name"])
    generated_at = escape(report["generated_at"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Field Test Report | {title}</title>
  <style>
    :root {{ color-scheme: light; font-family: "Segoe UI", sans-serif; color: #161616; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef0ed; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 24px auto; background: white; padding: 36px; border-top: 8px solid #c62828; }}
    header {{ display: flex; justify-content: space-between; gap: 24px; border-bottom: 2px solid #171717; padding-bottom: 20px; }}
    h1 {{ margin: 4px 0; font-size: 30px; }} h2 {{ margin-top: 34px; font-size: 19px; }}
    p, small {{ color: #565b58; }} small {{ display: block; margin-top: 3px; }}
    .eyebrow {{ color: #a51c1c; font: 700 12px/1 monospace; letter-spacing: .08em; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin: 24px 0; background: #c7cbc8; border: 1px solid #c7cbc8; }}
    .summary div {{ background: #f7f8f6; padding: 16px; }} .summary strong {{ display: block; font-size: 24px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} th {{ text-align: left; background: #202421; color: white; }} th, td {{ padding: 10px; border: 1px solid #d7dad7; vertical-align: top; }}
    .status {{ font-weight: 700; }} .status.pass, li.pass span {{ color: #176b3a; }} .status.fail, .status.wrong_display, .status.no_signal, li.fail span {{ color: #a51c1c; }}
    ul {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 20px; padding: 0; list-style: none; }} li {{ border-bottom: 1px solid #ddd; padding: 8px 0; }} li span {{ display: inline-block; width: 54px; font: 700 11px monospace; }}
    .notes {{ white-space: pre-wrap; padding: 16px; background: #f4f5f3; border-left: 4px solid #606661; }}
    footer {{ margin-top: 34px; padding-top: 14px; border-top: 1px solid #aaa; font: 11px monospace; overflow-wrap: anywhere; }}
    button {{ border: 0; background: #171717; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    @media (max-width: 720px) {{ main {{ width: 100%; margin: 0; padding: 20px; }} header {{ display: block; }} .summary {{ grid-template-columns: repeat(2, 1fr); }} table {{ display: block; overflow-x: auto; }} ul {{ grid-template-columns: 1fr; }} }}
    @media print {{ body {{ background: white; }} main {{ width: 100%; margin: 0; padding: 0; border-top: 0; }} button {{ display: none; }} h2 {{ break-after: avoid; }} table {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
<main>
  <header><div><div class="eyebrow">COMMISSIONING RECORD</div><h1>{title}</h1><p>Field test session {escape(report['session_id'])}</p></div><div><button onclick="window.print()">Print / Save PDF</button><p>Generated {generated_at}</p></div></header>
  <section class="summary">
    <div><strong>{summary['inputs_passed']} / {summary['input_count']}</strong><span>Inputs passed</span></div>
    <div><strong>{summary['projectors_passed']} / {summary['projector_count']}</strong><span>Projectors passed</span></div>
    <div><strong>{summary['checks_passed']} / {summary['check_count']}</strong><span>Checks passed</span></div>
    <div><strong>{mode_exercise['completed_cycles']}</strong><span>Mode cycles</span></div>
  </section>
  <h2>Floor-box input map</h2>
  <table><thead><tr><th>OBS input</th><th>Capture device</th><th>Channel</th><th>Signal</th><th>Notes</th></tr></thead><tbody>{input_rows}</tbody></table>
  <h2>Projector output map</h2>
  <table><thead><tr><th>Output</th><th>Monitor index</th><th>Result</th><th>Observed display</th><th>Notes</th></tr></thead><tbody>{projector_rows}</tbody></table>
  <h2>Acceptance checks</h2><ul>{check_rows}</ul>
  <h2>Exercise and soak</h2><p>Mode exercise: <strong>{escape(_status_label(mode_exercise['status']))}</strong>, {mode_exercise['switch_count']} switches across {mode_exercise['completed_cycles']} cycles. Soak started: {escape(str(soak['started_at'] or 'not started'))}; completed: {escape(str(soak['completed_at'] or 'not completed'))}.</p>
  <h2>Session notes</h2><div class="notes">{notes}</div>
  <footer>Configuration SHA-256: {escape(report['config_sha256'])}</footer>
</main>
</body>
</html>"""