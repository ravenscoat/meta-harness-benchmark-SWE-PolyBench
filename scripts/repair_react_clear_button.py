"""Reference-informed public red/green diagnosis of the consumed React case."""

import json
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.git import assert_clean, clone, git
from hx.models import Candidate, Task
from scripts.repair_react_contract import SOURCE_FILE, TEST_FILE, commit_candidate, sha

COMPONENT = "packages/material-ui/src/Autocomplete/Autocomplete.js"
TYPES = "packages/material-ui/src/Autocomplete/Autocomplete.d.ts"
TESTS = """
  describe('Autocomplete clear-button hit-target contract', () => {
    it('does not render an invisible clear-button hit target for an empty value', () => {
      const { queryByTitle } = render(
        <Autocomplete options={['one']} renderInput={(params) => <TextField {...params} />} />,
      );
      // Query the DOM, including hidden buttons: role queries omit invisible controls.
      expect(queryByTitle('Clear')).to.equal(null);
    });

    it('does not reserve clear-icon layout space for an empty value', () => {
      const { container } = render(
        <Autocomplete options={['one']} renderInput={(params) => <TextField {...params} />} />,
      );
      const root = container.querySelector(`.${classes.root}`);
      expect(root).not.to.have.class(classes.hasClearIcon);
      expect(root).to.have.class(classes.hasPopupIcon);
    });

    it('renders a usable clear control for a selected value and removes it after clearing', () => {
      const onChange = spy();
      const { getByTitle, queryByTitle, getByRole, container } = render(
        <Autocomplete defaultValue="one" options={['one']} onChange={onChange}
          renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      act(() => input.focus());
      expect(container.querySelector(`.${classes.root}`)).to.have.class(classes.hasClearIcon);
      const clear = getByTitle('Clear');
      expect(clear).toBeVisible();
      fireEvent.mouseDown(clear);
      fireEvent.mouseUp(clear);
      fireEvent.click(clear);
      expect(input.value).to.equal('');
      expect(onChange.firstCall.args[1]).to.equal(null);
      expect(onChange.firstCall.args[2]).to.equal('clear');
      expect(queryByTitle('Clear')).to.equal(null);
      expect(container.querySelector(`.${classes.root}`)).not.to.have.class(classes.hasClearIcon);
    });

    it('tracks free-solo typed text when deciding whether a clear control exists', () => {
      const { getByRole, getByTitle, queryByTitle } = render(
        <Autocomplete freeSolo options={[]}
          renderInput={(params) => <TextField {...params} />} />,
      );
      const input = getByRole('textbox');
      expect(queryByTitle('Clear')).to.equal(null);
      fireEvent.change(input, { target: { value: 'typed' } });
      fireEvent.click(getByTitle('Clear'));
      expect(input.value).to.equal('');
      expect(queryByTitle('Clear')).to.equal(null);
    });

    it('retains a clear control for selected tags even when the text input is empty', () => {
      const { getByRole, getByTitle, queryByTitle } = render(
        <Autocomplete multiple defaultValue={['one']} options={['one']}
          renderInput={(params) => <TextField {...params} />} />,
      );
      expect(getByRole('textbox').value).to.equal('');
      fireEvent.click(getByTitle('Clear'));
      expect(queryByTitle('Clear')).to.equal(null);
    });
  });
"""


def main():
    import docker

    root = Path(".hx/react-contract-reference-analysis-v2").resolve()
    assert (root / "exposure.json").is_file()
    if (root / "plan.json").exists():
        raise RuntimeError("Development attempt already exists; retain it.")
    old = Path(".hx/one-react-evaluation-v2")
    key = "mui__material-ui-23229"
    trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
    score = json.loads((trial / "score.json").read_text())
    original = Candidate.model_validate_json((trial / "state/runs" / score["run_id"] /
        "artifacts/implement.json").read_text())
    case = json.loads((old / "images.json").read_text())[key]
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    workspace = Path("/opt/hx-polybench-runtime/v1/infra-checks/react-clear-button-repair-v2")
    assert_clean(Path(original.workspace), original.candidate_commit)
    write(root / "plan.json", {"classification": "Reference-informed consumed-case development only",
        "reference_source": "https://github.com/mui/material-ui/pull/23229",
        "reference_inspected": "Public PR conversation identifies invisible clear button, dirty rendering condition and removal of clearIndicatorDirty style",
        "model_calls": 0, "private_test_patch_access": False,
        "original_score_sha256": sha(trial / "score.json"), "historical_scores": historical,
        "script_sha256": sha(Path(__file__)), "workspace": str(workspace),
        "previous_attempt_retained": ".hx/react-contract-repair-v1",
        "test_design": "DOM existence, layout modifier, selected/free-solo/multiple value lifecycles; role queries alone hide the invisible hit target"})
    (root / "executed-helper.py").write_bytes(Path(__file__).read_bytes())
    clone(Path(original.workspace), workspace, original.candidate_commit)
    tests = workspace / TEST_FILE
    text = tests.read_text()
    # The worker's single-click synthetic assertion encoded its proposed solution,
    # not the actual invisible clear-button defect. Preserve it in the old identity.
    start = text.index("  it('opens the popup when clicking the input root outside the input', () => {")
    end = text.index("  });", start) + len("  });")
    text = text[:start] + text[end:]
    marker = "  describe('combobox', () => {"
    assert text.count(marker) == 1
    text = text.replace(marker, TESTS + "\n" + marker)
    # Existing icon-class fixture was empty but assumed a clear icon always existed.
    # Give BOTH red and green a selected value so this still tests populated classes.
    before = """    it('should apply the icon classes', () => {
      const { container } = render(
        <Autocomplete options={[]} renderInput={(params) => <TextField {...params} />} />,"""
    after = """    it('should apply the icon classes', () => {
      const { container } = render(
        <Autocomplete defaultValue="one" options={['one']} renderInput={(params) => <TextField {...params} />} />,"""
    assert text.count(before) == 1
    tests.write_text(text.replace(before, after))
    tests_sha = sha(tests)
    (root / "public-regressions.js").write_text(TESTS)
    executable = original.verification_commands[0][0]
    focused = [[executable, "test:unit", "--grep", "Autocomplete clear-button hit-target contract"]]
    red = commit_candidate(workspace, original, "Public invisible clear-button regressions", focused)
    write(root / "red-candidate.json", red.model_dump())
    client = docker.from_env(timeout=1800)
    verifier = VisibleVerifier(load_settings(old / "settings.toml"), client, case)
    task = Task(id=key, repo=case["repo_path"], report="Consumed public clear-button development diagnostic.",
        base_commit=original.base_commit, kind="bug", allowed_paths=["**"])
    results = {}

    def replay(name, candidate):
        events = []
        result = verifier.run(candidate, task, root / name, lambda: None,
            lambda event, data: events.append({"event": event, **data}))
        write(root / name / "verification.json", result.model_dump())
        write(root / name / "events.json", events)
        results[name] = result.model_dump()
        write(root / "results.json", results)
        print(json.dumps({"event": "public.replay", "name": name, "passed": result.passed}), flush=True)
        return result

    try:
        assert not replay("red", red).passed
        assert "AssertionError" in (root / "red/public_test_1/stdout.txt").read_text()
        # Restore the hook from the public base: no interaction-handler rewrite is needed.
        (workspace / SOURCE_FILE).write_text(git(workspace, "show", original.base_commit + ":" + SOURCE_FILE) + "\n")
        component = workspace / COMPONENT
        text = component.read_text()
        assert text.count("const hasClearIcon = !disableClearable && !disabled;") == 1
        text = text.replace("const hasClearIcon = !disableClearable && !disabled;",
            "const hasClearIcon = !disableClearable && !disabled && dirty;")
        text = text.replace("$clearIndicatorDirty", "$clearIndicator")
        text = text.replace("  /* Styles applied to the clear indicator if the input is dirty. */\n  clearIndicatorDirty: {},\n", "")
        text = text.replace("className={clsx(classes.clearIndicator, {\n                      [classes.clearIndicatorDirty]: dirty,\n                    })}", "className={classes.clearIndicator}")
        assert "clearIndicatorDirty" not in text
        component.write_text(text)
        types = workspace / TYPES
        text = types.read_text().replace("    /** Styles applied to the clear indicator if the input is dirty. */\n    clearIndicatorDirty?: string;\n", "")
        assert "clearIndicatorDirty" not in text
        types.write_text(text)
        assert sha(tests) == tests_sha
        green = commit_candidate(workspace, original, "Render clear button only when there is something to clear", focused)
        write(root / "green-candidate.json", green.model_dump())
        patch, delivery = production_patch(green)
        (root / "production.patch").write_text(patch)
        write(root / "delivery.json", delivery)
        assert replay("green", green).passed
        broad = green.model_copy(update={"verification_commands": [[executable, "test:unit", "--grep", "Autocomplete"]]})
        assert replay("compatibility", broad).passed
        assert_clean(Path(original.workspace), original.candidate_commit)
        assert all(sha(Path(p)) == h for p, h in historical.items())
        write(root / "complete.json", {"model_calls": 0,
            "historical_scores_unchanged": len(historical), "original_score_replaced": False,
            "identical_red_green_tests_sha256": tests_sha,
            "production_patch_sha256": sha(root / "production.patch"),
            "reference_informed": True, "not_heldout": True,
            "limitation": "Public red/green proof; independent official development diagnostic still required"})
    finally:
        client.close()


if __name__ == "__main__":
    main()
