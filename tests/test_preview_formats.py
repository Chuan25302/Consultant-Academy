import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from preview_formats import visible_text  # noqa: E402


def test_css_words_are_not_counted_but_thai_characters_are():
    text, thai = visible_text(
        "<style>alpha beta gamma</style><p>หนึ่ง สอง</p>")
    assert "alpha" not in text and "gamma" not in text
    assert thai == len("หนึ่งสอง")


def test_uppercase_and_attributed_style_and_script_are_stripped():
    text, _ = visible_text(
        '<STYLE type="text/css">x y z</STYLE><script>q w</script><b>ok</b>')
    assert text.split() == ["ok"]
