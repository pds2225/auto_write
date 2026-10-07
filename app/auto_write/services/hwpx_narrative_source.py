"""Exact DOCX heading/body/image evidence for direct HWPX cell grants."""
from __future__ import annotations
import re
from pathlib import Path
from core.docx.services.hwpx_protected_regions import normalized_cell_label


def reference_sections(refs, labels=()):
    from docx import Document
    sections = {}
    allowed = {normalized_cell_label(label) for label in labels}
    duplicates = set()
    for ref in refs:
        path = Path(ref if isinstance(ref,(str,Path)) else ref.saved_path)
        if path.suffix.lower() != '.docx' or not path.is_file():
            continue
        document = Document(path)
        current = None
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            style = paragraph.style.name if paragraph.style else ''
            # Heading styles are a positive boundary. Short standalone lines are
            # accepted only when the following paragraph is ordinary body text.
            heading = style.startswith('Heading') or style in {'Title','Subtitle'} or normalized_cell_label(text) in allowed
            if heading:
                current = normalized_cell_label(text)
                if current in sections:
                    duplicates.add(current)
                sections.setdefault(current, {'label':text,'body':[],'images':[]})
                continue
            if current is None:
                continue
            if text:
                sections[current]['body'].append(text)
            for inline in paragraph._p.xpath('.//wp:inline'):
                blips = inline.xpath('.//a:blip')
                if len(blips) != 1:
                    continue
                rid = blips[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rid not in document.part.related_parts:
                    continue
                part = document.part.related_parts[rid]
                if part.content_type not in {'image/png','image/jpeg'}:
                    continue
                sections[current]['images'].append({'blob':part.blob,'suffix':'.png' if part.content_type=='image/png' else '.jpg','caption':text})
    return {k:v for k,v in sections.items() if k not in duplicates}


def narrative_from_references(refs) -> dict[str,str]:
    return {v['label']:'\n'.join(v['body']) for v in reference_sections(refs).values() if v['body']}


def direct_cell_plan(index, identity, refs, meta):
    from core.docx.services.hwpx_protected_regions import authorize_guidance_value_writes, find_record_row_targets
    from core.docx.services.hwpx_fill import _GUIDANCE_CONDITIONAL_RE, _conditional_guidance_value
    candidate_grants = authorize_guidance_value_writes(index)
    sections = reference_sections(refs, [g.field_label for g in candidate_grants])
    facts = {normalized_cell_label(k):str(v) for k,v in identity.items() if str(v).strip()}
    representative = facts.get(normalized_cell_label('대표자'))
    team = facts.get(normalized_cell_label('팀명'))
    if representative and team:
        facts[normalized_cell_label('신청자명(팀명)')] = f'{representative} (팀명: {team})'
    grants, values, notes, images = [], {}, [], {}
    for grant in candidate_grants:
        label = grant.field_label
        key = normalized_cell_label(label)
        conditional = bool(_GUIDANCE_CONDITIONAL_RE.fullmatch(re.sub(r'\s+',' ',grant.expected_raw_text).strip()))
        if conditional:
            value = _conditional_guidance_value(grant.expected_raw_text,label,identity)
            if value is None:
                notes.append(f'[conditional] {label} UNDECIDED')
                continue
            notes.append(f'[conditional] {label} RESOLVED')
        elif grant.kind in {'GUIDANCE_VALUE','EMPTY_NARRATIVE'}:
            section = sections.get(key)
            value = '\n'.join(section['body']) if section else facts.get(key)
            if not value:
                notes.append(f'[narrative] {label} NO_SOURCE')
                continue
            notes.append(f'[narrative] {label} '+('GUIDANCE_REPLACED' if grant.kind=='GUIDANCE_VALUE' else 'EMPTY_WRITTEN'))
            if section and section['images'] and meta.get('insert_reference_images',True):
                images[grant] = section['images']
        else:
            # Arbitrary identity/answers must not bypass pending P14 assessments.
            # The new blank-cell path only covers explicitly requested fan-out.
            if key not in {normalized_cell_label('아이디어명'), normalized_cell_label('신청자명(팀명)')}:
                continue
            value = facts.get(key)
            if not value:
                continue
        if re.search(r'생년|설립일|개시일|날짜|연월일',label) and value != '해당없음':
            notes.append(f'[protected] {label} UNCONFIRMED_DATE')
            continue
        grants.append(grant); values[grant]=value
    records = find_record_row_targets(index)
    grouped = {}
    for grant in records:
        grouped.setdefault(grant.record_label,[]).append(grant)
    for label, targets in grouped.items():
        provided = (meta.get('hwpx_records') or {}).get(label)
        if provided is None:
            # Record label equivalence is explicit, restricted to a suffix.
            short = re.sub(r'\s*(?:등\s*)?보유현황$','',label).strip()
            provided = (meta.get('hwpx_records') or {}).get(short)
        if provided is None:
            raw = facts.get(normalized_cell_label(label)) or facts.get(normalized_cell_label(re.sub(r'\s*(?:등\s*)?보유현황$','',label)))
            if raw:
                headers = [g.field_label for g in targets if g.record_index==0]
                parts = raw.split(' / ')
                if len(parts)==len(headers):
                    provided=[dict(zip(headers,parts))]
                else:
                    notes.append(f'[record-row] {label} FIELD_COUNT_MISMATCH')
        if not isinstance(provided,list):
            continue
        capacity=max(g.record_index for g in targets)+1
        if len(provided)>capacity:
            notes.append(f'[record-row] {label} OVERFLOW')
        for row in range(min(len(provided),capacity)):
            row_targets=[g for g in targets if g.record_index==row]
            item=provided[row]
            if not isinstance(item,dict) or set(map(normalized_cell_label,item)) != set(normalized_cell_label(g.field_label) for g in row_targets):
                notes.append(f'[record-row] {label} FIELD_COUNT_MISMATCH'); continue
            fields={normalized_cell_label(k):str(v) for k,v in item.items()}
            if not all(fields[normalized_cell_label(g.field_label)].strip() for g in row_targets):
                continue
            for grant in row_targets:
                grants.append(grant); values[grant]=fields[normalized_cell_label(grant.field_label)]
            notes.append(f'[record-row] {label} WRITTEN')
    return grants, values, notes, images
