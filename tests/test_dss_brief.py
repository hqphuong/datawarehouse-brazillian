import numpy as np
import pandas as pd
import pytest

from etl import dss_attrib as A
from etl import dss_brief as B
from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


@pytest.fixture(scope="module")
def brief(o):
    return B.decision_brief(
        o,
        top_routes=3,
        top_payment=3,
        top_sellers=3,
        top_low_sample=3,
        n_boot=20,
        seed=42,
    )


def test_brief_has_separate_action_groups(brief):
    expected = {
        "route_actions",
        "payment_actions",
        "promise_actions",
        "promise_summary",
        "seller_actions",
        "low_sample_actions",
        "low_sample_check",
        "notes",
        "parameters",
    }
    assert expected.issubset(brief)
    # Không có tổng xuyên loại: brief chỉ trả từng nhóm riêng.
    assert "total_avoided_orders" not in brief
    assert "avoided_orders_total" not in brief
    assert all("KHÔNG cộng" in note for note in brief["notes"][:1])


def test_brief_action_tables_contract(brief):
    assert len(brief["route_actions"]) <= 3
    assert len(brief["payment_actions"]) <= 3
    assert len(brief["promise_actions"]) <= 3
    assert len(brief["seller_actions"]) <= 3
    assert len(brief["low_sample_actions"]) <= 3
    for key in ("route_actions", "payment_actions"):
        frame = brief[key]
        assert (frame["avoided_orders"] >= 0).all()
        assert (frame["avoided_ci_low"] <= frame["avoided_ci_high"]).all()
        assert frame["status"].isin(
            {"ước lượng ổn định (CI hẹp)", "tác động âm", "chưa đủ bằng chứng"}
        ).all()


def test_brief_promise_uses_net_only(brief):
    ps = brief["promise_summary"]
    assert ps["late_orders_before"] == ps["late_orders_after"] + ps["net_avoided_orders"]
    assert ps["net_avoided_orders"] > 0
    promise = brief["promise_actions"]
    # Bảng promise chỉ có NET, không có GROSS/avoidable.
    assert "net_avoided_orders" in promise.columns
    assert "avoidable_orders" not in promise.columns
    assert (promise["new_late_orders"] >= 0).all()
    assert promise["net_avoided_orders"].notna().all()


def test_brief_payment_actions_are_approval_only(o):
    table = A.approval_action_table(o, min_orders=100, top=3, n_boot=20, seed=42)
    assert len(table) > 0
    assert (table["cut_prep"] == 0).all()
    assert (table["cut_transit"] == 0).all()
    assert (table["cut_approval"] >= 0).all()
    assert table.attrs["n_payment_types_eligible"] >= len(table)


def test_brief_low_sample_actions_are_flagged(brief):
    low = brief["low_sample_actions"]
    assert (low["status"] == "cần thêm dữ liệu").all()
    assert (low["needed_orders"] > 0).all()
    check = brief["low_sample_check"].set_index("route")
    for route in low["route"]:
        assert bool(check.loc[route, "low_sample"]) is True
    named = {"MA->SP", "PR->BA", "SP->TO"} & set(check.index)
    for route in named:
        assert bool(check.loc[route, "in_flagged"]) is True


def test_brief_text_avoids_causal_and_certain_claims(brief):
    text = "\n".join(brief["notes"])
    for key in (
        "route_actions",
        "payment_actions",
        "promise_actions",
        "seller_actions",
        "low_sample_actions",
    ):
        if len(brief[key]):
            text += "\n" + "\n".join(brief[key]["action"].astype(str))
    for banned in ("sẽ giảm", "chắc chắn", "gây ra"):
        assert banned not in text.lower()
    assert "đổi định nghĩa trễ, không rút ngắn thời gian giao" in text
    assert "GMV" in text


def test_brief_gmv_values_are_integers(brief):
    for key in (
        "route_actions",
        "payment_actions",
        "promise_actions",
        "seller_actions",
        "low_sample_actions",
    ):
        frame = brief[key]
        if len(frame):
            assert frame["gmv"].map(
                lambda value: isinstance(value, (int, np.integer))
            ).all()


def test_brief_rejects_bad_input(o):
    with pytest.raises(ValueError):
        B.decision_brief(pd.DataFrame())
    with pytest.raises(ValueError):
        B.decision_brief(o, top_routes=0)
    with pytest.raises(ValueError):
        B.decision_brief(o, top_low_sample=-1)
