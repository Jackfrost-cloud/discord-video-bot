from bot.utils.formatting import format_duration, format_size, sanitize_filename


def test_format_size_bytes():
    assert format_size(500) == "500.0 o"


def test_format_size_mb():
    assert "Mo" in format_size(5 * 1024 * 1024)


def test_format_size_unknown():
    assert format_size(None) == "inconnue"
    assert format_size(0) == "inconnue"


def test_format_duration_minutes():
    assert format_duration(154) == "02:34"


def test_format_duration_hours():
    assert format_duration(3661) == "01:01:01"


def test_format_duration_unknown():
    assert format_duration(None) == "inconnue"


def test_sanitize_filename_removes_path_chars():
    result = sanitize_filename("../../etc/passwd: évasion?")
    assert "/" not in result
    assert ".." not in result


def test_sanitize_filename_fallback_on_empty():
    assert sanitize_filename("") == "video"


def test_sanitize_filename_truncates_long_names():
    result = sanitize_filename("a" * 500)
    assert len(result) <= 150
