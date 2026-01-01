"""
Broker Classification Configuration
Klasifikasi broker berdasarkan kepemilikan:
- FOREIGN (Asing): Broker dengan parent company asing
- BUMN (Pemerintah): Broker milik BUMN/Pemerintah
- LOCAL (Lokal): Broker lokal swasta
"""

# Foreign brokers - berdasarkan parent company asing
# Format: broker_code: (name, parent_country)
FOREIGN_BROKERS = {
    # US Investment Banks
    'MS': ('Morgan Stanley Sekuritas Indonesia', 'US'),
    'BK': ('J.P. Morgan Sekuritas Indonesia', 'US'),
    'CG': ('Citigroup Sekuritas Indonesia', 'US'),
    'CS': ('Credit Suisse Sekuritas Indonesia', 'Switzerland'),  # Now UBS

    # European Banks
    'AK': ('UBS Sekuritas Indonesia', 'Switzerland'),
    'GW': ('HSBC Sekuritas Indonesia', 'UK'),
    'RX': ('Macquarie Sekuritas Indonesia', 'Australia'),
    'KZ': ('CLSA Sekuritas Indonesia', 'Hong Kong'),

    # Singapore Banks
    'AI': ('UOB Kay Hian Sekuritas', 'Singapore'),
    'DP': ('DBS Vickers Sekuritas Indonesia', 'Singapore'),
    'KK': ('Phillip Sekuritas Indonesia', 'Singapore'),
    'TP': ('OCBC Sekuritas Indonesia', 'Singapore'),
    'YU': ('CGS International Sekuritas Indonesia', 'Singapore'),

    # Korean Investment
    'AG': ('Kiwoom Sekuritas Indonesia', 'Korea'),
    'AH': ('Shinhan Sekuritas Indonesia', 'Korea'),
    'BQ': ('Korea Investment and Sekuritas Indonesia', 'Korea'),
    'XA': ('NH Korindo Sekuritas Indonesia', 'Korea'),
    'YP': ('Mirae Asset Sekuritas Indonesia', 'Korea'),

    # Taiwan
    'HD': ('KGI Sekuritas Indonesia', 'Taiwan'),
    'FS': ('Yuanta Sekuritas Indonesia', 'Taiwan'),
    'CP': ('KB Valbury Sekuritas', 'Korea'),  # KB Financial Group

    # Malaysia
    'ZP': ('Maybank Sekuritas Indonesia', 'Malaysia'),
    'DR': ('RHB Sekuritas Indonesia', 'Malaysia'),
    'DU': ('KAF Sekuritas Indonesia', 'Malaysia'),

    # China/HK
    'GI': ('Webull Sekuritas Indonesia', 'China'),

    # Japan
    # None currently active
}

# BUMN/Government-linked brokers
BUMN_BROKERS = {
    'CC': ('Mandiri Sekuritas', 'Bank Mandiri'),
    'NI': ('BNI Sekuritas', 'Bank BNI'),
    'OD': ('BRI Danareksa Sekuritas', 'Bank BRI + Danareksa'),
    'DX': ('Bahana Sekuritas', 'Bahana Pembinaan Usaha Indonesia'),
    'JB': ('BJB Sekuritas', 'Bank BJB'),
}

# Color codes for visualization
BROKER_COLORS = {
    'FOREIGN': '#dc3545',      # Red - Asing
    'BUMN': '#28a745',         # Green - Pemerintah/BUMN
    'LOCAL': '#6f42c1',        # Purple - Lokal
}

# Display names
BROKER_TYPE_NAMES = {
    'FOREIGN': 'Asing',
    'BUMN': 'BUMN/Pemerintah',
    'LOCAL': 'Lokal',
}


def get_broker_type(broker_code: str) -> str:
    """
    Klasifikasi broker berdasarkan kode.

    Returns:
        'FOREIGN' untuk broker asing
        'BUMN' untuk broker BUMN/pemerintah
        'LOCAL' untuk broker lokal swasta
    """
    broker_code = broker_code.upper().strip()

    if broker_code in FOREIGN_BROKERS:
        return 'FOREIGN'
    elif broker_code in BUMN_BROKERS:
        return 'BUMN'
    else:
        return 'LOCAL'


def get_broker_color(broker_code: str) -> str:
    """Get color for broker based on classification."""
    broker_type = get_broker_type(broker_code)
    return BROKER_COLORS.get(broker_type, BROKER_COLORS['LOCAL'])


def get_broker_info(broker_code: str) -> dict:
    """
    Get complete broker information.

    Returns dict with:
        - code: broker code
        - type: FOREIGN/BUMN/LOCAL
        - type_name: Display name in Indonesian
        - color: Hex color code
        - name: Full broker name (if known)
        - parent: Parent company/country (if applicable)
    """
    broker_code = broker_code.upper().strip()
    broker_type = get_broker_type(broker_code)

    info = {
        'code': broker_code,
        'type': broker_type,
        'type_name': BROKER_TYPE_NAMES.get(broker_type, 'Unknown'),
        'color': BROKER_COLORS.get(broker_type, BROKER_COLORS['LOCAL']),
        'name': None,
        'parent': None,
    }

    if broker_code in FOREIGN_BROKERS:
        info['name'], info['parent'] = FOREIGN_BROKERS[broker_code]
    elif broker_code in BUMN_BROKERS:
        info['name'], info['parent'] = BUMN_BROKERS[broker_code]

    return info


def classify_brokers(broker_codes: list) -> dict:
    """
    Classify a list of broker codes.

    Returns dict with counts and lists for each type.
    """
    result = {
        'FOREIGN': {'count': 0, 'brokers': [], 'color': BROKER_COLORS['FOREIGN']},
        'BUMN': {'count': 0, 'brokers': [], 'color': BROKER_COLORS['BUMN']},
        'LOCAL': {'count': 0, 'brokers': [], 'color': BROKER_COLORS['LOCAL']},
    }

    for code in broker_codes:
        broker_type = get_broker_type(code)
        result[broker_type]['count'] += 1
        result[broker_type]['brokers'].append(code)

    return result


def is_foreign_broker(broker_code: str) -> bool:
    """Check if broker is foreign."""
    return get_broker_type(broker_code) == 'FOREIGN'


def is_bumn_broker(broker_code: str) -> bool:
    """Check if broker is BUMN/government."""
    return get_broker_type(broker_code) == 'BUMN'


def is_local_broker(broker_code: str) -> bool:
    """Check if broker is local private."""
    return get_broker_type(broker_code) == 'LOCAL'


# Export all foreign broker codes as a set for quick lookup
FOREIGN_BROKER_CODES = set(FOREIGN_BROKERS.keys())
BUMN_BROKER_CODES = set(BUMN_BROKERS.keys())


if __name__ == '__main__':
    # Test
    test_codes = ['MS', 'YP', 'CC', 'NI', 'PD', 'XL', 'LG']
    print("Broker Classification Test:")
    print("-" * 50)
    for code in test_codes:
        info = get_broker_info(code)
        print(f"{code}: {info['type_name']} ({info['type']}) - Color: {info['color']}")
