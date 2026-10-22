"""Valida independientemente integridad, limpieza, contabilidad y patrones sinteticos."""

import calendar
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIRST_DAY = date(2026, 4, 1)
LAST_DAY = date(2026, 9, 30)
EXPECTED_HEADERS = {
    "clientes.csv": [
        "cliente_id", "nombre_sintetico", "fecha_alta", "segmento",
        "grupo_edad", "provincia", "sucursal_id",
    ],
    "sucursales.csv": ["sucursal_id", "nombre_sintetico", "provincia"],
    "productos.csv": ["producto_id", "nombre_sintetico", "familia", "moneda"],
    "cuentas.csv": [
        "cuenta_id", "cliente_id", "producto_id", "fecha_apertura",
        "moneda", "saldo_inicial",
    ],
    "transacciones.csv": [
        "transaccion_id", "cuenta_id", "fecha_hora", "tipo_transaccion",
        "direccion", "canal", "monto", "moneda", "estado",
    ],
    "creditos.csv": [
        "credito_id", "cliente_id", "producto_id", "fecha_desembolso",
        "fecha_corte", "moneda", "monto_original", "saldo_capital",
        "tasa_anual_pct", "plazo_meses", "dias_mora",
    ],
    "calendario.csv": [
        "fecha", "anio", "trimestre", "mes", "nombre_mes", "dia_mes",
        "dia_semana", "nombre_dia", "es_fin_semana",
    ],
}
EXPECTED_COUNTS = {
    "clientes.csv": 1200, "sucursales.csv": 7, "productos.csv": 5,
    "cuentas.csv": 1800, "transacciones.csv": 72360,
    "creditos.csv": 400, "calendario.csv": 183,
}
PROVINCES = {
    "San Jose", "Alajuela", "Cartago", "Heredia",
    "Guanacaste", "Puntarenas", "Limon",
}
CREDIT_TYPES = {"SALARIO", "DEPOSITO", "TRANSFERENCIA_RECIBIDA", "INTERES"}
DEBIT_TYPES = {"RETIRO", "PAGO_SERVICIO", "COMPRA", "TRANSFERENCIA_ENVIADA", "COMISION"}
CHANNELS = {"BANCA_MOVIL", "WEB", "ATM", "SUCURSAL"}
MONTH_NAMES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
DAY_NAMES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
EXPECTED_CLEANING = {
    "raw": 72360, "duplicates": 288, "quarantine": 72,
    "quarantine_by_reason": {
        "invalid_account": 24, "invalid_timestamp": 24, "negative_amount": 24,
    },
    "clean": 72000, "normalize": 720, "blanks": 360,
}
EXPECTED_ANOMALIES = {
    "exact_duplicates": 288, "invalid_account": 24,
    "invalid_timestamp": 24, "negative_amount": 24,
    "channel_whitespace_lowercase": 720, "channel_blank": 360,
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def iso_date(text, context):
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", text), f"{context}: fecha no ISO: {text!r}")
    return date.fromisoformat(text)


def iso_timestamp(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text):
        raise ValueError(f"Timestamp no ISO local: {text!r}")
    return datetime.fromisoformat(text)


def cents(text, context):
    require(
        re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d{2}", text),
        f"{context}: importe invalido: {text!r}",
    )
    negative = text.startswith("-")
    whole, fraction = text.lstrip("-").split(".")
    result = int(whole) * 100 + int(fraction)
    require(not (negative and result == 0), f"{context}: cero negativo")
    return -result if negative else result


def integer(text, context):
    require(re.fullmatch(r"(?:0|[1-9]\d*)", text), f"{context}: entero invalido: {text!r}")
    return int(text)


def money(value):
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) // 100}.{abs(value) % 100:02d}"


def ratio(numerator, denominator):
    return str(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
    )


def unique_index(rows, key, pattern, context):
    index = {}
    for position, row in enumerate(rows, 2):
        identifier = row[key]
        require(re.fullmatch(pattern, identifier), f"{context}:{position}: ID invalido {identifier!r}")
        require(identifier not in index, f"{context}:{position}: PK duplicada {identifier}")
        require(all(value != "" for value in row.values()), f"{context}:{position}: campo vacio")
        index[identifier] = row
    return index


def read_tables(manifest):
    require(manifest["counts"] == EXPECTED_COUNTS, "Conteos del manifiesto no pactados")
    require(set(manifest["files"]) == set(EXPECTED_HEADERS), "Lista de archivos del manifiesto incorrecta")
    tables = {}
    sizes = {}
    for name, headers in EXPECTED_HEADERS.items():
        path = ROOT / "csv" / name
        payload = path.read_bytes()
        require(payload.startswith(b"\xef\xbb\xbf"), f"{name}: falta BOM UTF-8")
        require(b"\xef\xbb\xbf" not in payload[3:], f"{name}: BOM interno")
        metadata = manifest["files"][name]
        require(metadata["sha256"] == hashlib.sha256(payload).hexdigest(), f"{name}: SHA-256 distinto")
        require(metadata["headers"] == headers, f"{name}: esquema del manifiesto distinto")
        require(metadata["size_bytes"] == len(payload), f"{name}: tamano distinto")
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
        require(next(reader) == headers, f"{name}: encabezado incorrecto")
        rows = []
        for position, values in enumerate(reader, 2):
            require(len(values) == len(headers), f"{name}:{position}: cantidad de columnas incorrecta")
            rows.append(dict(zip(headers, values)))
        require(len(rows) == EXPECTED_COUNTS[name], f"{name}: conteo {len(rows)} inesperado")
        require(metadata["row_count"] == len(rows), f"{name}: conteo difiere del manifiesto")
        tables[name] = rows
        sizes[name] = len(payload)
    return tables, sizes


def validate_dimensions(tables):
    branches = unique_index(tables["sucursales.csv"], "sucursal_id", r"SUC\d{2}", "sucursales")
    require(set(branches) == {f"SUC{i:02d}" for i in range(1, 8)}, "IDs de sucursales incorrectos")
    require({row["provincia"] for row in branches.values()} == PROVINCES, "Provincias incorrectas")
    for identifier, row in branches.items():
        require(row["nombre_sintetico"] == f"Sucursal sintetica {int(identifier[3:]):02d}", identifier)

    products = unique_index(tables["productos.csv"], "producto_id", r"PRD\d{2}", "productos")
    families = ("AHORRO", "CORRIENTE", "PLAZO", "CREDITO_PERSONAL", "CREDITO_PYME")
    require(set(products) == {f"PRD{i:02d}" for i in range(1, 6)}, "IDs de productos incorrectos")
    for index, family in enumerate(families, 1):
        product = products[f"PRD{index:02d}"]
        require(product["familia"] == family, f"Familia incorrecta PRD{index:02d}")
        require(product["moneda"] == "CRC", "Moneda de producto incorrecta")
        require(product["nombre_sintetico"] == f"Producto sintetico {index:02d}", "Nombre de producto no sintetico")

    clients = unique_index(tables["clientes.csv"], "cliente_id", r"CLI\d{6}", "clientes")
    require(set(clients) == {f"CLI{i:06d}" for i in range(1, 1201)}, "IDs de clientes incorrectos")
    registration_dates = {}
    for identifier, row in clients.items():
        require(row["nombre_sintetico"] == f"Cliente sintetico {int(identifier[3:]):04d}", identifier)
        require(row["segmento"] in {"ASALARIADO", "INDEPENDIENTE", "PENSIONADO", "PYME"}, f"{identifier}: segmento")
        require(row["grupo_edad"] in {"18-29", "30-44", "45-59", "60+"}, f"{identifier}: grupo edad")
        require(row["sucursal_id"] in branches, f"{identifier}: sucursal huerfana")
        require(row["provincia"] == branches[row["sucursal_id"]]["provincia"], f"{identifier}: provincia")
        registered = iso_date(row["fecha_alta"], identifier)
        require(registered < FIRST_DAY, f"{identifier}: alta posterior al inicio")
        registration_dates[identifier] = registered

    accounts = unique_index(tables["cuentas.csv"], "cuenta_id", r"CTA\d{6}", "cuentas")
    require(set(accounts) == {f"CTA{i:06d}" for i in range(1, 1801)}, "IDs de cuentas incorrectos")
    account_clients = set()
    opening_balances = {}
    for identifier, row in accounts.items():
        client_id = row["cliente_id"]
        require(client_id in clients, f"{identifier}: cliente huerfano")
        account_clients.add(client_id)
        require(row["producto_id"] in {"PRD01", "PRD02", "PRD03"}, f"{identifier}: producto no depositario")
        require(row["producto_id"] in products, f"{identifier}: producto huerfano")
        require(row["moneda"] == "CRC", f"{identifier}: moneda")
        opened = iso_date(row["fecha_apertura"], identifier)
        require(registration_dates[client_id] <= opened < FIRST_DAY, f"{identifier}: apertura fuera de orden")
        opening_balances[identifier] = cents(row["saldo_inicial"], identifier)
        require(opening_balances[identifier] >= 0, f"{identifier}: saldo inicial negativo")
    require(account_clients == set(clients), "Clientes sin cuenta")

    loans = unique_index(tables["creditos.csv"], "credito_id", r"PRE\d{6}", "creditos")
    require(set(loans) == {f"PRE{i:06d}" for i in range(1, 401)}, "IDs de creditos incorrectos")
    for identifier, row in loans.items():
        client_id = row["cliente_id"]
        require(client_id in clients, f"{identifier}: cliente huerfano")
        require(row["producto_id"] in {"PRD04", "PRD05"}, f"{identifier}: producto no crediticio")
        require(row["producto_id"] in products, f"{identifier}: producto huerfano")
        require(row["moneda"] == "CRC", f"{identifier}: moneda")
        disbursed = iso_date(row["fecha_desembolso"], identifier)
        cutoff = iso_date(row["fecha_corte"], identifier)
        require(cutoff == LAST_DAY, f"{identifier}: fecha de corte")
        require(registration_dates[client_id] <= disbursed <= cutoff, f"{identifier}: desembolso fuera de orden")
        original = cents(row["monto_original"], identifier)
        outstanding = cents(row["saldo_capital"], identifier)
        require(original > 0 and 0 < outstanding <= original, f"{identifier}: capital")
        require(cents(row["tasa_anual_pct"], identifier) >= 0, f"{identifier}: tasa negativa")
        term = integer(row["plazo_meses"], identifier)
        require(1 <= term <= 120, f"{identifier}: plazo")
        month_index = disbursed.year * 12 + disbursed.month - 1 + term
        year, month_zero = divmod(month_index, 12)
        maturity = date(
            year, month_zero + 1,
            min(disbursed.day, calendar.monthrange(year, month_zero + 1)[1]),
        )
        require(maturity > cutoff, f"{identifier}: cartera positiva posterior al plazo")
        arrears = integer(row["dias_mora"], identifier)
        require(0 <= arrears <= min(120, (cutoff - disbursed).days), f"{identifier}: mora")

    calendar_rows = tables["calendario.csv"]
    calendar_index = unique_index(calendar_rows, "fecha", r"\d{4}-\d{2}-\d{2}", "calendario")
    expected_dates = [
        FIRST_DAY + timedelta(days=offset)
        for offset in range((LAST_DAY - FIRST_DAY).days + 1)
    ]
    require(list(calendar_index) == [day.isoformat() for day in expected_dates], "Calendario incompleto o desordenado")
    for current, row in zip(expected_dates, calendar_rows):
        expected = {
            "fecha": current.isoformat(), "anio": str(current.year),
            "trimestre": str((current.month - 1) // 3 + 1),
            "mes": str(current.month), "nombre_mes": MONTH_NAMES[current.month - 1],
            "dia_mes": str(current.day), "dia_semana": str(current.isoweekday()),
            "nombre_dia": DAY_NAMES[current.weekday()],
            "es_fin_semana": "1" if current.weekday() >= 5 else "0",
        }
        require(row == expected, f"Calendario incorrecto {current}")
    return accounts, opening_balances


def validate_transactions(rows, accounts):
    seen = {}
    duplicate_ids = Counter()
    quarantine = Counter()
    clean = []
    normalized_count = blank_count = 0
    for position, row in enumerate(rows, 2):
        identifier = row["transaccion_id"]
        context = f"transacciones.csv:{position} ({identifier})"
        require(re.fullmatch(r"TX\d{8}", identifier), f"{context}: ID")
        require(all(value != "" for key, value in row.items() if key != "canal"), f"{context}: campo vacio")
        if identifier in seen:
            require(row == seen[identifier], f"{context}: mismo ID con payload diferente")
            duplicate_ids[identifier] += 1
            require(row["canal"] in CHANNELS, f"{context}: duplicado de registro contaminado")
            continue
        seen[identifier] = row
        require(row["moneda"] == "CRC", f"{context}: moneda")
        require(row["estado"] == "APLICADA", f"{context}: estado")
        tx_type = row["tipo_transaccion"]
        require(tx_type in CREDIT_TYPES | DEBIT_TYPES, f"{context}: tipo")
        expected_direction = "CREDITO" if tx_type in CREDIT_TYPES else "DEBITO"
        require(row["direccion"] == expected_direction, f"{context}: direccion incompatible")
        normalized_channel = row["canal"].strip().upper()
        require(normalized_channel in CHANNELS or row["canal"] == "", f"{context}: canal desconocido")
        amount = cents(row["monto"], context)
        reasons = []
        if row["cuenta_id"] not in accounts:
            reasons.append("invalid_account")
        try:
            timestamp = iso_timestamp(row["fecha_hora"])
        except ValueError:
            timestamp = None
            reasons.append("invalid_timestamp")
        if amount < 0:
            reasons.append("negative_amount")
        require(amount != 0, f"{context}: monto cero no documentado")
        if timestamp is not None:
            require(FIRST_DAY <= timestamp.date() <= LAST_DAY, f"{context}: fuera del periodo")
        if reasons:
            require(len(reasons) == 1, f"{context}: errores superpuestos {reasons}")
            require(int(identifier[2:]) > 72000, f"{context}: error dentro de la base")
            require(row["canal"] in CHANNELS, f"{context}: error con canal contaminado")
            quarantine[reasons[0]] += 1
            continue
        require(1 <= int(identifier[2:]) <= 72000, f"{context}: fila adicional no documentada")
        if row["canal"] == "":
            blank_count += 1
        elif row["canal"] != normalized_channel:
            require(
                row["canal"] != row["canal"].strip()
                and row["canal"].strip() == row["canal"].strip().lower(),
                f"{context}: contaminacion de canal no pactada",
            )
            normalized_count += 1
        clean.append({
            **row, "canal": normalized_channel or "NO_INFORMADO",
            "cents": amount, "timestamp": timestamp,
        })

    require(set(seen) == {f"TX{i:08d}" for i in range(1, 72073)}, "IDs transaccionales faltantes o extras")
    require(len(duplicate_ids) == 288 and set(duplicate_ids.values()) == {1}, "Duplicados no son 288 pares exactos")
    require(all(int(identifier[2:]) <= 72000 for identifier in duplicate_ids), "Duplicado de fila en cuarentena")
    actual_cleaning = {
        "raw": len(rows), "duplicates": sum(duplicate_ids.values()),
        "quarantine": sum(quarantine.values()),
        "quarantine_by_reason": dict(quarantine), "clean": len(clean),
        "normalize": normalized_count, "blanks": blank_count,
    }
    require(actual_cleaning == EXPECTED_CLEANING, f"Limpieza incorrecta: {actual_cleaning}")
    account_activity = Counter(row["cuenta_id"] for row in clean)
    require(set(account_activity) == set(accounts), "Cuentas sin transacciones")
    require(len(set(account_activity.values())) > 1, "Actividad por cuenta perfectamente uniforme")
    return clean, actual_cleaning


def validate_financials(clean, opening_balances, manifest):
    movements = defaultdict(list)
    credit = debit = 0
    for row in clean:
        movements[row["cuenta_id"]].append(row)
        if row["direccion"] == "CREDITO":
            credit += row["cents"]
        else:
            debit += row["cents"]
    closing = {}
    minimum_balance = min(opening_balances.values())
    for account_id, opening in opening_balances.items():
        balance = opening
        for row in sorted(
            movements[account_id],
            key=lambda transaction: (transaction["timestamp"], transaction["transaccion_id"]),
        ):
            balance += row["cents"] if row["direccion"] == "CREDITO" else -row["cents"]
            require(balance >= 0, f"{account_id}: saldo negativo tras {row['transaccion_id']}: {money(balance)}")
            minimum_balance = min(minimum_balance, balance)
        closing[account_id] = balance
    opening = sum(opening_balances.values())
    final = sum(closing.values())
    require(final == opening + credit - debit, "Identidad contable no cuadra")
    actual = {}
    for key, value in (("credit", credit), ("debit", debit), ("opening", opening), ("final", final)):
        actual[f"{key}_cents"] = str(value)
        actual[f"{key}_crc"] = money(value)
    require(actual == manifest["expected_accounting"], f"Totales contables difieren: {actual}")
    return actual, money(minimum_balance)


def validate_analytics(clean, manifest):
    monthly = Counter(row["timestamp"].strftime("%Y-%m") for row in clean)
    expected_months = [f"2026-{month:02d}" for month in range(4, 10)]
    require(set(monthly) == set(expected_months), "Meses transaccionales incorrectos")
    require(
        all(monthly[left] < monthly[right] for left, right in zip(expected_months, expected_months[1:])),
        f"Volumen mensual no creciente: {dict(monthly)}",
    )
    require(monthly["2026-09"] * 100 >= monthly["2026-04"] * 110, "Septiembre no supera abril en 10%")
    salaries = [row for row in clean if row["tipo_transaccion"] == "SALARIO"]
    require(len(salaries) > 0, "No hay salarios")
    payday_count = sum(
        row["timestamp"].day in (
            15, calendar.monthrange(row["timestamp"].year, row["timestamp"].month)[1]
        )
        for row in salaries
    )
    require(payday_count * 100 >= len(salaries) * 60, "Concentracion salarial inferior al 60%")
    channels = Counter(row["canal"] for row in clean)
    require(set(channels) == CHANNELS | {"NO_INFORMADO"}, "Canales normalizados incorrectos")
    require(
        all(channels["BANCA_MOVIL"] > count for name, count in channels.items() if name != "BANCA_MOVIL"),
        f"BANCA_MOVIL no es lider: {dict(channels)}",
    )
    require(channels["NO_INFORMADO"] == 360, "NO_INFORMADO no coincide con blancos")
    actual = {
        "monthly_transaction_counts": dict(sorted(monthly.items())),
        "september_to_april_count_ratio": ratio(monthly["2026-09"], monthly["2026-04"]),
        "salary_count": len(salaries), "salary_payday_count": payday_count,
        "salary_payday_share": ratio(payday_count, len(salaries)),
        "normalized_channel_counts": dict(sorted(channels.items())),
        "most_used_channel": "BANCA_MOVIL",
    }
    require(actual == manifest["expected_analytics"], f"Analitica difiere del manifiesto: {actual}")
    return actual


def main():
    manifest_path = ROOT / "manifiesto.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["is_synthetic"] is True, "Falta identificacion sintetica")
    require(manifest["seed"] == 20261022, "Semilla incorrecta")
    require(manifest["period"] == {"start": "2026-04-01", "end": "2026-09-30"}, "Periodo incorrecto")
    require(manifest["timezone"] == "America/Costa_Rica", "Zona horaria incorrecta")
    require(manifest["currency"] == "CRC", "Moneda del manifiesto incorrecta")
    require(
        manifest["csv_format"] == {
            "encoding": "utf-8-sig", "delimiter": ",",
            "line_terminator": "\\n", "decimal_places": 2,
        },
        "Formato CSV del manifiesto incorrecto",
    )
    require(manifest["anomalies"] == EXPECTED_ANOMALIES, "Anomalias del manifiesto incorrectas")
    require(manifest["expected_cleaning"] == EXPECTED_CLEANING, "Limpieza del manifiesto incorrecta")
    tables, sizes = read_tables(manifest)
    accounts, opening_balances = validate_dimensions(tables)
    clean, cleaning = validate_transactions(tables["transacciones.csv"], accounts)
    accounting, minimum = validate_financials(clean, opening_balances, manifest)
    analytics = validate_analytics(clean, manifest)
    manifest_size = manifest_path.stat().st_size
    print(json.dumps({
        "status": "success", "directory": str(ROOT),
        "counts": {name: len(rows) for name, rows in tables.items()},
        "verified_csv_sha256": {name: manifest["files"][name]["sha256"] for name in EXPECTED_HEADERS},
        "cleaning": cleaning, "accounting": accounting, "analytics": analytics,
        "accounts_with_transactions": len(accounts),
        "transactions_per_account": {
            "min": min(Counter(row["cuenta_id"] for row in clean).values()),
            "max": max(Counter(row["cuenta_id"] for row in clean).values()),
        },
        "minimum_account_balance_crc": minimum,
        "sizes_bytes": {
            "csv": sizes, "csv_total": sum(sizes.values()),
            "manifest": manifest_size,
            "csv_and_manifest_total": sum(sizes.values()) + manifest_size,
        },
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
