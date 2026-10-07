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
    # Inspect the actual result, never the original issue or a test name:
    # those commonly contain failure words even after a successful repair.
    for key in ("status", "summary", "limitations", "blockers", "failures"):
        value = summary.get(key, "")
        entries = value if isinstance(value, list) else [value]
        for entry in entries[:20]:
            if not isinstance(entry, str):
                continue
            for statement in re.split(r"[\n]|(?<=[.!?])\s+", entry[:5000]):
                lower = statement.lower()
                if re.search(r"\b(original|baseline|initial|earlier|previous)\b", lower):
                    continue
                if re.search(r"\b(no failures|zero failures|0 failures|now passes|"
                             r"all .{0,40}passed|resolved|subsequently|rerun .{0,30}passed)\b", lower):
                    continue
                if (key == "status" and lower.strip() in
                        ("failed", "blocked", "incomplete", "needs_repair")) or re.search(
                    r"\b(still fails?|remain(?:s)? failing|unresolved|not implemented|"
                    r"unable to (?:complete|verify|run)|could not (?:complete|verify|run)|"
                    r"tests? (?:are failing|failed|fails)|verification failed|"
                    r"regression (?:fails|failed)|missing required|not yet (?:fixed|verified))\b",
                    lower,
                ):
                    reasons.append(statement.strip()[:700])
                    if len(reasons) >= 4:
                        return reasons
    return reasons


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
            "verification contracts: cover requested behavior through public interfaces "
            "and assert observable results, not implementation details. Source inventories "
            "and declared scripts are not passing evidence. Report current unresolved "
            "problems separately from earlier failures subsequently resolved."
        ),
        context={"navigation_paths": paths[:12], "search_anchors": terms},
    )
