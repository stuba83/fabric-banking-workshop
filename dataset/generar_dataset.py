"""Genera datos bancarios exclusivamente sinteticos, sin dependencias externas."""

import argparse
import calendar
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


SEED = 20261022
START = date(2026, 4, 1)
END = date(2026, 9, 30)
PREVIOUS_DAY = START - timedelta(days=1)
ROOT = Path(__file__).resolve().parent
HEADERS = {
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
PROVINCES = (
    "San Jose", "Alajuela", "Cartago", "Heredia",
    "Guanacaste", "Puntarenas", "Limon",
)
FAMILIES = ("AHORRO", "CORRIENTE", "PLAZO", "CREDITO_PERSONAL", "CREDITO_PYME")
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
DAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
CHANNELS = ("BANCA_MOVIL", "WEB", "ATM", "SUCURSAL")
CREDIT_TYPES = {"SALARIO", "DEPOSITO", "TRANSFERENCIA_RECIBIDA", "INTERES"}
TRANSACTION_TYPES = (
    "SALARIO", "DEPOSITO", "RETIRO", "PAGO_SERVICIO", "COMPRA",
    "TRANSFERENCIA_RECIBIDA", "TRANSFERENCIA_ENVIADA", "INTERES", "COMISION",
)
TYPE_WEIGHTS = (9, 19, 11, 14, 26, 8, 8, 3, 2)
AMOUNT_RANGES_CRC = {
    "SALARIO": (350_000, 1_800_000),
    "DEPOSITO": (10_000, 900_000),
    "RETIRO": (5_000, 150_000),
    "PAGO_SERVICIO": (3_000, 110_000),
    "COMPRA": (1_000, 180_000),
    "TRANSFERENCIA_RECIBIDA": (5_000, 650_000),
    "TRANSFERENCIA_ENVIADA": (5_000, 550_000),
    "INTERES": (100, 8_000),
    "COMISION": (100, 3_000),
}


def money(cents):
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"


def parse_generated_money(text):
    whole, fraction = text.split(".")
    return int(whole) * 100 + int(fraction)


def ratio(numerator, denominator):
    return str(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
    )


def random_date(rng, first, last):
    return first + timedelta(days=rng.randrange((last - first).days + 1))


def monthly_counts(total):
    weights = (100, 102, 105, 108, 112, 116)
    denominator = sum(weights)
    counts = [total * weight // denominator for weight in weights]
    residual_order = sorted(
        range(len(weights)),
        key=lambda index: (-(total * weights[index] % denominator), index),
    )
    for index in residual_order[:total - sum(counts)]:
        counts[index] += 1
    return counts


def build_dataset():
    rng = random.Random(SEED)
    tables = {name: [] for name in HEADERS}
    branches = tables["sucursales.csv"]
    for index, province in enumerate(PROVINCES, 1):
        branches.append({
            "sucursal_id": f"SUC{index:02d}",
            "nombre_sintetico": f"Sucursal sintetica {index:02d}",
            "provincia": province,
        })
    for index, family in enumerate(FAMILIES, 1):
        tables["productos.csv"].append({
            "producto_id": f"PRD{index:02d}",
            "nombre_sintetico": f"Producto sintetico {index:02d}",
            "familia": family,
            "moneda": "CRC",
        })

    clients = tables["clientes.csv"]
    for index in range(1, 1201):
        branch = rng.choices(branches, weights=(28, 20, 12, 15, 8, 10, 7), k=1)[0]
        clients.append({
            "cliente_id": f"CLI{index:06d}",
            "nombre_sintetico": f"Cliente sintetico {index:04d}",
            "fecha_alta": random_date(
                rng, date(2017, 1, 1), date(2026, 2, 28)
            ).isoformat(),
            "segmento": rng.choices(
                ("ASALARIADO", "INDEPENDIENTE", "PENSIONADO", "PYME"),
                weights=(46, 27, 17, 10), k=1,
            )[0],
            "grupo_edad": rng.choices(
                ("18-29", "30-44", "45-59", "60+"),
                weights=(20, 36, 28, 16), k=1,
            )[0],
            "provincia": branch["provincia"],
            "sucursal_id": branch["sucursal_id"],
        })

    accounts = tables["cuentas.csv"]
    account_clients = clients + [rng.choice(clients) for _ in range(600)]
    for index, client in enumerate(account_clients, 1):
        accounts.append({
            "cuenta_id": f"CTA{index:06d}",
            "cliente_id": client["cliente_id"],
            "producto_id": rng.choices(
                ("PRD01", "PRD02", "PRD03"), weights=(65, 28, 7), k=1
            )[0],
            "fecha_apertura": random_date(
                rng, date.fromisoformat(client["fecha_alta"]), PREVIOUS_DAY
            ).isoformat(),
            "moneda": "CRC",
            "saldo_inicial": "",
        })

    account_order = list(range(len(accounts)))
    account_order.extend(rng.choices(
        range(len(accounts)), weights=[rng.randint(1, 9) for _ in accounts],
        k=72_000 - len(accounts),
    ))
    rng.shuffle(account_order)
    transactions = []
    for month, count in zip(range(4, 10), monthly_counts(72_000)):
        last_day = calendar.monthrange(2026, month)[1]
        for _ in range(count):
            tx_type = rng.choices(TRANSACTION_TYPES, weights=TYPE_WEIGHTS, k=1)[0]
            if tx_type == "SALARIO" and rng.randrange(100) < 85:
                day = rng.choice((15, last_day))
            else:
                day = rng.randint(1, last_day)
            timestamp = datetime(
                2026, month, day, rng.randint(6, 22),
                rng.randrange(60), rng.randrange(60),
            )
            lower, upper = AMOUNT_RANGES_CRC[tx_type]
            # Dos sorteos enteros concentran importes sin aritmetica binaria.
            amount = (rng.randint(lower * 100, upper * 100)
                      + rng.randint(lower * 100, upper * 100)) // 2
            transactions.append({
                "transaccion_id": f"TX{len(transactions) + 1:08d}",
                "cuenta_id": accounts[account_order[len(transactions)]]["cuenta_id"],
                "fecha_hora": timestamp.isoformat(timespec="seconds"),
                "tipo_transaccion": tx_type,
                "direccion": "CREDITO" if tx_type in CREDIT_TYPES else "DEBITO",
                "canal": rng.choices(
                    CHANNELS, weights=(58, 20, 12, 10), k=1
                )[0],
                "monto": money(amount),
                "moneda": "CRC",
                "estado": "APLICADA",
            })

    by_account = defaultdict(list)
    credit_cents = debit_cents = 0
    for transaction in transactions:
        by_account[transaction["cuenta_id"]].append(transaction)
        cents = parse_generated_money(transaction["monto"])
        if transaction["direccion"] == "CREDITO":
            credit_cents += cents
        else:
            debit_cents += cents
    opening_cents = 0
    for account in accounts:
        running = minimum = 0
        for transaction in sorted(
            by_account[account["cuenta_id"]],
            key=lambda row: (row["fecha_hora"], row["transaccion_id"]),
        ):
            cents = parse_generated_money(transaction["monto"])
            running += cents if transaction["direccion"] == "CREDITO" else -cents
            minimum = min(minimum, running)
        # El saldo inicial cubre todo prefijo de debitos, sin reembolsos artificiales.
        opening = -minimum + rng.randint(50_000 * 100, 2_000_000 * 100)
        account["saldo_inicial"] = money(opening)
        opening_cents += opening

    contaminated = rng.sample(range(72_000), 1080)
    for index in contaminated[:720]:
        transactions[index]["canal"] = f"  {transactions[index]['canal'].lower()}  "
    for index in contaminated[720:]:
        transactions[index]["canal"] = ""
    contaminated_set = set(contaminated)
    pristine = [
        index for index in range(72_000) if index not in contaminated_set
    ]
    raw_transactions = transactions.copy()
    for index in rng.sample(pristine, 288):
        raw_transactions.append(transactions[index].copy())
    for offset, index in enumerate(rng.sample(pristine, 72), 1):
        invalid = transactions[index].copy()
        invalid["transaccion_id"] = f"TX{72_000 + offset:08d}"
        if offset <= 24:
            invalid["cuenta_id"] = f"CTA_INEXISTENTE_{offset:02d}"
        elif offset <= 48:
            invalid["fecha_hora"] = "2026-09-31T25:61:00"
        else:
            invalid["monto"] = "-" + invalid["monto"]
        raw_transactions.append(invalid)
    rng.shuffle(raw_transactions)
    tables["transacciones.csv"] = raw_transactions

    for index, client in enumerate(rng.sample(clients, 400), 1):
        earliest = max(date(2025, 11, 1), date.fromisoformat(client["fecha_alta"]))
        disbursed = random_date(rng, earliest, date(2026, 8, 31))
        age = (END - disbursed).days
        original = rng.randint(300_000 * 100, 18_000_000 * 100)
        capital = original * rng.randint(70, 100) // 100
        tables["creditos.csv"].append({
            "credito_id": f"PRE{index:06d}",
            "cliente_id": client["cliente_id"],
            "producto_id": "PRD05" if client["segmento"] == "PYME" else "PRD04",
            "fecha_desembolso": disbursed.isoformat(),
            "fecha_corte": END.isoformat(),
            "moneda": "CRC",
            "monto_original": money(original),
            "saldo_capital": money(capital),
            "tasa_anual_pct": money(rng.randint(1000, 2500)),
            "plazo_meses": str(rng.choice((12, 24, 36, 48, 60))),
            "dias_mora": str(
                0 if rng.randrange(100) < 72 else rng.randint(1, min(120, age))
            ),
        })

    for offset in range((END - START).days + 1):
        current = START + timedelta(days=offset)
        tables["calendario.csv"].append({
            "fecha": current.isoformat(),
            "anio": str(current.year),
            "trimestre": str((current.month - 1) // 3 + 1),
            "mes": str(current.month),
            "nombre_mes": MONTHS[current.month - 1],
            "dia_mes": str(current.day),
            "dia_semana": str(current.isoweekday()),
            "nombre_dia": DAYS[current.weekday()],
            "es_fin_semana": str(int(current.isoweekday() >= 6)),
        })

    monthly = Counter(row["fecha_hora"][:7] for row in transactions)
    channel_counts = Counter(
        row["canal"].strip().upper() or "NO_INFORMADO" for row in transactions
    )
    salaries = [row for row in transactions if row["tipo_transaccion"] == "SALARIO"]
    payday_count = sum(
        int(row["fecha_hora"][8:10]) in (
            15, calendar.monthrange(2026, int(row["fecha_hora"][5:7]))[1]
        )
        for row in salaries
    )
    final_cents = opening_cents + credit_cents - debit_cents
    accounting = {}
    for key, value in (
        ("credit", credit_cents), ("debit", debit_cents),
        ("opening", opening_cents), ("final", final_cents),
    ):
        accounting[f"{key}_cents"] = str(value)
        accounting[f"{key}_crc"] = money(value)
    manifest = {
        "is_synthetic": True,
        "seed": SEED,
        "generator_version": 1,
        "period": {"start": START.isoformat(), "end": END.isoformat()},
        "timezone": "America/Costa_Rica",
        "timestamp_convention": "Hora local UTC-6, sin sufijo de zona horaria",
        "currency": "CRC",
        "csv_format": {
            "encoding": "utf-8-sig", "delimiter": ",",
            "line_terminator": "\\n", "decimal_places": 2,
        },
        "counts": {name: len(rows) for name, rows in tables.items()},
        "anomalies": {
            "exact_duplicates": 288, "invalid_account": 24,
            "invalid_timestamp": 24, "negative_amount": 24,
            "channel_whitespace_lowercase": 720, "channel_blank": 360,
        },
        "expected_cleaning": {
            "raw": 72_360, "duplicates": 288, "quarantine": 72,
            "quarantine_by_reason": {
                "invalid_account": 24, "invalid_timestamp": 24, "negative_amount": 24,
            },
            "clean": 72_000, "normalize": 720, "blanks": 360,
        },
        "cleaning_rules": [
            "Deduplicar por transaccion_id; exigir payload identico antes de eliminar.",
            "Poner en cuarentena cuenta inexistente, fecha_hora invalida o monto negativo.",
            "Normalizar canal con strip y upper; vacio se convierte en NO_INFORMADO.",
            "Calcular finanzas solo sobre las 72000 transacciones limpias.",
        ],
        "expected_accounting": accounting,
        "expected_analytics": {
            "monthly_transaction_counts": dict(sorted(monthly.items())),
            "september_to_april_count_ratio": ratio(monthly["2026-09"], monthly["2026-04"]),
            "salary_count": len(salaries),
            "salary_payday_count": payday_count,
            "salary_payday_share": ratio(payday_count, len(salaries)),
            "normalized_channel_counts": dict(sorted(channel_counts.items())),
            "most_used_channel": "BANCA_MOVIL",
        },
        "limitations": [
            "Todos los registros e identificadores son ficticios; no corresponden a ninguna entidad real.",
            "Nombres de productos y sucursales son ficticios, no comerciales.",
            "Las transferencias pueden ser externas; no constituyen doble partida interna balanceada.",
            "Todas las cuentas estan activas durante el periodo; saldo inicial al 2026-04-01.",
            "Los saldos iniciales se dimensionan para evitar saldos negativos en todo prefijo temporal.",
            "Los creditos son una fotografia simple de cartera, no un cuadro de amortizacion.",
            "El saldo de creditos no se concilia con movimientos de las cuentas.",
            "No hay conversion de moneda ni cuentas o numeros de enrutamiento bancario reales.",
            "Patrones didacticos impuestos por diseno; no representan causalidad ni comportamiento real.",
            "La cuenta de plazo se simplifica como cuenta activa; no modela bloqueos ni vencimientos.",
            "La semilla reproduce esta version en Python 3.14; no se promete igualdad entre versiones mayores.",
        ],
    }
    return tables, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Reemplazar solamente los siete CSV y manifiesto.json; conservar documentos y scripts.",
    )
    args = parser.parse_args()
    csv_directory = ROOT / "csv"
    manifest_path = ROOT / "manifiesto.json"
    outputs = [csv_directory / name for name in HEADERS] + [manifest_path]
    existing = [path.name for path in outputs if path.exists()]
    if existing and not args.overwrite:
        parser.error(
            "Ya existen archivos generados: " + ", ".join(existing)
            + ". Use --overwrite para regenerarlos."
        )
    tables, manifest = build_dataset()
    csv_directory.mkdir(exist_ok=True)
    manifest["files"] = {}
    for name, rows in tables.items():
        path = csv_directory / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS[name], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        payload = path.read_bytes()
        manifest["files"][name] = {
            "row_count": len(rows),
            "headers": HEADERS[name],
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "status": "success", "seed": SEED, "directory": str(ROOT),
        "counts": manifest["counts"],
        "csv_bytes": sum(info["size_bytes"] for info in manifest["files"].values()),
        "manifest": str(manifest_path),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
