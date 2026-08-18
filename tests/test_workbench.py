from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from test_creator_service import _analyze_and_finalize

from xhs_agent.creator.review import calibrate_baseline
from xhs_agent.renderers import build_workbench
from xhs_agent.storage import read_json, write_json_atomic
from xhs_agent.workbench import rebuild_workbench


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag in ("link", "script") and (attributes.get("href") or attributes.get("src")):
            self.links.append(attributes.get("href") or attributes.get("src"))


def test_workbench_builds_index_creator_and_version_pages(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    output = tmp_path / "workbench"
    analyzed, finalized = _analyze_and_finalize(state)
    result = build_workbench(state, output)

    assert result.creator_count == 1
    assert result.baseline_count == 1
    assert result.page_count == 3
    assert result.index_path.is_file()
    index_html = result.index_path.read_text(encoding="utf-8")
    assert "home-sections" in index_html
    assert "home-card" in index_html
    creator_page = output / "creators" / analyzed.creator["creator_id"] / "index.html"
    baseline_page = creator_page.parent / "baselines" / f"{finalized.baseline['baseline_id']}.html"
    assert creator_page.is_file()
    assert baseline_page.is_file()
    baseline_html = baseline_page.read_text(encoding="utf-8")
    assert "请确认这版画像" in baseline_html
    assert "数据快照" in baseline_html
    assert "TOP10 笔记数据" in baseline_html
    assert "自然表达与商业表达" in baseline_html
    assert "近期基线、历史能力与转型趋势" in baseline_html
    assert "查看支持证据" in baseline_html
    assert "data-claim-filter" in baseline_html
    assert "跳到主要内容" in baseline_html
    assert "条结论" in baseline_html
    assert "CLAIMS" not in baseline_html
    assert (output / "assets" / "workbench.css").is_file()
    assert (state / "cache" / "workbench-manifest.json").is_file()
    assert not (output / "workbench-manifest.json").exists()


def test_all_internal_page_links_resolve(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    output = tmp_path / "workbench"
    _analyze_and_finalize(state)
    build_workbench(state, output)
    for page in output.rglob("*.html"):
        parser = LinkCollector()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            if link.startswith(("#", "http://", "https://")):
                continue
            target = (page.parent / link.split("#", 1)[0]).resolve()
            assert target.is_file(), f"broken local link in {page}: {link}"


def test_workbench_escapes_creator_content(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    output = tmp_path / "workbench"
    analyzed, _finalized = _analyze_and_finalize(state)
    creator_path = analyzed.creator_root / "creator.json"
    creator = read_json(creator_path)
    creator["display_name"] = "<script>alert('private')</script>"
    write_json_atomic(creator_path, creator)
    build_workbench(state, output)
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*.html"))
    assert "<script>alert('private')</script>" not in rendered
    assert "&lt;script&gt;alert" in rendered


def test_workbench_separates_human_goal_context_from_evidence_portrait(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    output = tmp_path / "workbench"
    _analyzed, finalized = _analyze_and_finalize(state)
    calibrated = calibrate_baseline(
        state,
        finalized.baseline["baseline_id"],
        desired_positioning="合成目标定位：清晰解释与可执行步骤",
        target_audience="虚构目标受众：需要结构化示例的测试用户",
    )
    build_workbench(state, output)
    page = next(output.rglob(f"{calibrated.baseline['baseline_id']}.html"))
    rendered = page.read_text(encoding="utf-8")
    assert "团队目标校准" in rendered
    assert "不等同于公开数据已经证明的现有受众" in rendered
    assert "合成目标定位：清晰解释与可执行步骤" in rendered
    assert "虚构目标受众：需要结构化示例的测试用户" in rendered


def test_rebuild_removes_only_stale_manifest_pages(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    output = tmp_path / "workbench"
    analyzed, finalized = _analyze_and_finalize(state)
    build_workbench(state, output)
    stale_page = (
        output / "creators" / analyzed.creator["creator_id"] / "baselines"
        / f"{finalized.baseline['baseline_id']}.html"
    )
    unrelated = output / "notes-for-user.txt"
    unrelated.write_text("keep", encoding="utf-8")
    finalized.baseline_path.unlink()
    build_workbench(state, output)
    assert not stale_page.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_empty_workbench_has_non_technical_next_step(tmp_path: Path) -> None:
    output = tmp_path / "workbench"
    result = build_workbench(tmp_path / ".xhs-agent", output)
    text = result.index_path.read_text(encoding="utf-8")
    assert result.creator_count == 0
    assert "还没有博主画像" in text
    assert "creator analyze" in text


def test_workbench_service_records_run(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    result = rebuild_workbench(state, tmp_path / "workbench")
    run_path = state / "runs" / f"{result.run['run_id']}.json"
    stored = read_json(run_path)
    assert stored["operation"] == "workbench.build"
    assert stored["status"] == "completed"
    assert stored["outputs"]["index_path"].endswith("workbench/index.html")
