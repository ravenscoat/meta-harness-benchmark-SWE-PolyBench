from benchmarks.polybench.contract_coverage import inventory


def test_emoji_heading_keeps_actual_contract_not_figure_metadata():
    result=inventory('# Expected Behavior 🤔\nSee the image below.\n![example](https://example/image.gif)\nThe input should retain entered text.\n# Steps\n1. Blur it.')
    assert not result['fallback']
    assert len(result['requirements'])==1
    assert result['requirements'][0]['quote']=='The input should retain entered text.'
    assert result['requirements'][0]['scenarios']==['behavior']


def test_markup_and_code_arrows_do_not_invent_numeric_boundaries():
    value=inventory('Fix preference resets.\n<!-- comment -->\n```diff\n- id: <redacted>\n```\nQueue ARN -> URL.')
    assert value['requirements'][0]['scenarios']==['behavior']


def test_real_limit_remains_boundary():
    assert inventory('# Expected behavior\nReject length > 448.')['requirements'][0]['scenarios']==['below','at','above']
