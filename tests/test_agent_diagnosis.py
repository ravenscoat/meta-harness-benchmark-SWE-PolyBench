import json

import pytest

from hx.agent_diagnosis import diagnose_development, diagnose_trial


def test_public_green_is_not_a_known_official_failure_cause():
    row={"usage_known":True,"accepted_candidate":True,"official_resolved":False,
         "public_verified":True,"case":"dev","private_test":"secret"}
    result=diagnose_trial(row,"baseline/case-0-repeat-1/score.json")
    assert result['category']=='official_non_solve'
    assert 'secret' not in json.dumps(result)
    assert any('not a known hidden cause' in x for x in result['findings'])


@pytest.mark.parametrize('updates,category',[
    ({'usage_known':False},'unknown_usage'),
    ({'workflow_error':'bad session'},'operational_failure'),
    ({'infrastructure_error':'setup'},'operational_failure'),
    ({'missing_observations':1},'operational_failure'),
    ({'patch_error':'reject'},'delivery_rejection'),
    ({'accepted_candidate':False},'no_accepted_candidate'),
    ({'official_resolved':True},'official_solve')])
def test_failure_classes_are_separate(updates,category):
    row={'usage_known':True,'accepted_candidate':True,'official_resolved':False}
    assert diagnose_trial(row|updates,'score')['category']==category


def test_diagnosis_reads_only_development_score_layout(tmp_path):
    public=tmp_path/'development'
    directory=public/'baseline/case-0-repeat-1'
    directory.mkdir(parents=True)
    (directory/'score.json').write_text(json.dumps({'usage_known':True,'accepted_candidate':True,
                                                  'official_resolved':True,'case':'dev'}))
    heldout=tmp_path/'heldout/baseline/case-0-repeat-1'
    heldout.mkdir(parents=True)
    (heldout/'score.json').write_text('DO NOT READ')
    (public/'arbitrary-private-score.json').write_text('DO NOT READ')
    result=diagnose_development(public)
    assert result['counts']=={'official_solve':1}
    assert len(result['trials'])==1


def test_submitted_filtered_verification_is_a_public_review_lead(tmp_path):
    public=tmp_path/'development'
    folder=public/'baseline/case-0-repeat-1'
    trace=folder/'public-traces/run/delegate-0/stdout.txt'
    trace.parent.mkdir(parents=True)
    (folder/'score.json').write_text(json.dumps({'usage_known':True,'accepted_candidate':True}))
    summary={'verification_commands':[['node','mocha','--grep','existing test','--invert']]}
    trace.write_text(json.dumps({'item':{'type':'agent_message','text':json.dumps(summary)}}))
    findings=diagnose_development(public)['trials'][0]['trace_findings']
    assert findings[0]['category']=='filtered_verification'
    assert 'not proof of a defect' in findings[0]['finding']
