import pandas as pd
from lib import demo_data
from lib.reorder import Settings


def test_demo_payload_shape():
    data = demo_data.load_all_data_demo()
    assert set(data) == {"products", "vendors", "settings", "purchase_log",
                         "shop_products", "sales", "adjustments", "loaded_at"}
    assert isinstance(data["settings"], Settings)
    assert len(data["products"]) >= 150
    assert set(data["sales"]["source"].unique()) <= {"shopify", "square"}
    assert pd.api.types.is_datetime64_any_dtype(data["sales"]["date"])
    # Fictional brand: no Lumati SKU prefixes
    assert not data["products"]["sku"].str.startswith("LUM-").any()


def test_demo_is_deterministic():
    a = demo_data.load_all_data_demo()
    b = demo_data.load_all_data_demo()
    pd.testing.assert_frame_equal(a["sales"], b["sales"])
