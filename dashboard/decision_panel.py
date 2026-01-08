"""
Decision Panel Components for Dashboard
Adds "What Should I Do Today?" and "Why This Signal?" sections
"""

import dash_bootstrap_components as dbc
from dash import html


def create_decision_panel(stock_code, unified_data):
    """
    Decision Panel - "What Should I Do Today?"
    Mengikat semua data mentah menjadi keputusan aksi yang jelas.
    Panel ini adalah yang PALING PENTING di dashboard.
    """
    try:
        decision = unified_data.get('decision', {})
        accum = unified_data.get('accumulation', {})
        impulse = unified_data.get('impulse', {})
        confidence = accum.get('confidence', {})

        action = decision.get('action', 'WAIT')
        action_color = decision.get('color', 'secondary')
        action_icon = decision.get('icon', '⏳')
        reason = decision.get('reason', 'Tidak ada data')

        # Confidence metrics
        passed = confidence.get('passed', 0)
        total = confidence.get('total', 6)
        pass_rate = confidence.get('pass_rate', 0)
        conf_level = confidence.get('level', 'LOW')

        # Confidence level text
        conf_text = {
            'VERY_HIGH': 'SANGAT TINGGI',
            'HIGH': 'TINGGI',
            'MEDIUM': 'SEDANG',
            'LOW': 'RENDAH',
            'VERY_LOW': 'SANGAT RENDAH'
        }.get(conf_level, 'N/A')

        conf_color = {
            'VERY_HIGH': 'success',
            'HIGH': 'success',
            'MEDIUM': 'warning',
            'LOW': 'danger',
            'VERY_LOW': 'danger'
        }.get(conf_level, 'secondary')

        # Check for impulse signal
        is_impulse = impulse.get('impulse_detected', False)
        impulse_strength = impulse.get('strength', '') if is_impulse else ''

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-bullseye me-2 text-warning"),
                    html.Strong("APA YANG HARUS DILAKUKAN HARI INI?", className="text-warning"),
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-warning"),
            dbc.CardBody([
                dbc.Row([
                    # Decision Action (MAIN)
                    dbc.Col([
                        html.Div([
                            html.Span(action_icon, style={"fontSize": "48px"}),
                            html.H2(action, className=f"text-{action_color} fw-bold mb-0 mt-2"),
                        ], className="text-center")
                    ], md=3, className="d-flex align-items-center justify-content-center border-end"),

                    # Decision Details
                    dbc.Col([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Confidence", className="text-muted d-block"),
                                    html.H4(conf_text, className=f"text-{conf_color} mb-0"),
                                    html.Small(f"{passed}/{total} validasi lolos", className="text-muted"),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Pass Rate", className="text-muted d-block"),
                                    html.H4(f"{pass_rate:.0f}%", className=f"text-{conf_color} mb-0"),
                                    html.Small("dari kriteria", className="text-muted"),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Engine", className="text-muted d-block"),
                                    html.H4(
                                        f"⚡ {impulse_strength}" if is_impulse else "📊 Akumulasi",
                                        className=f"text-{'danger' if is_impulse else 'info'} mb-0",
                                        style={"fontSize": "16px"}
                                    ),
                                    html.Small("Momentum" if is_impulse else "Engine", className="text-muted"),
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-3"),

                        # Reason
                        html.Div([
                            html.I(className=f"fas fa-{'check-circle text-success' if action in ['ENTRY', 'ADD'] else 'exclamation-circle text-warning' if action in ['WAIT', 'HOLD'] else 'times-circle text-danger'} me-2"),
                            html.Span(reason, className="small")
                        ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),
                    ], md=9)
                ])
            ], className="py-3")
        ], className="mb-3", style={"border": f"2px solid var(--bs-{action_color})", "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"})

    except Exception as e:
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bullseye me-2"),
                "Decision Panel"
            ]),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_why_signal_checklist(stock_code, validation_result):
    """
    Create "Why This Signal" checklist - explains why current signal is what it is.
    Menampilkan checklist validasi yang terpenuhi dan tidak terpenuhi.
    """
    try:
        if validation_result.get('error'):
            return html.Div()

        validations = validation_result.get('validations', {})
        overall_signal = validation_result.get('summary', {}).get('overall_signal', 'NETRAL')
        impulse = validation_result.get('impulse_signal', {})

        # Build checklist items
        checks = []

        # CPR Check
        cpr = validations.get('cpr', {})
        cpr_passed = cpr.get('passed', False)
        cpr_signal = cpr.get('signal', 'NETRAL')
        cpr_pct = cpr.get('cpr_pct', 50)
        checks.append({
            'name': 'CPR (Close Position Ratio)',
            'passed': cpr_passed,
            'detail': f"{cpr_pct}% - {cpr_signal}",
            'tooltip': 'CPR > 60% = pembeli dominan, < 40% = penjual dominan'
        })

        # UV/DV Check
        uvdv = validations.get('uvdv', {})
        uvdv_passed = uvdv.get('passed', False)
        uvdv_ratio = uvdv.get('uvdv_ratio', 1.0)
        checks.append({
            'name': 'Volume Up/Down',
            'passed': uvdv_passed,
            'detail': f"Rasio {uvdv_ratio:.2f}x",
            'tooltip': '> 1.2x = volume naik dominan, < 0.8x = volume turun dominan'
        })

        # Broker Influence
        broker = validations.get('broker_influence', {})
        broker_passed = broker.get('passed', False)
        broker_signal = broker.get('signal', 'NETRAL')
        checks.append({
            'name': 'Broker Influence',
            'passed': broker_passed,
            'detail': broker_signal,
            'tooltip': 'Net pengaruh broker dengan partisipasi tinggi'
        })

        # Failed Breaks
        failed = validations.get('failed_breaks', {})
        failed_passed = failed.get('passed', False)
        failed_bd = failed.get('failed_breakdowns', 0)
        failed_bo = failed.get('failed_breakouts', 0)
        checks.append({
            'name': 'Failed Breaks',
            'passed': failed_passed,
            'detail': f"BD:{failed_bd} / BO:{failed_bo}",
            'tooltip': 'Banyak failed breakdown = support kuat'
        })

        # Elasticity
        elast = validations.get('elasticity', {})
        elast_passed = elast.get('passed', False)
        elast_signal = elast.get('signal', 'NETRAL')
        checks.append({
            'name': 'Volume Elasticity',
            'passed': elast_passed,
            'detail': elast_signal[:15] if elast_signal else 'N/A',
            'tooltip': 'Volume naik tapi harga diam = ada yang menyerap'
        })

        # Rotation
        rotation = validations.get('rotation', {})
        rotation_passed = rotation.get('passed', False)
        num_acc = rotation.get('num_accumulators', 0)
        checks.append({
            'name': 'Broker Rotation',
            'passed': rotation_passed,
            'detail': f"{num_acc} broker akumulasi",
            'tooltip': '>= 3 broker searah = institusional, bukan spekulan'
        })

        passed_count = sum(1 for c in checks if c['passed'])

        # Signal explanation
        if impulse.get('impulse_detected'):
            signal_explanation = "⚡ MOMENTUM/IMPULSE terdeteksi! Pergerakan agresif dengan volume spike. Risiko tinggi."
            explanation_color = "danger"
        elif overall_signal == 'AKUMULASI':
            signal_explanation = f"📊 AKUMULASI terdeteksi. {passed_count}/6 kriteria terpenuhi menunjukkan ada pengumpulan bertahap."
            explanation_color = "success"
        elif overall_signal == 'DISTRIBUSI':
            signal_explanation = f"🔴 DISTRIBUSI terdeteksi. Pelaku besar sedang melepas saham bertahap."
            explanation_color = "danger"
        else:
            signal_explanation = f"⏳ NETRAL - Hanya {passed_count}/6 kriteria terpenuhi. Belum ada pola jelas."
            explanation_color = "secondary"

        # Build checklist rows (2 columns)
        checklist_items = []
        for i, c in enumerate(checks):
            checklist_items.append(
                dbc.Col([
                    html.Div([
                        html.Span(
                            "✅" if c['passed'] else "❌",
                            className=f"me-2 {'text-success' if c['passed'] else 'text-danger'}"
                        ),
                        html.Span(
                            c['name'],
                            className="small",
                            style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                            title=c['tooltip']
                        ),
                        html.Small(f" ({c['detail']})", className="text-muted")
                    ], className="mb-2")
                ], width=6)
            )

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-clipboard-check me-2 text-info"),
                    html.Strong("Kenapa Sinyal Ini?", className="text-info"),
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-info"),
            dbc.CardBody([
                # Signal explanation
                dbc.Alert(signal_explanation, color=explanation_color, className="mb-3 py-2"),

                # Checklist
                html.Div([
                    dbc.Row(checklist_items)
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"}),

                # Summary
                html.Div([
                    html.Small([
                        html.Strong(f"{passed_count}/6 "),
                        "validasi terpenuhi. ",
                        "Semakin banyak validasi, semakin kuat sinyalnya." if passed_count >= 4 else "Butuh minimal 4/6 untuk sinyal yang reliable."
                    ], className="text-muted")
                ], className="mt-2 text-center")
            ])
        ], color="dark", outline=True, className="mb-3", style={"borderColor": "var(--bs-info)"})

    except Exception as e:
        return html.Div()
