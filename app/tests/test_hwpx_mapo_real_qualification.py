"""Windows real-form qualification; source is private, read-only and never committed."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile
import pytest
from lxml import etree
from test_hwpx_web_e2e_gate import web,client,_route,_tail,_loc
from test_hwpx_engine_coverage_synthetic import references,LABELS,HP
from auto_write.services.hwpx_form_diff import compare_hwpx_forms
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import _cell_joined,assess_fields


def test_real_form_console_qualification(client,web,tmp_path):
    default=Path(__file__).resolve().parents[2]/'data'/'mapo_next_stage_2026_form.hwpx'
    source=Path(os.environ.get('AUTO_WRITE_MAPO_FORM',str(default)))
    if not source.is_file():pytest.skip('MAPO 실양식 없음')
    before=source.read_bytes()
    assert hashlib.md5(before).hexdigest()=='eb680cbcfd61398c694508a003f42b68'
    from core.docx.services.hwp_docx_convert import _hangul_image_pids
    user_pids=set(_hangul_image_pids())
    ref=references(tmp_path/'synthetic_reference.docx',images=1)
    response=client.post('/console/documents/write',data={'project_title':'합성 값 실양식 검증','organization_name':'','instruction':''},files=[('template_file',('form.hwpx',before,'application/octet-stream')),('reference_files',('synthetic_reference.docx',ref.read_bytes(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))],follow_redirects=False)
    assert response.status_code==303,response.text
    location=_loc(response);assert 'error=' not in location,location
    project_id=_tail(location);route=_route(client,project_id);routing=route['routing']
    output=Path(routing['final']);assert output.is_file()
    assert routing['routing_status']!='TEMPLATE_MISMATCH',routing
    assert '_DRAFT' not in output.name,routing
    with ZipFile(output) as archive:
        root=etree.fromstring(archive.read('Contents/section0.xml'))
        text=''.join(root.itertext())
        assert len(root.findall(f'.//{{{HP}}}pic'))>=1
    for phrase in ('경우 기재','시에만 기재','에 대해 작성','등 기재','역할 분담'):
        assert phrase not in text,phrase
    assert '테스트팀' in text and '4명(대표 포함)' in text
    assert text.count('테스트 시스템')>=4
    assert text.count('홍길동 (팀명: 테스트팀)')==2
    for value in ('특허(출원)','10-2026-0000000','2026.01.01 출원'):
        assert value in text
    for label in LABELS:
        assert f'{label} 합성 본문' in text,label
    idx=index_hwpx_structure(output)
    fields=assess_fields(idx)
    assert not any(f.decision=='AUTO' or f.auto_write_allowed for f in fields)
    compare=compare_hwpx_forms(source,output)
    assert compare.form_intact,compare.as_dict()
    assert not any(k in compare.structure_deltas for k in ('표','행','칸'))
    pdf=routing.get('pdf_pair',{})
    if os.name=='nt':
        assert output.with_suffix('.pdf').is_file() or pdf.get('attempts')==2,pdf
    assert source.read_bytes()==before
    assert user_pids <= set(_hangul_image_pids())
    pairs=[]
    old=index_hwpx_structure(source)
    for table in idx.tables:
        section=next(s for s in idx.sections if s.section_index==table.section_index)
        old_table=old.tables[table.table_index]
        old_section=next(s for s in old.sections if s.section_index==table.section_index)
        for a,b in zip(old_table.cells,table.cells):
            av,bv=_cell_joined(old_section,a),_cell_joined(section,b)
            if av!=bv:pairs.append({'table':table.table_index,'row':b.row,'col':b.col,'before':av,'after':bv})
    evidence={'routing_status':routing['routing_status'],'pdf_pair':pdf,'form_diff':compare.as_dict(),'choice_marks':compare.choice_marks,'guidance_replacements':compare.guidance_replacements,'value_paragraphs':compare.value_paragraphs,'fields':pairs,'output':str(output),'original_md5':hashlib.md5(source.read_bytes()).hexdigest(),'original_preserved':True,'user_pids_preserved':True,'instructions_remaining':0}
    directory=os.environ.get('AUTO_WRITE_ENGINE_EVIDENCE_DIR')
    if directory:
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        (target/'qualification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        from shutil import copy2
        copy2(output,target/'qualified.hwpx')
        if output.with_suffix('.pdf').is_file():copy2(output.with_suffix('.pdf'),target/'qualified.pdf')
