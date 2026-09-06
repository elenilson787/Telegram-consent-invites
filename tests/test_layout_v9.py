from local_app_v9 import layout_profile


def test_compact_profile_for_864p_screen():
    profile = layout_profile(864)
    assert profile['compact'] is True
    assert profile['queue_row_min'] >= 150
    assert profile['textbox_height'] >= 100
    assert profile['route_row_min'] < profile['queue_row_min']


def test_regular_profile_for_tall_screen():
    profile = layout_profile(1080)
    assert profile['compact'] is False
    assert profile['queue_row_min'] > layout_profile(864)['queue_row_min']
    assert profile['textbox_height'] > layout_profile(864)['textbox_height']
