from engram.cli import read_messages


def test_read_messages_only_at_prefix_sets_speaker(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text("# comment\nUpdate: we moved\n@Caroline: hi there\n\nplain line\n")
    assert read_messages(f) == [("user", "Update: we moved"), ("Caroline", "hi there"), ("user", "plain line")]
