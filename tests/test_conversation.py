from agent4_lead_qualifier.conversation import parse_agent_json


def test_parses_clean_json():
    raw = (
        '{"reply": "Какие маркетплейсы вы используете?", '
        '"qualification_complete": false, '
        '"lead": {"role": "селлер"}}'
    )
    result = parse_agent_json(raw)
    assert result.reply == "Какие маркетплейсы вы используете?"
    assert result.qualification_complete is False
    assert result.lead.role == "селлер"
    assert result.lead.marketplaces == ""


def test_parses_json_wrapped_in_markdown_fence():
    raw = '```json\n{"reply": "ok", "qualification_complete": true, "lead": {"contact": "@ivan"}}\n```'
    result = parse_agent_json(raw)
    assert result.reply == "ok"
    assert result.qualification_complete is True
    assert result.lead.contact == "@ivan"


def test_falls_back_to_plain_text_on_invalid_json():
    raw = "Извините, я не робот, просто напишите мне позже"
    result = parse_agent_json(raw)
    assert result.reply == raw
    assert result.qualification_complete is False
    assert result.lead.role == ""


def test_missing_lead_fields_default_to_empty_string():
    raw = '{"reply": "ok", "qualification_complete": false, "lead": {}}'
    result = parse_agent_json(raw)
    assert result.lead.turnover == ""
    assert result.lead.pain_points == ""
