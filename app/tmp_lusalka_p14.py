import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Show T14-T50 paragraph text and styles
for i in range(14, 51):
    item = content[i]
    if 'Paragraph' in item:
        para = item['Paragraph']
        runs = para.get('content', [])
        para_text = ''
        for run in runs:
            if 'Text' not in run:
                continue
            text_obj = run['Text']
            text = text_obj.get('text', '')
            para_text += text
        
        text = para_text.strip()
        if text and len(text) > 2:
            # Get first run style
            first_style = '?'
            for run in runs:
                if 'Text' in run:
                    s = run['Text'].get('style', {})
                    first_style = f"{s.get('font_name','?')} {s.get('font_size',0)}pt"
                    break
            print(f'P{i} | {first_style} | {text[:150]}')
