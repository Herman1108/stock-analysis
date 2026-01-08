"""
Decision Panel Components for Dashboard
FINAL UI COPYWRITING - Professional, awam-friendly
"""

import dash_bootstrap_components as dbc
from dash import html


def create_decision_panel(stock_code, unified_data):
    """
    Action Panel - "Apa yang Perlu Dilakukan Hari Ini?"
    FINAL COPYWRITING: Clear action, sub-guidance, and next focus.
    """
    try:
        decision = unified_data.get('decision', {})
        accum = unified_data.get('accumulation', {})
        impulse = unified_data.get('impulse', {})
        confidence = accum.get('confidence', {})
        summary = accum.get('summary', {})
        sr = unified_data.get('support_resistance', {})

        # Get price context for actionable guidance
        current_price = sr.get('current_price', 0) or accum.get('current_price', 0)
        resistance_levels = sr.get('resistance_levels', [])
        key_resistance = resistance_levels[0] if resistance_levels else None
        key_support = sr.get('key_support', None)

        action = decision.get('action', 'WAIT')
        action_color = decision.get('color', 'secondary')
        action_icon = decision.get('icon', '⏳')
        reason = decision.get('reason', 'Tidak ada data')

        # Confidence metrics
        passed = confidence.get('passed', 0)
        total = confidence.get('total', 6)
        pass_rate = confidence.get('pass_rate', 0)
        conf_level = confidence.get('level', 'LOW')

        # Range info for sub-guidance
        range_pct = summary.get('range_pct', 0)

        # Confidence level text (Indonesian)
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

        # Get actual signal result (AKUMULASI/NETRAL/DISTRIBUSI)
        overall_signal = summary.get('overall_signal', 'NETRAL')
        signal_text = {
            'AKUMULASI': 'AKUMULASI',
            'DISTRIBUSI': 'DISTRIBUSI',
            'NETRAL': 'NETRAL'
        }.get(overall_signal, 'NETRAL')
        signal_color = {
            'AKUMULASI': 'success',
            'DISTRIBUSI': 'danger',
            'NETRAL': 'secondary'
        }.get(overall_signal, 'secondary')

        # FINAL COPYWRITING V2: Action label & description based on signal WITH PRICE CONTEXT
        if overall_signal == 'DISTRIBUSI':
            display_action = "EXIT"
            display_icon = "🚨"
            display_color = "danger"
            # Add price context for distribution
            if key_resistance:
                sub_guidance = f"Sinyal distribusi terdeteksi. EXIT direkomendasikan selama harga di bawah Rp {key_resistance:,.0f} (zona distribusi aktif)."
            else:
                sub_guidance = "Sinyal distribusi terdeteksi. Pertimbangkan mengamankan profit atau mengurangi eksposur."
            next_focus = [
                "Harga breakdown area support",
                "Volume distribusi meningkat",
                "Broker besar mulai keluar konsisten"
            ]
        elif overall_signal == 'AKUMULASI':
            display_action = "BUY ON WEAKNESS"
            display_icon = "🟢"
            display_color = "success"
            # Add price context for accumulation
            if key_support:
                sub_guidance = f"Ada indikasi akumulasi. Entry optimal di area Rp {key_support:,.0f} (zona support aktif)."
            else:
                sub_guidance = "Ada indikasi akumulasi. Fokus pada area support dan manajemen risiko."
            next_focus = [
                "Harga menyentuh zona support",
                "Volume konfirmasi saat pullback",
                "Broker besar konsisten akumulasi"
            ]
        else:  # NETRAL
            display_action = "WAIT"
            display_icon = "⏳"
            display_color = "secondary"
            sub_guidance = "Pasar belum memberikan konfirmasi arah. Observasi lebih aman daripada spekulasi."
            next_focus = [
                "Range menyempit < 20%",
                "Volume terserap konsisten >= 3 hari",
                "Sinyal akumulasi atau distribusi muncul"
            ]

        # Override with impulse if detected
        if is_impulse:
            display_action = "MOMENTUM"
            display_icon = "⚡"
            display_color = "danger"
            sub_guidance = "Pergerakan cepat terdeteksi. Risiko tinggi, potensi tinggi. Hanya untuk trader berpengalaman."
            next_focus = [
                "Pantau volume spike berkelanjutan",
                "Perhatikan resistance terdekat",
                "Siapkan exit strategy"
            ]

        # Confidence subtext explanation
        conf_subtext = "Sistem memiliki keyakinan tinggi berdasarkan kombinasi indikator teknikal & broker flow."

        return dbc.Card([
            dbc.CardHeader([
                html.Div([
                    html.I(className="fas fa-bullseye me-2 text-warning"),
                    html.Strong("Apa yang Perlu Dilakukan Hari Ini?", className="text-warning"),
                ], className="d-flex align-items-center")
            ], className="bg-transparent border-warning"),
            dbc.CardBody([
                dbc.Row([
                    # Action Label (MAIN - Besar) - Using display variables from signal
                    dbc.Col([
                        html.Div([
                            html.Span(display_icon, style={"fontSize": "48px"}),
                            html.H2(display_action, className=f"text-{display_color} fw-bold mb-0 mt-2"),
                        ], className="text-center")
                    ], md=3, className="d-flex align-items-center justify-content-center border-end"),

                    # Decision Details
                    dbc.Col([
                        # Sub-Guidance (WAJIB ADA)
                        html.Div([
                            html.P(sub_guidance, className="mb-2", style={"fontSize": "14px"})
                        ], className="mb-3"),

                        # 3 Metrics Row
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("Decision Confidence", className="text-muted d-block"),
                                    html.H4(conf_text, className=f"text-{conf_color} mb-0"),
                                    html.Small(f"{passed} dari {total} validasi terpenuhi", className="text-muted d-block"),
                                    html.Small(conf_subtext, className="text-muted", style={"fontSize": "10px"}),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Pass Rate Validasi", className="text-muted d-block"),
                                    html.H4(f"{pass_rate:.0f}%", className=f"text-{conf_color} mb-0"),
                                    html.Small("Persentase kriteria sistem", className="text-muted d-block"),
                                    html.Small("yang terpenuhi hari ini", className="text-muted", style={"fontSize": "10px"}),
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.Small("Sinyal Hari Ini", className="text-muted d-block"),
                                    html.H4(
                                        f"⚡ {signal_text}" if is_impulse else f"📊 {signal_text}",
                                        className=f"text-{'danger' if is_impulse else signal_color} mb-0",
                                        style={"fontSize": "16px"}
                                    ),
                                    html.Small(
                                        "Pergerakan cepat & agresif" if is_impulse else (
                                            "Pola pembelian terdeteksi" if overall_signal == 'AKUMULASI' else
                                            "Pola penjualan terdeteksi" if overall_signal == 'DISTRIBUSI' else
                                            "Belum ada pola jelas"
                                        ),
                                        className="text-muted d-block"
                                    ),
                                    html.Small(
                                        "via mesin Momentum" if is_impulse else "via mesin Akumulasi",
                                        className="text-muted", style={"fontSize": "10px"}
                                    ),
                                ], className="text-center")
                            ], width=4),
                        ], className="mb-3"),

                        # Next Focus (krusial - bikin user aktif menunggu)
                        html.Div([
                            html.Small([
                                html.I(className="fas fa-search me-1"),
                                html.Strong("Pantau jika:")
                            ], className="text-info d-block mb-1"),
                            html.Ul([
                                html.Li(html.Small(focus, className="text-muted"))
                                for focus in next_focus
                            ], className="mb-0 ps-3", style={"fontSize": "11px"})
                        ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.05)"}),
                    ], md=9)
                ])
            ], className="py-3")
        ], className="mb-3", style={"border": f"2px solid var(--bs-{display_color})", "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"})

    except Exception as e:
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-bullseye me-2"),
                "Action Panel"
            ]),
            dbc.CardBody(html.P(f"Error: {str(e)}", className="text-danger"))
        ], className="mb-3")


def create_why_signal_checklist(stock_code, validation_result):
    """
    Kenapa Sinyal Ini? - Checklist Validasi
    FINAL COPYWRITING: Clear status, checklist, tooltips.
    """
    try:
        if validation_result.get('error'):
            return html.Div()

        validations = validation_result.get('validations', {})
        overall_signal = validation_result.get('summary', {}).get('overall_signal', 'NETRAL')
        impulse = validation_result.get('impulse_signal', {})

        # Build checklist items with Indonesian labels
        checks = []

        # CPR Check
        cpr = validations.get('cpr', {})
        cpr_passed = cpr.get('passed', False)
        cpr_pct = cpr.get('cpr_pct', 50)
        cpr_detail = "indikasi akumulasi" if cpr_pct > 60 else ("indikasi distribusi" if cpr_pct < 40 else "netral")
        checks.append({
            'name': 'CPR (Close Position Ratio)',
            'passed': cpr_passed,
            'detail': f"{cpr_pct:.0f}% - {cpr_detail}",
            'tooltip': 'Posisi harga penutupan dalam range harian. >60% = pembeli dominan'
        })

        # Broker Influence
        broker = validations.get('broker_influence', {})
        broker_passed = broker.get('passed', False)
        broker_signal = broker.get('signal', 'NETRAL')
        broker_detail = "ada tanda awal akumulasi" if broker_passed else "belum ada tanda jelas"
        checks.append({
            'name': 'Pengaruh Broker',
            'passed': broker_passed,
            'detail': broker_detail,
            'tooltip': 'Net pengaruh broker dengan partisipasi tinggi terhadap harga'
        })

        # Elasticity
        elast = validations.get('elasticity', {})
        elast_passed = elast.get('passed', False)
        elast_detail = "terlihat penahanan jual" if elast_passed else "tidak ada penahanan"
        checks.append({
            'name': 'Elastisitas Volume',
            'passed': elast_passed,
            'detail': elast_detail,
            'tooltip': 'Volume naik tapi harga stabil = ada yang menyerap tekanan jual'
        })

        # Rotation
        rotation = validations.get('rotation', {})
        rotation_passed = rotation.get('passed', False)
        num_acc = rotation.get('num_accumulators', 0)
        rotation_detail = f"{num_acc} broker aktif"
        checks.append({
            'name': 'Rotasi Broker',
            'passed': rotation_passed,
            'detail': rotation_detail,
            'tooltip': 'Terlalu banyak broker aktif = pasar ramai spekulan, bukan akumulator utama'
        })

        # UV/DV Check
        uvdv = validations.get('uvdv', {})
        uvdv_passed = uvdv.get('passed', False)
        uvdv_ratio = uvdv.get('uvdv_ratio', 1.0)
        uvdv_detail = f"rasio {uvdv_ratio:.2f}x"
        checks.append({
            'name': 'Volume Naik/Turun',
            'passed': uvdv_passed,
            'detail': uvdv_detail,
            'tooltip': '>1.2x = volume saat harga naik lebih dominan'
        })

        # Failed Breaks
        failed = validations.get('failed_breaks', {})
        failed_passed = failed.get('passed', False)
        failed_bd = failed.get('failed_breakdowns', 0)
        failed_bo = failed.get('failed_breakouts', 0)
        failed_detail = f"gagal tembus: {failed_bd}x turun, {failed_bo}x naik"
        checks.append({
            'name': 'Gagal Tembus Level',
            'passed': failed_passed,
            'detail': failed_detail,
            'tooltip': 'Banyak gagal breakdown = support kuat, banyak gagal breakout = resistance kuat'
        })

        passed_count = sum(1 for c in checks if c['passed'])

        # Signal status with icon
        if impulse.get('impulse_detected'):
            status_icon = "⚡"
            status_text = "MOMENTUM"
            status_subtext = f"{passed_count} dari 6 kriteria terpenuhi. Pergerakan cepat terdeteksi - risiko tinggi."
            status_color = "danger"
        elif overall_signal == 'AKUMULASI':
            status_icon = "📊"
            status_text = "AKUMULASI"
            status_subtext = f"{passed_count} dari 6 kriteria terpenuhi. Pola pembelian bertahap terdeteksi."
            status_color = "success"
        elif overall_signal == 'DISTRIBUSI':
            status_icon = "🔴"
            status_text = "DISTRIBUSI"
            status_subtext = f"{passed_count} dari 6 kriteria terpenuhi. Pola pelepasan saham terdeteksi."
            status_color = "danger"
        else:
            status_icon = "⏳"
            status_text = "NETRAL"
            status_subtext = f"{passed_count} dari 6 kriteria terpenuhi. Belum ada pola yang cukup kuat untuk entry."
            status_color = "secondary"

        # Build checklist rows (2 columns)
        checklist_items = []
        for c in checks:
            checklist_items.append(
                dbc.Col([
                    html.Div([
                        html.Span(
                            "✅" if c['passed'] else "❌",
                            className=f"me-2"
                        ),
                        html.Span(
                            c['name'],
                            className="small",
                            style={'borderBottom': '1px dotted #6c757d', 'cursor': 'help'},
                            title=c['tooltip']
                        ),
                        html.Br(),
                        html.Small(c['detail'], className="text-muted ms-4")
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
                # Status Badge
                html.Div([
                    html.Span(status_icon, style={"fontSize": "24px"}, className="me-2"),
                    html.Span(status_text, className=f"badge bg-{status_color} fs-6 me-2"),
                ], className="mb-2"),

                # Subtext
                html.P(status_subtext, className="text-muted small mb-3"),

                # Checklist Validasi
                html.Div([
                    html.Small([
                        html.I(className="fas fa-list-check me-1"),
                        html.Strong("Checklist Validasi:")
                    ], className="text-info d-block mb-2"),
                    dbc.Row(checklist_items),
                    # Footer Edukatif
                    html.Hr(className="my-2", style={"opacity": "0.2"}),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Semakin banyak validasi terpenuhi, semakin kuat sinyal yang terbentuk."
                    ], className="text-muted fst-italic", style={"fontSize": "10px"})
                ], className="p-2 rounded", style={"backgroundColor": "rgba(255,255,255,0.03)"}),
            ])
        ], color="dark", outline=True, className="mb-3", style={"borderColor": "var(--bs-info)"})

    except Exception as e:
        return html.Div()
