#!/usr/bin/env python3
"""Builds data/catalog.json – the product catalog used to identify what you mean.

Only models I'm confident exist are listed. Missing a model is harmless: typing anything that is
not in the catalog yields a "search exactly what I typed" candidate that you confirm (and can edit)
before any search runs. Add models by appending E(...) rows and re-running this script.

E(brand, name, aliases=[], model_numbers=[], storage_gb=[], year=None, category="smartphone")
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS: list[dict] = []


def E(brand, name, aliases=(), nums=(), storage=(), year=None, cat="smartphone", allow=()):
    ITEMS.append({
        "id": (brand + "-" + name).lower().replace(" ", "-").replace("(", "").replace(")", "").replace("+", "plus"),
        "brand": brand, "name": name, "aliases": list(aliases), "model_numbers": list(nums),
        "storage_gb": list(storage), "year": year, "category": cat, "allow_words": list(allow),
    })


# ------------------------------------------------------------------ Apple iPhone
S64_256 = [64, 128, 256]
for name, st, yr in [
    ("iPhone 11", [64, 128, 256], 2019), ("iPhone 11 Pro", [64, 256, 512], 2019),
    ("iPhone 11 Pro Max", [64, 256, 512], 2019),
    ("iPhone 12 mini", [64, 128, 256], 2020), ("iPhone 12", [64, 128, 256], 2020),
    ("iPhone 12 Pro", [128, 256, 512], 2020), ("iPhone 12 Pro Max", [128, 256, 512], 2020),
    ("iPhone 13 mini", [128, 256, 512], 2021), ("iPhone 13", [128, 256, 512], 2021),
    ("iPhone 13 Pro", [128, 256, 512, 1024], 2021), ("iPhone 13 Pro Max", [128, 256, 512, 1024], 2021),
    ("iPhone 14", [128, 256, 512], 2022), ("iPhone 14 Plus", [128, 256, 512], 2022),
    ("iPhone 14 Pro", [128, 256, 512, 1024], 2022), ("iPhone 14 Pro Max", [128, 256, 512, 1024], 2022),
    ("iPhone 15", [128, 256, 512], 2023), ("iPhone 15 Plus", [128, 256, 512], 2023),
    ("iPhone 15 Pro", [128, 256, 512, 1024], 2023), ("iPhone 15 Pro Max", [256, 512, 1024], 2023),
    ("iPhone 16e", [128, 256, 512], 2025), ("iPhone 16", [128, 256, 512], 2024),
    ("iPhone 16 Plus", [128, 256, 512], 2024), ("iPhone 16 Pro", [128, 256, 512, 1024], 2024),
    ("iPhone 16 Pro Max", [256, 512, 1024], 2024),
    ("iPhone 17", [256, 512], 2025), ("iPhone Air", [256, 512, 1024], 2025),
    ("iPhone 17 Pro", [256, 512, 1024], 2025), ("iPhone 17 Pro Max", [256, 512, 1024, 2048], 2025),
]:
    E("Apple", name, aliases=[f"Apple {name}"], storage=st, year=yr)
E("Apple", "iPhone SE (2020)", ["iPhone SE 2020", "iPhone SE 2nd generation", "iPhone SE (2e generatie)"], storage=[64, 128, 256], year=2020)
E("Apple", "iPhone SE (2022)", ["iPhone SE 2022", "iPhone SE 3", "iPhone SE (3rd generation)", "iPhone SE (3e generatie)", "iPhone SE (3. Generation)"], storage=[64, 128, 256], year=2022)

# ------------------------------------------------------------------ Samsung Galaxy S
for name, num, yr, st in [
    ("S21", "SM-G991B", 2021, [128, 256]), ("S21+", "SM-G996B", 2021, [128, 256]),
    ("S21 Ultra", "SM-G998B", 2021, [128, 256, 512]), ("S21 FE", "SM-G990B", 2022, [128, 256]),
    ("S22", "SM-S901B", 2022, [128, 256]), ("S22+", "SM-S906B", 2022, [128, 256]),
    ("S22 Ultra", "SM-S908B", 2022, [128, 256, 512, 1024]),
    ("S23", "SM-S911B", 2023, [128, 256, 512]), ("S23+", "SM-S916B", 2023, [256, 512]),
    ("S23 Ultra", "SM-S918B", 2023, [256, 512, 1024]), ("S23 FE", "SM-S711B", 2023, [128, 256]),
    ("S24", "SM-S921B", 2024, [128, 256, 512]), ("S24+", "SM-S926B", 2024, [256, 512]),
    ("S24 Ultra", "SM-S928B", 2024, [256, 512, 1024]), ("S24 FE", "SM-S721B", 2024, [128, 256, 512]),
    ("S25", "SM-S931B", 2025, [128, 256, 512]), ("S25+", "SM-S936B", 2025, [256, 512]),
    ("S25 Ultra", "SM-S938B", 2025, [256, 512, 1024]), ("S25 Edge", "SM-S937B", 2025, [256, 512]),
    ("S25 FE", "SM-S731B", 2025, [128, 256, 512]),
]:
    full = f"Galaxy {name}"
    E("Samsung", full, aliases=[f"Samsung {full}", f"Samsung {full} 5G", name.replace("+", " Plus")], nums=[num], storage=st, year=yr)

# Foldables
for name, yr, st in [("Galaxy Z Fold5", 2023, [256, 512, 1024]), ("Galaxy Z Flip5", 2023, [256, 512]),
                     ("Galaxy Z Fold6", 2024, [256, 512, 1024]), ("Galaxy Z Flip6", 2024, [256, 512]),
                     ("Galaxy Z Fold7", 2025, [256, 512, 1024]), ("Galaxy Z Flip7", 2025, [256, 512]),
                     ("Galaxy Z Flip7 FE", 2025, [128, 256])]:
    E("Samsung", name, aliases=[f"Samsung {name}", f"Samsung {name} 5G", name.replace("Galaxy ", "")], storage=st, year=yr)
# Galaxy A
for name, yr in [("A15", 2023), ("A16", 2024), ("A25", 2024), ("A26", 2025), ("A34", 2023), ("A35", 2024),
                 ("A36", 2025), ("A54", 2023), ("A55", 2024), ("A56", 2025)]:
    E("Samsung", f"Galaxy {name}", aliases=[f"Samsung Galaxy {name}", f"Samsung Galaxy {name} 5G", f"Galaxy {name} 5G"], storage=[128, 256], year=yr)

# ------------------------------------------------------------------ Google Pixel
for name, yr, st in [
    ("Pixel 6a", 2022, [128]), ("Pixel 7", 2022, [128, 256]), ("Pixel 7 Pro", 2022, [128, 256, 512]),
    ("Pixel 7a", 2023, [128]), ("Pixel 8", 2023, [128, 256]), ("Pixel 8 Pro", 2023, [128, 256, 512, 1024]),
    ("Pixel 8a", 2024, [128, 256]), ("Pixel 9", 2024, [128, 256]), ("Pixel 9 Pro", 2024, [128, 256, 512, 1024]),
    ("Pixel 9 Pro XL", 2024, [128, 256, 512, 1024]), ("Pixel 9 Pro Fold", 2024, [256, 512]),
    ("Pixel 9a", 2025, [128, 256]), ("Pixel 10", 2025, [128, 256]), ("Pixel 10 Pro", 2025, [128, 256, 512, 1024]),
    ("Pixel 10 Pro XL", 2025, [256, 512, 1024]), ("Pixel 10 Pro Fold", 2025, [256, 512, 1024]),
]:
    E("Google", name, aliases=[f"Google {name}"], storage=st, year=yr)

# ------------------------------------------------------------------ Xiaomi / Redmi / POCO
for name, yr in [("Xiaomi 13T", 2023), ("Xiaomi 13T Pro", 2023), ("Xiaomi 14", 2024), ("Xiaomi 14T", 2024),
                 ("Xiaomi 14T Pro", 2024), ("Xiaomi 14 Ultra", 2024), ("Xiaomi 15", 2025),
                 ("Xiaomi 15 Ultra", 2025), ("Xiaomi 15T", 2025), ("Xiaomi 15T Pro", 2025),
                 ("Redmi Note 13", 2024), ("Redmi Note 13 Pro", 2024), ("Redmi Note 13 Pro+", 2024),
                 ("Redmi Note 14", 2025), ("Redmi Note 14 Pro", 2025), ("Redmi Note 14 Pro+", 2025),
                 ("POCO F6", 2024), ("POCO F6 Pro", 2024), ("POCO X6 Pro", 2024), ("POCO F7 Pro", 2025),
                 ("POCO X7 Pro", 2025)]:
    al = [name.replace("Xiaomi ", "Xiaomi ") + " 5G"]
    if name.startswith("Redmi") or name.startswith("POCO"):
        al.append("Xiaomi " + name)
    E("Xiaomi", name, aliases=al, storage=[128, 256, 512], year=yr)

# ------------------------------------------------------------------ OnePlus, Nothing, Motorola, Fairphone, Sony, Honor, OPPO, Asus
for name, yr in [("OnePlus 11", 2023), ("OnePlus 12", 2024), ("OnePlus 12R", 2024), ("OnePlus 13", 2025),
                 ("OnePlus 13R", 2025), ("OnePlus Nord 4", 2024), ("OnePlus Nord 5", 2025)]:
    E("OnePlus", name, aliases=[name + " 5G"], storage=[128, 256, 512], year=yr)
for name, yr in [("Nothing Phone (1)", 2022), ("Nothing Phone (2)", 2023), ("Nothing Phone (2a)", 2024),
                 ("Nothing Phone (2a) Plus", 2024), ("Nothing Phone (3a)", 2025), ("Nothing Phone (3a) Pro", 2025),
                 ("Nothing Phone (3)", 2025), ("CMF Phone 1", 2024), ("CMF Phone 2 Pro", 2025)]:
    E("Nothing", name, aliases=[name.replace("(", "").replace(")", "")], storage=[128, 256, 512], year=yr)
for name, yr in [("razr 40", 2023), ("razr 50", 2024), ("razr 50 ultra", 2024), ("razr 60", 2025),
                 ("razr 60 ultra", 2025), ("edge 50 neo", 2024), ("edge 50 pro", 2024), ("moto g85", 2024),
                 ("moto g55", 2024)]:
    E("Motorola", name, aliases=[f"Motorola {name}", f"Motorola {name} 5G"], storage=[128, 256, 512], year=yr)
for name, yr, st in [("Fairphone 4", 2021, [128, 256]), ("Fairphone 5", 2023, [256]), ("Fairphone (Gen. 6)", 2025, [256])]:
    E("Fairphone", name, aliases=["Fairphone 6"] if "Gen. 6" in name else [], storage=st, year=yr)
for name, yr in [("Xperia 1 V", 2023), ("Xperia 1 VI", 2024), ("Xperia 1 VII", 2025), ("Xperia 5 V", 2023),
                 ("Xperia 10 V", 2023), ("Xperia 10 VI", 2024)]:
    E("Sony", name, aliases=[f"Sony {name}"], storage=[128, 256, 512], year=yr)
for name, yr in [("Magic6 Pro", 2024), ("Magic7 Pro", 2025), ("200", 2024), ("200 Pro", 2024), ("400", 2025),
                 ("400 Pro", 2025)]:
    E("Honor", "Honor " + name, aliases=[name] if not name[0].isdigit() else [],
      storage=[256, 512], year=yr)
for name, yr in [("Find X8", 2024), ("Find X8 Pro", 2024)]:
    E("OPPO", "OPPO " + name, aliases=[name], storage=[256, 512], year=yr)
E("Asus", "Zenfone 11 Ultra", aliases=["Asus Zenfone 11 Ultra", "ASUS Zenfone 11 Ultra 5G"], storage=[256, 512], year=2024)

# ------------------------------------------------------------------ a few non-phone electronics
E("Apple", "AirPods Pro (2nd generation)", ["AirPods Pro 2", "Apple AirPods Pro 2", "AirPods Pro 2e generatie", "AirPods Pro (2. Generation)"],
  cat="earbuds", allow=["case", "charging", "magsafe", "usb", "c"], year=2022)
E("Apple", "AirPods 4", ["Apple AirPods 4", "AirPods (4th generation)"], cat="earbuds", allow=["case", "charging", "magsafe", "usb", "c"], year=2024)
E("Samsung", "Galaxy Buds3 Pro", ["Samsung Galaxy Buds3 Pro", "Galaxy Buds 3 Pro"], cat="earbuds", allow=["case", "charging"], year=2024)
E("Sony", "WH-1000XM5", ["Sony WH-1000XM5", "WH1000XM5"], cat="headphones", year=2022)
E("Sony", "WH-1000XM6", ["Sony WH-1000XM6", "WH1000XM6"], cat="headphones", year=2025)
E("Apple", "Apple Watch Series 10", ["Apple Watch S10"], cat="smartwatch", year=2024, allow=["band", "strap"])
E("Apple", "iPad (10th generation)", ["iPad 10", "Apple iPad 10th generation", "iPad 10e generatie", "iPad 10. Generation"], cat="tablet", storage=[64, 256], year=2022)
E("Sony", "PlayStation 5 Slim", ["PS5 Slim", "Sony PlayStation 5 Slim"], cat="console", year=2023)

# de-duplicate ids
seen, out = set(), []
for it in ITEMS:
    if it["id"] in seen:
        continue
    seen.add(it["id"])
    # remove aliases that equal the name
    it["aliases"] = [a for a in dict.fromkeys(it["aliases"]) if a.lower() != it["name"].lower()]
    out.append(it)

path = ROOT / "data" / "catalog.json"
path.write_text(json.dumps({"note": "Models listed are ones known to exist; absence is harmless – custom text can always be searched.",
                            "products": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"wrote {len(out)} catalog products -> {path}")
