from packrat.passwords import validate_password


def test_empty_password_rejected():
    assert validate_password("") == "Please enter a password."


def test_short_password_rejected():
    assert "at least 8" in validate_password("short")


def test_good_password_accepted():
    assert validate_password("correct horse battery") == ""
