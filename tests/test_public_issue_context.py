import pytest

from scripts.capture_public_issue_context import capture, issue_api, prose


@pytest.mark.parametrize('url', ['http://github.com/o/r/issues/1',
    'https://github.com/o/r/pull/1', 'https://github.com.evil/o/r/issues/1',
    'https://github.com/o/r/issues/1?token=secret', 'file:///private'])
def test_only_explicit_public_issue_urls(url):
    with pytest.raises(ValueError):
        issue_api(url)


def test_prose_omits_code_images_and_implementation_links():
    result = prose('API uses `invisible`.\n```jsx\nsecretSolution();\n```\n    indentedCode();\n'
                   '![image](https://x/p.png) https://github.com/o/r/pull/123')
    assert '`invisible`' in result
    assert 'secretSolution' not in result and 'indentedCode' not in result
    assert 'https://' not in result
    assert len(prose('x' * 5000)) == 1000
    assert 'secret' not in prose('Visible prose\n```js\nsecretUnclosedCode();')


def test_rejects_pull_request_and_bounds_comments():
    with pytest.raises(ValueError, match='pull request'):
        capture('https://github.com/o/r/issues/1', lambda _: {'pull_request': {}, 'title': 'PR'})
    row = {'html_url': 'https://github.com/o/r/issues/1#comment', 'created_at': 'date',
           'user': {'login': 'author'}, 'body': 'Public prose'}
    result = capture('https://github.com/o/r/issues/1',
                     lambda url: [row] * 30 if '/comments?' in url else {'title': 'Issue'})
    assert result['truncated'] and len(result['comments']) == 20
