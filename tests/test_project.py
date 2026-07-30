from termicode.project import generate_local_project_map


def test_lists_files_and_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("y = 2\n", encoding="utf-8")

    result = generate_local_project_map()

    assert "main.py" in result
    assert "src/" in result
    assert "app.py" in result


def test_ignored_directories_are_pruned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.js").write_text("noise", encoding="utf-8")
    (tmp_path / "real.py").write_text("code", encoding="utf-8")

    result = generate_local_project_map()

    assert "node_modules" not in result
    assert "package.js" not in result
    assert "real.py" in result


def test_gitignored_files_are_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / "visible.py").write_text("code", encoding="utf-8")

    result = generate_local_project_map()

    assert "secret.txt" not in result
    assert "visible.py" in result


def test_depth_beyond_max_depth_is_not_descended(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / "too_deep.py").write_text("code", encoding="utf-8")

    result = generate_local_project_map(max_depth=1)

    assert "too_deep.py" not in result


def test_truncates_when_over_max_chars(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for i in range(200):
        (tmp_path / f"file_{i}.py").write_text("code", encoding="utf-8")

    result = generate_local_project_map(max_chars=200)

    assert "MAP TRUNCATED" in result


def test_empty_directory_returns_an_empty_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert generate_local_project_map() == ""
