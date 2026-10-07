"""Bounded source discovery and evidence-directed repair of a worker result."""

import re


def _terms(report):
    # Issue templates and environment tables are usually worse search anchors
    # than API names and the short description at the beginning of a report.
    report = re.sub(r"<!--[\s\S]*?-->", " ", report[:16000])
    report = re.sub(r"https?://\S+", " ", report)
    title = report.split("\n", 1)[0][:300]
    quoted = re.findall(r"`([^`\n]{2,100})`", report)
    identifiers = re.findall(
        r"\b(?:[A-Za-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]+_[A-Za-z0-9_]+)\b",
        report[:6000],
    )
    stop = set("the a an and or with when from for into this that true false "
               "input output expected actual behavior issue bug fix provide "
               "current version latest steps reproduce summary component "
               "undefined null none return error does not is are on in to of "
               "it be as at by value using should unexpectedly".split())
    terms = []
    # Keep title anchors first so numerous configuration flags do not bury
    # the component or function that owns the behavior.
    for piece in [title] + quoted[:20] + identifiers[:30]:
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_./-]*", piece):
            token = token.strip("./-")[:100]
            if len(token) < 3 or token.lower() in stop:
                continue
            if token.lower() not in [item.lower() for item in terms]:
                terms.append(token)
            if len(terms) >= 10:
                return terms
    return terms


def _repair_reasons(summary):
    if not isinstance(summary, dict):
        return []
    reasons = []
    # A passing filtered run does not settle an excluded compatibility failure.
    # Inspect argv, not test IDs or assertions containing words such as 'fails'.
    commands = summary.get("verification_commands", [])
    if isinstance(commands, list):
        for command in commands[:20]:
            if not isinstance(command, list):
                continue
            args = [arg[:500] for arg in command[:80] if isinstance(arg, str)]
            exclusions = [arg for arg in args if re.search(
                r"^--(?:invert|deselect|exclude|ignore)(?:$|[=-])", arg
            )]
            if any(arg in ("-k", "-m") and index + 1 < len(args)
                   and re.search(r"\bnot\b", args[index + 1])
                   for index, arg in enumerate(args)):
                exclusions.append("negative test selection")
            if exclusions:
                reasons.append("Verification excludes checks (" +
                               ", ".join(exclusions)[:300] +
                               "); inspect omitted expectations and report unfiltered results.")
                break
    # Inspect the actual result, never the original issue or a test name:
    # those commonly contain failure words even after a successful repair.
    for key in ("status", "summary", "limitations", "blockers", "failures"):
        value = summary.get(key, "")
        entries = value if isinstance(value, list) else [value]
        for entry in entries[:20]:
            if not isinstance(entry, str):
                continue
            # Evaluate clauses separately: 'rerun passed; one existing test fails'
            # must not erase the outstanding failure in the second clause.
            for statement in re.split(r"[\n;]|(?<=[.!?])\s+|\bbut\b|\bhowever\b", entry[:5000]):
                lower = statement.lower()
                failure = re.search(
                    r"\b(still fails?|remain(?:s)? failing|unresolved|not implemented|"
                    r"unable to (?:complete|verify|run)|could not (?:complete|verify|run)|"
                    r"tests? (?:are failing|failed|fails)|verification failed|"
                    r"regression (?:fails|failed)|missing required|not yet (?:fixed|verified)|"
                    r"failed (?:one|[1-9][0-9]*|a) (?:\w+\s+){0,4}(?:tests?|checks?|assertions?)|"
                    r"(?:tests?|checks?|assertions?)\b.{0,180}\bfails?|"
                    r"[1-9][0-9]* (?:failures|failing tests))\b", lower
                )
                if not failure:
                    if key == "status" and lower.strip() in (
                            "failed", "blocked", "incomplete", "needs_repair"):
                        reasons.append(statement.strip()[:700])
                    continue
                historical = re.search(r"\b(original (?:source|code)|baseline|initial|earlier|previous|before the fix)\b", lower)
                current = re.search(r"\b(still|unchanged|existing|compatibility|unresolved|unfiltered)\b", lower)
                resolved = re.search(r"\b(now passes|afterward.{0,60}passed|subsequently (?:corrected|resolved)|"
                                     r"(?:was|were) (?:corrected|resolved)|rerun.{0,30}passed)\b", lower)
                if (historical or resolved) and not current:
                    continue
                if statement.strip()[:700] not in reasons:
                    reasons.append(statement.strip()[:700])
                if len(reasons) >= 4:
                    return reasons
    return reasons[:4]


def _action(kind, memory, query="", guidance="", context=None):
    return {"action": kind, "query": query[:2000], "guidance": guidance[:4000],
            "memory": memory, "context": context or {},
            "omit_optional_context": []}


def next_action(state):
    calls = state.get("worker_calls", 0)
    inspections = state.get("inspections", 0)
    memory = state.get("memory", {})
    memory = dict(memory) if isinstance(memory, dict) else {}
    terms = _terms(str(state.get("report", "")))

    if calls >= 2:
        return _action("finish", memory)
    if calls:
        reasons = _repair_reasons(state.get("last_summary"))
        if not reasons:
            return _action("finish", memory)
        return _action(
            "delegate", {"phase": "repair", "repair_reasons": reasons},
            guidance=(
                "Continue from the existing diff and previous result. Address the concrete "
                "unresolved items in context; do not restart or expand the task. Distinguish "
                "a source defect, an incorrect verification command, and an unavailable "
                "environment. Inspect the last output before rerunning a stalled command. "
                "For filtered verification or compatibility failures, read the omitted "
                "expectations and compare them with the public requirement, callers and "
                "neighboring modes. Reconcile the implementation with legitimate existing "
                "behavior; do not label an expectation obsolete solely because it conflicts "
                "with the chosen design. Use unfiltered affected checks when permitted, "
                "and retain every remaining failure in the result. If a requirement truly "
                "changes an expectation, explain that from public evidence within the "
                "supplied test-edit rules; exclusion is not repair or passing evidence. "
                "Preserve valid work and unrelated behavior. If the blocker cannot be "
                "resolved within the supplied rules, report it accurately rather than "
                "inventing edits or passing evidence. Return the original result schema."
            ),
            context={"unresolved_items": reasons},
        )

    if inspections == 0 and terms:
        return _action("inspect", {"phase": "discovery", "anchors": terms},
                       query=" ".join(terms))

    observations = state.get("observations", [])
    matches = []
    for observation in observations[-2:]:
        if isinstance(observation, dict):
            matches.extend(observation.get("matches", [])[:6])
    # A second lookup is useful only when discovery produced no candidates.
    # Leave the remaining actions available for implementation, repair, finish.
    if inspections == 1 and not matches and len(terms) > 1:
        return _action("inspect", {"phase": "discovery", "anchors": terms[:2]},
                       query=" ".join(terms[:2]))

    paths = []
    for match in matches:
        if isinstance(match, dict) and isinstance(match.get("path"), str):
            path = match["path"][:300]
            if path not in paths:
                paths.append(path)
    return _action(
        "delegate", {"phase": "implementation", "anchors": terms},
        guidance=(
            "Use discovery matches as navigation hints; inspect actual source before editing. "
            "Find the behavior's owner and its callers/state updates, rather than assuming "
            "the highest-ranked example or wrapper owns the bug. Derive an invariant from "
            "the requested behavior and trace the full reported event sequence, including "
            "initial state, repeated use, reset, and empty or absent data where relevant. "
            "For a guard or cached index, check validity against current data/state and "
            "whether state is reset at the right transition; do not choose a predicate "
            "solely because it fixes one reproduction. Compare neighboring modes so a "
            "narrow fix preserves legitimate behavior. Follow the supplied path, test, and "
            "verification contracts. Read existing affected tests before choosing a design; "
            "compare alternative fixes against both the requested behavior and established "
            "public outputs. Trace any changed producer value through its consumers and "
            "dependencies, including repeated updates and disabled/default modes. Do not "
            "exclude a conflicting existing check to make compatibility appear to pass. "
            "Cover requested behavior through public interfaces "
            "and assert observable results, not implementation details. Source inventories "
            "and declared scripts are not passing evidence. Report current unresolved "
            "problems separately from earlier failures subsequently resolved."
        ),
        context={"navigation_paths": paths[:12], "search_anchors": terms},
    )
