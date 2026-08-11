# -*- coding: utf-8 -*-
import unhwp, json, sys
sys.stdout.reconfigure(encoding='utf-8')

hwp_path = (
    r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625'
    r'\25_2026 예술분야 예비창업 프로그램 참여자 모집'
    r'\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'
)

result = unhwp.parse(hwp_path)
data = json.loads(result.json)
sec = data['sections'][0]
content = sec['content']

headlines = {15, 20, 27, 36, 39, 48}
body20 = {41, 43, 45, 47}
subtitles = {16, 18, 21, 23, 25, 28, 30, 32, 34, 37, 40, 42, 44, 46, 49}

for i in range(14, 51):
    item = content[i]
    if 'Paragraph' not in item:
        print(f'P{i}: NOT PARA keys={list(item.keys())}')
        continue
    para = item['Paragraph']
    runs = para.get('content', [])
    para_text = ''
    styles = []
    for run in runs:
        if 'Text' not in run:
            continue
        t = run['Text']
        text = t.get('text', '')
        para_text += text
        s = t.get('style', {})
        styles.append(
            f"{s.get('font_name','?')} {s.get('font_size',0)}pt color={s.get('color','?')}"
        )
    text = para_text.strip().replace('\n', ' ')
    if not text:
        print(f'P{i}: (empty)')
        continue
    role = (
        'HEADLINE' if i in headlines else
        'BODY20' if i in body20 else
        'SUBTITLE' if i in subtitles else
        'other'
    )
    st = ' | '.join(styles[:3])
    print(f'P{i} [{role}] | {st} | {text[:100]}')
