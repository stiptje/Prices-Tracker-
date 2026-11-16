import pytest
from pricetracker.matcher import ModelSpec, judge


def spec(name="iPhone 15 Pro", **kw):
    return ModelSpec(name=name, brand=kw.pop("brand", "Apple"), **kw)


@pytest.mark.parametrize("title,ok", [
    ("Apple iPhone 15 Pro 256GB Zwart", True),
    ("iPhone15 Pro 256 GB", True),
    ("Apple iPhone 15 Pro (256 GB) – Titanblau", True),
    ("Apple iPhone 15 Pro Max 256GB", False),
    ("Apple iPhone 15 Plus", False),
    ("Apple iPhone 15", False),
    ("Hoesje voor iPhone 15 Pro", False),
    ("Coque iPhone 15 Pro MagSafe", False),
    ("Screenprotector iPhone 15 Pro", False),
    ("Apple iPhone 15 Pro Reconditionné 256 Go", False),   # refurbished not requested
    ("Apple iPhone 14 Pro 256GB", False),
    ("iPhone 15 Pro - 256GB - écran 6,1 pouces", True),    # spec text must not look like an accessory
])
def test_iphone_15_pro(title, ok):
    assert judge(spec(), title).ok is ok


def test_storage_filter():
    s = spec(storage_gb=256)
    assert judge(s, "iPhone 15 Pro 256GB").ok
    assert not judge(s, "iPhone 15 Pro 128GB").ok
    assert judge(spec(storage_gb=1024), "iPhone 15 Pro 1TB").ok


def test_refurbished_toggle():
    t = "Apple iPhone 15 Pro 256GB Refurbished"
    assert not judge(spec(), t).ok
    v = judge(spec(allow_refurbished=True), t)
    assert v.ok and v.condition == "refurbished"
    # a refurbished-only shop marks everything refurbished even if the title does not say so
    assert not judge(spec(), "Apple iPhone 15 Pro 256GB", retailer_condition="refurbished").ok


@pytest.mark.parametrize("name,title,ok", [
    ("Galaxy S24", "Samsung Galaxy S24 5G 128GB", True),
    ("Galaxy S24", "Samsung Galaxy S24 Ultra", False),
    ("Galaxy S24", "Samsung Galaxy S24+ 256GB", False),
    ("Galaxy S24", "Samsung Galaxy S24 FE", False),
    ("Pixel 9", "Google Pixel 9 Pro XL", False),
    ("Pixel 9", "Google Pixel 9a", False),
    ("Pixel 9", "Google Pixel 9 128GB", True),
    ("iPhone 16", "Apple iPhone 16e", False),
    ("Galaxy Z Flip6", "Samsung Galaxy Z Flip 6 5G", True),
    ("Xiaomi 14", "Xiaomi 14T Pro", False),
    ("Redmi Note 13", "Xiaomi Redmi Note 13 Pro+ 5G", False),
    ("Nothing Phone (2)", "Nothing Phone (2a)", False),
    ("OnePlus 12", "OnePlus 12R", False),
    ("Xperia 1 V", "Sony Xperia 1 VI", False),
])
def test_variants(name, title, ok):
    assert judge(ModelSpec(name=name), title).ok is ok


def test_model_number_and_alias():
    s = ModelSpec(name="Galaxy S24 Ultra", brand="Samsung", model_numbers=["SM-S928B"], aliases=["S24 Ultra"])
    assert judge(s, "SM-S928B/DS Titanium Black").ok
    assert judge(s, "Samsung S24 Ultra 256GB").ok


def test_allow_words_for_earbuds():
    s = ModelSpec(name="AirPods Pro (2nd generation)", aliases=["AirPods Pro 2"], allow_words=["case", "charging", "magsafe"])
    assert judge(s, "Apple AirPods Pro 2 met MagSafe Charging Case (USB-C)").ok
    assert not judge(ModelSpec(name="AirPods Pro 2"), "Hoesje voor AirPods Pro 2").ok
