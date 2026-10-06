"""Select distinct diagnostic lines before spending space on their context."""
import re


def _clip(line: str, budget: int) -> str:
    if len(line) <= budget:
        return line
    if budget < 7:
        return line[:budget]
    # The start identifies the error; the end often identifies the failing value.
    head = (budget - 5) * 2 // 3
    return line[:head] + " ... " + line[-(budget - 5 - head):]


def _render(selected: dict) -> str:
    pieces = []
    previous = -1
    for index in sorted(selected):
        if pieces and index > previous + 1:
            pieces.append("[...]")
        pieces.append(selected[index])
        previous = index
    return "\n".join(pieces)


def focused_output(output: str, limit: int = 2000) -> str:
    if limit <= 0:
        return ""
    if len(output) <= limit:
        return output

    lines = [re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).rstrip()
             for line in output.splitlines()]
    exception = re.compile(
        r"\b(?:[A-Za-z_]\w*(?:Error|Exception)|Error|Exception)\b"
        r"(?=\s*:|\s*$)")
    cause = re.compile(
        r"\b(?:caused by|root cause)\s*:|"
        r"\b(?:cannot|can't|could not|unable to|failed to)\s+\S+|"
        r"\b(?:not found|no such file|timed? out|offline|unsupported)\b", re.I)
    warning = re.compile(r"\b(?:\w*warning\w*|deprecated)\b|warnings\.warn", re.I)
    error = re.compile(r"\b(?:error|fatal|panic|failure)\b|^\s*FAIL\b", re.I)
    summary = re.compile(r"^\s*(?:FAILED|ERROR)\s+\S+|\b[1-9]\d*\s+(?:failed|errors?)\b", re.I)
    context = re.compile(
        r'^\s*(?:File ".+", line \d+|at\s+\S+|[>^~]+(?:\s|$)|'
        r'assert\s+|(?:Expected|Actual|Received|Expected value|Received value)\s*:)|'
        r'^\s*\S+:\d+(?::\d+)?(?:\s|$)', re.I)

    candidates = []
    priorities = {}
    seen = set()
    for index, line in enumerate(lines):
        key = line.strip()
        if not key:
            continue
        # Explicit exceptions and pytest evidence outrank warning vocabulary.
        if exception.search(line) or re.match(r"^\s*E\s+\S", line):
            priority = 5
        elif warning.search(line):
            continue
        elif cause.search(line) or re.search(r":\s*(?:fatal\s+)?error\s*:", line, re.I):
            priority = 4
        elif summary.search(line):
            priority = 2
        elif error.search(line):
            priority = 3
        elif re.search(r"Traceback \(|During handling of|direct cause of", line):
            priority = 1
        else:
            continue
        priorities[index] = priority
        if key not in seen:
            seen.add(key)
            candidates.append(index)

    if not candidates:
        # Unknown formats still get a useful tail, without repeated warnings.
        seen = set()
        for index in range(len(lines) - 1, -1, -1):
            key = lines[index].strip()
            if key and key not in seen and not warning.search(lines[index]):
                seen.add(key)
                candidates.append(index)
        if not candidates:
            for index in range(len(lines) - 1, -1, -1):
                if lines[index].strip():
                    candidates.append(index)
                    break
    else:
        # Short causes get covered before a verbose line of equal importance.
        candidates.sort(key=lambda index: (-priorities[index], len(lines[index]), index))

    selected = {}
    used = 0
    line_budget = min(480, max(80, limit // max(1, min(len(candidates), 8))))
    for index in candidates:
        # Seven characters cover a newline and a possible gap marker.
        available = limit - used - (7 if selected else 0)
        if available <= 0:
            break
        text = _clip(lines[index], min(line_budget, available))
        if selected and len(text) < min(24, len(lines[index])):
            continue
        selected[index] = text
        used += len(text) + (7 if len(selected) > 1 else 0)

    # Context is optional and never displaces a selected error or cause.
    anchors = sorted(selected)
    selected_text = {lines[index].strip() for index in selected}
    for anchor in anchors:
        if priorities.get(anchor, 0) < 3:
            continue
        for index in range(max(0, anchor - 4), min(len(lines), anchor + 3)):
            line = lines[index]
            key = line.strip()
            if (index in selected or not key or key in selected_text
                    or warning.search(line) or not context.search(line)):
                continue
            available = limit - used - 7
            if available < min(24, len(line)):
                continue
            selected[index] = _clip(line, min(240, available))
            selected_text.add(key)
            used += len(selected[index]) + 7

    return _render(selected)
