from termicode.rules import generate_termicode_rules


def test_detects_nextjs_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "package.json").write_text('{"dependencies": {"next": "14.0.0"}}', encoding="utf-8")

    result = generate_termicode_rules()

    assert result.startswith("Success")
    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "nextjs" in content
    assert "App Router" in content


def test_detects_react_project_when_next_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "18.0.0"}}', encoding="utf-8")

    generate_termicode_rules()

    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "react" in content
    assert "functional components" in content


def test_detects_django_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("django==5.0\n", encoding="utf-8")

    generate_termicode_rules()

    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "python" in content
    assert "Django" in content


def test_detects_fastapi_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("fastapi==0.110\n", encoding="utf-8")

    generate_termicode_rules()

    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "FastAPI" in content


def test_generic_python_project_when_no_framework_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.0\n", encoding="utf-8")

    generate_termicode_rules()

    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "PEP 8" in content


def test_falls_back_to_generic_rules_with_no_markers_at_all(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generate_termicode_rules()

    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "generic" in content
    assert "general software project" in content


def test_refuses_to_overwrite_an_existing_agent_md(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENT.md").write_text("existing content\n", encoding="utf-8")

    result = generate_termicode_rules()

    assert "already exists" in result
    assert (tmp_path / "AGENT.md").read_text(encoding="utf-8") == "existing content\n"
