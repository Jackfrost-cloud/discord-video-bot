from bot.utils.urls import extract_first_url, is_well_formed_url


def test_extract_first_url_found():
    assert extract_first_url("regarde ça https://youtu.be/abc merci") == "https://youtu.be/abc"


def test_extract_first_url_none():
    assert extract_first_url("pas de lien ici") is None


def test_extract_first_url_empty_string():
    assert extract_first_url("") is None


def test_is_well_formed_url_valid():
    assert is_well_formed_url("https://www.youtube.com/watch?v=abc")


def test_is_well_formed_url_invalid():
    assert not is_well_formed_url("not-a-url")
    assert not is_well_formed_url("ftp://example.com/file")
