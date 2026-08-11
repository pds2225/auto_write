# -*- coding: utf-8 -*-
"""Verify v7_min 1-1 styles vs 1-2 unchanged."""
import sys
import unhwp
import json

sys.stdout.reconfigure(encoding='utf-8')

path = (
    r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625'
    r'\25_2026 예술분야 예비창업 프로그램 참여자 모집'
    r'\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v7_min.hwp'
)

data = json.loads(unhwp.parse(path).json)
content = data['sections'][0]['content']

want = [
    '1-1. 창업 동기',
    'ㅇ 보유 역량',
    'ㅇ 해결하고자',
    '1-2. 사업 아이템',
]

for i, item in enumerate(content):
    if 'Paragraph' not in item:
        continue
    para = item['Paragraph']
    runs = para.get('content', [])
    text = ''
    styles = []
    for run in runs:
        if 'Text' not in run:
            continue
        t = run['Text']
        text += t.get('text', '')
        s = t.get('style', {})
        styles.append(
            f"{s.get('font_name')} {s.get('font_size')}pt {s.get('color')}"
        )
    text_s = text.strip()
    if any(w in text_s for w in want):
        role = (
            'HEADLINE-target' if text_s.startswith('1-1.') else
            'SUBTITLE-target' if text_s.startswith('ㅇ') and ('보유' in text_s or '해결' in text_s) else
            'CONTROL-1-2' if text_s.startswith('1-2.') else
            '?'
        )
        print(f'P{i} [{role}]')
        print(f'  text: {text_s[:80]}')
        print(f'  styles: {styles[:4]}')
