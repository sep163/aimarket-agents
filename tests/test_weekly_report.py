from agent5_marketing_analytics.weekly_report import build_prompt, is_anomaly, pct_change


def test_pct_change_normal_case():
    assert pct_change(120, 100) == 20.0
    assert pct_change(80, 100) == -20.0


def test_pct_change_no_baseline_returns_none():
    assert pct_change(100, 0) is None


def test_is_anomaly_both_direction():
    assert is_anomaly(25.0) is True
    assert is_anomaly(-25.0) is True
    assert is_anomaly(10.0) is False


def test_is_anomaly_respects_direction():
    assert is_anomaly(25.0, direction="up") is True
    assert is_anomaly(-25.0, direction="up") is False
    assert is_anomaly(-25.0, direction="down") is True
    assert is_anomaly(None) is False


def test_build_prompt_flags_anomaly_channel():
    channel_rows = [
        {
            "channel": "yandex_direct",
            "spend": 12000,
            "prev_spend": 9000,
            "clicks": 400,
            "prev_clicks": 380,
            "conversions": 20,
            "prev_conversions": 30,
            "cpl": 600,
            "prev_cpl": 300,
        }
    ]
    problem_rows = [{"problem_tag": "низкая конверсия рекламы", "cnt": 5}]

    prompt = build_prompt(channel_rows, problem_rows)

    assert "yandex_direct" in prompt
    assert "АНОМАЛИЯ" in prompt
    assert "низкая конверсия рекламы" in prompt


def test_build_prompt_handles_empty_data():
    prompt = build_prompt([], [])
    assert "Данных по каналам за неделю нет." in prompt
    assert "Проблем клиентов за последние 30 дней не зафиксировано." in prompt
