"""Capture bounded prose-only public GitHub issue discussion before offline coding.

No authentication, pull requests, implementation files or private benchmark input.
The caller explicitly selects an issue; notes must be frozen into a new attempt.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from benchmarks.polybench.prepare import write

MAX_RESPONSE = 256000


def issue_api(url):
    match = re.fullmatch(r'https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)', url)
    if not match:
        raise ValueError('Explicit public GitHub issue URL required')
    return 'https://api.github.com/repos/' + '/'.join(match.groups()[:2]) + '/issues/' + match[3]


def prose(body):
    lines, fence = [], None
    for line in body.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1][0]
                lines.append('[code omitted]')
            elif marker[1][0] == fence:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'(?m)^(?: {4}|\t).*(?:\n|$)', '', text)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '[image omitted]', text)
    text = re.sub(r'https://github\.com/\S+/(?:pull|commit|blob|compare)/\S+', '[implementation link omitted]', text)
    return text.strip()[:1000]


def fetch(url):
    request = Request(url, headers={'User-Agent': 'HX-public-context', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=20) as response:
        if not response.url.startswith('https://api.github.com/'):
            raise ValueError('Unexpected redirect')
        data = response.read(MAX_RESPONSE + 1)
    if len(data) > MAX_RESPONSE:
        raise ValueError('Public response exceeds bound')
    return json.loads(data)


def capture(url, loader=fetch):
    api = issue_api(url)
    issue = loader(api)
    if not isinstance(issue, dict) or 'pull_request' in issue:
        raise ValueError('Issue discussion only; pull request content forbidden')
    comments = loader(api + '/comments?per_page=100')
    if not isinstance(comments, list):
        raise ValueError('Invalid comment response')
    rows = [{'url': row['html_url'], 'created_at': row['created_at'],
             'author': row['user']['login'], 'prose': prose(row.get('body') or '')}
            for row in comments[:20]]
    return {'version': 'public-issue-context@1', 'source': url, 'title': issue['title'],
            'comments': rows, 'truncated': len(comments) > 20 or len(comments) == 100,
            'model_calls': 0, 'limitation': 'Public discussion may postdate benchmark base. '
            'API clarification is external development evidence, not fresh heldout evaluation. '
            'Prose may include implementation advice; this filter is not a semantic leak detector.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('issue_url')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Never overwrite captured public evidence')
    write(args.output, capture(args.issue_url))
