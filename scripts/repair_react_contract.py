"""Public red/green development replay for the consumed MUI 23229 attempt.

No model calls, reference patch access, or replacement of its benchmark score.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.git import assert_clean, clone, git
from hx.models import Candidate, Task

TEST_FILE = "packages/material-ui/src/Autocomplete/Autocomplete.test.js"
SOURCE_FILE = "packages/material-ui/src/useAutocomplete/useAutocomplete.js"
TESTS = """
  describe('Autocomplete input outline interaction', () => {
    const clickSequence = (target) => {
      fireEvent.mouseDown(target);
      fireEvent.mouseUp(target);
      fireEvent.click(target);
    };

    it('opens on outline mouse-down before mouse-up or click', () => {
      const { getByRole } = render(
        <Autocomplete options={['one']} renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      fireEvent.mouseDown(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      expect(getByRole('listbox')).to.have.text('one');
    });

    it('toggles an empty outline on repeated complete pointer interactions', () => {
      const onOpen = spy();
      const onClose = spy();
      const { getByRole, queryByRole } = render(
        <Autocomplete options={['one']} onOpen={onOpen} onClose={onClose}
          renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      clickSequence(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      expect(input).toHaveFocus();
      clickSequence(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'false');
      expect(queryByRole('listbox')).to.equal(null);
      expect(input).toHaveFocus();
      expect(onClose.callCount).to.equal(1);
      expect(onClose.firstCall.args[1]).to.equal('toggleInput');
      clickSequence(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      expect(onOpen.callCount).to.equal(2);
    });

    it('keeps a nonempty outline open on a repeated interaction', () => {
      const { getByRole } = render(
        <Autocomplete value="one" options={['one']}
          renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      clickSequence(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      clickSequence(input.parentElement);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
    });

    it('does not double-toggle when an input event bubbles through its outline', () => {
      const onOpen = spy();
      const onClose = spy();
      const { getByRole } = render(
        <Autocomplete options={['one']} onOpen={onOpen} onClose={onClose}
          renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      clickSequence(input);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      clickSequence(input);
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'false');
      expect(onOpen.callCount).to.equal(1);
      expect(onClose.callCount).to.equal(1);
    });

    it('keeps the popup button toggle independent from outline interactions', () => {
      const onOpen = spy();
      const onClose = spy();
      const { getByRole } = render(
        <Autocomplete options={['one']} onOpen={onOpen} onClose={onClose}
          renderInput={(params) => <TextField {...params} />} />,
      );
      clickSequence(getByRole('button', { name: 'Open' }));
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'true');
      clickSequence(getByRole('button', { name: 'Close' }));
      expect(getByRole('combobox')).to.have.attribute('aria-expanded', 'false');
      expect(onOpen.callCount).to.equal(1);
      expect(onClose.callCount).to.equal(1);
    });
  });
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit_candidate(workspace, original, message, commands):
    git(workspace, "add", "--all")
    git(workspace, "commit", "-qm", message)
    head = git(workspace, "rev-parse", "HEAD")
    patch = subprocess.run(["git", "-C", str(workspace), "diff", "--binary",
        original.base_commit, head], check=True, capture_output=True).stdout
    return original.model_copy(update={"workspace": str(workspace),
        "input_commit": original.candidate_commit, "candidate_commit": head,
        "changed_files": git(workspace, "diff", "--name-only", original.base_commit, head).splitlines(),
        "diff_sha256": hashlib.sha256(patch).hexdigest(), "verification_commands": commands})


def main():
    import docker

    root = Path(".hx/react-contract-repair-v1").resolve()
    if root.exists():
        raise RuntimeError("Development identity exists; preserve it and choose a new version.")
    old = Path(".hx/one-react-evaluation-v2")
    key = "mui__material-ui-23229"
    case = json.loads((old / "images.json").read_text())[key]
    trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
    score_path = trial / "score.json"
    score = json.loads(score_path.read_text())
    original = Candidate.model_validate_json((trial / "state/runs" / score["run_id"] /
        "artifacts/implement.json").read_text())
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    source_hashes = {str(p): sha(p) for p in Path("benchmarks/polybench").glob("*.py")}
    workspace = Path("/opt/hx-polybench-runtime/v1/infra-checks/react-contract-repair-v1")
    assert_clean(Path(original.workspace), original.candidate_commit)
    write(root / "plan.json", {"classification": "Consumed evaluation case, now development-only",
        "original_score_sha256": sha(score_path), "original_candidate": original.model_dump(),
        "model_calls": 0, "private_grader_access": False,
        "derivation": "Public issue requests outline clicks behave like input; existing public input tests require empty-value toggling on mouse-down and nonempty-value persistence.",
        "script_sha256": sha(Path(__file__)), "historical_scores": historical,
        "runtime_sources": source_hashes, "workspace": str(workspace)})
    clone(Path(original.workspace), workspace, original.candidate_commit)
    path = workspace / TEST_FILE
    text = path.read_text()
    marker = "  describe('combobox', () => {"
    assert text.count(marker) == 1
    text = text.replace(marker, TESTS + "\n" + marker)
    # Correct the worker-added synthetic click into the same real pointer sequence
    # before BOTH red and green runs; the new regression source stays identical.
    old_click = "    fireEvent.click(input.parentElement);"
    assert text.count(old_click) == 1
    text = text.replace(old_click, "    fireEvent.mouseDown(input.parentElement);\n"
        "    fireEvent.mouseUp(input.parentElement);\n" + old_click)
    path.write_text(text)
    (root / "public-regressions.js").write_text(TESTS)
    executable = original.verification_commands[0][0]
    focused = [[executable, "test:unit", "--grep", "Autocomplete input outline interaction"]]
    red = commit_candidate(workspace, original, "Public outline interaction regressions", focused)
    write(root / "red-candidate.json", red.model_dump())
    tests_sha = sha(path)
    task = Task(id=key, repo=case["repo_path"], report="Public input outline development diagnostic.",
        base_commit=original.base_commit, kind="bug", allowed_paths=["**"])
    client = docker.from_env(timeout=1800)
    verifier = VisibleVerifier(load_settings(old / "settings.toml"), client, case)
    results = {}

    def replay(name, candidate):
        events = []
        verification = verifier.run(candidate, task, root / name, lambda: None,
            lambda event, data: events.append({"event": event, **data}))
        write(root / name / "verification.json", verification.model_dump())
        write(root / name / "events.json", events)
        results[name] = verification.model_dump()
        write(root / "results.json", results)
        print(json.dumps({"event": "public.replay", "name": name,
                          "passed": verification.passed}), flush=True)
        return verification

    try:
        failed = replay("red", red)
        assert not failed.passed, "New public regression must fail the saved worker implementation"
        output = (root / "red/public_test_1/stdout.txt").read_text()
        assert "failing" in output, "Require assertion failures, not an operational failure"
        path = workspace / SOURCE_FILE
        text = path.read_text()
        opening = "    if (event.target !== inputRef.current && !event.target.closest('button')) {\n      handleOpen(event);\n    }\n"
        assert text.count(opening) == 1
        text = text.replace(opening, "")
        old_down = "  const handleMouseDown = (event) => {\n"
        assert text.count(old_down) == 1
        text = text.replace(old_down, old_down +
            "    // Match input behavior only for the input outline itself.\n"
            "    // Input and button events have their own handlers.\n"
            "    if (event.target === anchorEl) {\n"
            "      handleInputMouseDown(event);\n"
            "    }\n\n")
        path.write_text(text)
        assert sha(workspace / TEST_FILE) == tests_sha
        green = commit_candidate(workspace, original, "Reuse input mouse-down behavior for outline interactions", focused)
        write(root / "green-candidate.json", green.model_dump())
        patch, delivery = production_patch(green)
        (root / "production.patch").write_text(patch)
        write(root / "delivery.json", delivery)
        assert replay("green", green).passed
        broad = green.model_copy(update={"verification_commands": [[executable, "test:unit", "--grep", "Autocomplete"]]})
        assert replay("compatibility", broad).passed
        assert_clean(Path(original.workspace), original.candidate_commit)
        assert all(sha(Path(p)) == h for p, h in historical.items())
        assert all(sha(Path(p)) == h for p, h in source_hashes.items())
        write(root / "complete.json", {"model_calls": 0,
            "historical_scores_unchanged": len(historical), "private_grader_access": False,
            "original_score_replaced": False, "identical_red_green_tests_sha256": tests_sha,
            "production_patch_sha256": sha(root / "production.patch"),
            "limitation": "Public development proof only; not an official resolution or fresh benchmark result."})
    finally:
        client.close()


if __name__ == "__main__":
    main()
