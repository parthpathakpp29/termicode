from termicode.ignore import (
    load_gitignore_patterns,
    path_contains_ignored_segment,
    prune_walk_dirs,
    should_skip_by_gitignore,
    should_skip_dir,
    should_skip_file,
)


def test_should_skip_dir_matches_known_names_case_insensitively():
    assert should_skip_dir("node_modules", "/project") is True
    assert should_skip_dir("NODE_MODULES", "/project") is True
    assert should_skip_dir(".git", "/project") is True
    assert should_skip_dir("src", "/project") is False


def test_should_skip_dir_matches_dist_info_and_egg_info_suffixes():
    assert should_skip_dir("somepkg.dist-info", "/project") is True
    assert should_skip_dir("somepkg.egg-info", "/project") is True


def test_should_skip_dir_detects_a_venv_lib_layout(tmp_path):
    lib_dir = tmp_path / "lib"
    (lib_dir / "site-packages").mkdir(parents=True)

    assert should_skip_dir("lib", str(tmp_path)) is True


def test_should_skip_dir_ordinary_lib_directory_is_not_skipped(tmp_path):
    """A directory that is just named "lib" without a site-packages child
    is real project code, not a venv -- must not be pruned."""
    (tmp_path / "lib").mkdir()

    assert should_skip_dir("lib", str(tmp_path)) is False


def test_should_skip_file_matches_known_suffixes_and_names():
    assert should_skip_file("module.pyc") is True
    assert should_skip_file("image.PNG") is True
    assert should_skip_file(".DS_Store") is True
    assert should_skip_file("main.py") is False


def test_path_contains_ignored_segment_matches_anywhere_in_the_path():
    assert path_contains_ignored_segment("a/node_modules/b/c.js") is True
    assert path_contains_ignored_segment("a/b/site-packages/c.py") is True
    assert path_contains_ignored_segment("a/b/c.py") is False


def test_prune_walk_dirs_mutates_in_place():
    dirs = ["src", "node_modules", ".git", "tests"]

    prune_walk_dirs("/project", dirs)

    assert dirs == ["src", "tests"]


def test_load_gitignore_patterns_reads_non_comment_non_empty_lines(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "# a comment\n\n*.log\nbuild/\n  \nnode_modules\n", encoding="utf-8"
    )

    patterns = load_gitignore_patterns(str(tmp_path))

    assert patterns == ["*.log", "build", "node_modules"]


def test_load_gitignore_patterns_returns_empty_list_when_no_gitignore(tmp_path):
    assert load_gitignore_patterns(str(tmp_path)) == []


def test_should_skip_by_gitignore_matches_a_plain_filename_pattern():
    assert should_skip_by_gitignore("notes.log", is_dir=False, patterns=["*.log", "secret.txt"]) is False
    assert should_skip_by_gitignore("secret.txt", is_dir=False, patterns=["*.log", "secret.txt"]) is True


def test_should_skip_by_gitignore_matches_a_rooted_pattern():
    patterns = ["/build"]

    assert should_skip_by_gitignore("build", is_dir=True, patterns=patterns) is True
    assert should_skip_by_gitignore("src/build", is_dir=True, patterns=patterns) is False


def test_should_skip_by_gitignore_matches_a_nested_path_pattern():
    patterns = ["src/generated"]

    assert should_skip_by_gitignore("src/generated", is_dir=True, patterns=patterns) is True
    assert should_skip_by_gitignore("other/generated", is_dir=True, patterns=patterns) is False


def test_should_skip_by_gitignore_matches_a_directory_name_anywhere():
    patterns = ["cache"]

    assert should_skip_by_gitignore("a/b/cache", is_dir=True, patterns=patterns) is True


def test_should_skip_by_gitignore_returns_false_with_no_patterns():
    assert should_skip_by_gitignore("anything", is_dir=False, patterns=[]) is False
