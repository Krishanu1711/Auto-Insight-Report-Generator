"""
scripts/generate_samples.py — Generate deterministic sample files for data/samples/.

Run with:  python scripts/generate_samples.py
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = ["East", "west", "West", "South", "North"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
CATEGORIES = ["Technology", "Furniture", "Office Supplies"]

N_ORDERS = 1_000
N_ORDERS_JSON_XML = 100
N_FEEDBACK = 50

# ---------------------------------------------------------------------------
# orders_sample.csv (1 000 rows, injected dirt)
# ---------------------------------------------------------------------------

def _generate_orders(n: int = N_ORDERS):
    rows = []
    start = date(2021, 1, 1)
    for i in range(1, n + 1):
        order_date = start + timedelta(days=random.randint(0, 3 * 365))
        region = random.choice(REGIONS)
        segment = random.choice(SEGMENTS)
        category = random.choice(CATEGORIES)
        sales = round(random.uniform(10, 2000), 2)
        quantity = random.randint(1, 20)
        discount = round(random.uniform(0, 0.5), 2)
        profit = round(sales * (1 - discount) * random.uniform(-0.1, 0.4), 2)

        # Inject dirt
        order_id_val = f"ORD-{i:05d}"
        sales_val: str | float = sales

        roll = random.random()
        if roll < 0.03:
            sales_val = f"${sales:,.2f}"     # dollar + comma
        elif roll < 0.05:
            sales_val = ""                   # missing
        elif roll < 0.06:
            sales_val = "?"                  # NA token

        discount_val: str | float = discount
        if random.random() < 0.02:
            discount_val = f"{discount:.0%}"  # percentage string

        profit_val: str | float | None = profit
        if random.random() < 0.04:
            profit_val = None               # NaN

        rows.append({
            "order_id": order_id_val,
            "order_date": order_date.isoformat(),
            "region": region,
            "segment": segment,
            "category": category,
            "sales": sales_val,
            "quantity": quantity,
            "discount": discount_val,
            "profit": profit_val,
        })

    # Inject 5 exact duplicate rows
    for _ in range(5):
        rows.append(random.choice(rows[:100]))

    # Inject 2 extreme outliers
    rows[10]["sales"] = 999_999
    rows[20]["profit"] = -99_999

    return rows


def write_csv(rows):
    path = SAMPLES_DIR / "orders_sample.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def write_json(rows):
    subset = rows[:N_ORDERS_JSON_XML]
    path = SAMPLES_DIR / "orders_sample.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(subset, f, indent=2, default=str)
    print(f"Wrote {len(subset)} records to {path}")


def write_xml(rows):
    subset = rows[:N_ORDERS_JSON_XML]
    root = ET.Element("orders")
    for row in subset:
        order_el = ET.SubElement(root, "order")
        for k, v in row.items():
            child = ET.SubElement(order_el, k)
            child.text = "" if v is None else str(v)
    tree = ET.ElementTree(root)
    path = SAMPLES_DIR / "orders_sample.xml"
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="unicode", xml_declaration=False)
    print(f"Wrote {len(subset)} records to {path}")


def write_feedback():
    phrases = [
        "The product quality is excellent and I am very satisfied.",
        "Delivery was slow but the item arrived in perfect condition.",
        "Customer service was unhelpful and rude.",
        "Great value for money — would definitely recommend to friends.",
        "The packaging was damaged but the product itself was fine.",
        "I love this company; they always deliver on time.",
        "Not what I expected based on the description.",
        "Returns process was quick and easy, no complaints.",
        "The quality has declined compared to my last purchase.",
        "Absolutely fantastic experience from start to finish!",
    ]
    lines = []
    for _ in range(N_FEEDBACK):
        n = random.randint(1, 3)
        line = " ".join(random.choice(phrases) for _ in range(n))
        lines.append(line)
    path = SAMPLES_DIR / "feedback_sample.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {path}")


def write_delimited_txt(rows):
    subset = rows[:200]
    path = SAMPLES_DIR / "delimited_sample.txt"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
        writer.writeheader()
        writer.writerows(subset)
    print(f"Wrote {len(subset)} rows to {path}")


if __name__ == "__main__":
    orders = _generate_orders()
    write_csv(orders)
    write_json(orders)
    write_xml(orders)
    write_feedback()
    write_delimited_txt(orders)
    print("Done.")

