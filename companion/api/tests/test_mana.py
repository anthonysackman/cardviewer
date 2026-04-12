from app.mana import parse_mana_cost, sort_color_identity


def test_parse_mana_cost_empty():
    assert parse_mana_cost(None) == []
    assert parse_mana_cost("") == []


def test_parse_mana_cost_simple():
    assert parse_mana_cost("{4}{U}") == ["{4}", "{U}"]


def test_parse_mana_cost_hybrid():
    assert parse_mana_cost("{W/U}") == ["{W/U}"]


def test_parse_mana_cost_unicode_symbols():
    assert parse_mana_cost("{½}{∞}") == ["{½}", "{∞}"]


def test_parse_mana_cost_skips_junk_between_braced_groups():
    assert parse_mana_cost("{2} x {W}") == ["{2}", "{W}"]


def test_sort_color_identity_wubrg():
    assert sort_color_identity(["R", "W"]) == ["W", "R"]


def test_sort_color_identity_includes_c():
    assert sort_color_identity(["G", "C"]) == ["G", "C"]


def test_sort_color_identity_empty():
    assert sort_color_identity(None) == []
    assert sort_color_identity([]) == []
