import json

from mdaddict.cli import main


def test_cli_plain_markdown_and_json(tmp_path, capsys):
    source = tmp_path / "source.txt"
    source.write_text("Original content\n", encoding="utf-8")
    assert main([str(source)]) == 0
    assert capsys.readouterr().out == "Original content\n"
    assert main([str(source), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["markdown"] == "Original content\n"


def test_cli_unicode_is_preserved(tmp_path, capsys):
    source = tmp_path / "source.txt"
    source.write_text("λ, ﬁ, and x²\n", encoding="utf-8")
    assert main([str(source), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["markdown"] == "λ, ﬁ, and x²\n"


def test_cli_refuses_input_overwrite_and_has_useful_errors(tmp_path, capsys):
    source = tmp_path / "source.md"
    source.write_text("Keep\n", encoding="utf-8")
    assert main([str(source), "--output", str(source)]) == 1
    assert "must not overwrite" in capsys.readouterr().err
    assert source.read_text(encoding="utf-8") == "Keep\n"
    assert main([str(tmp_path / "absent.pdf")]) == 1
    assert "FileNotFoundError" in capsys.readouterr().err
