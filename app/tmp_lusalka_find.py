import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Find the 사업계획서 section (T13) and show its paragraphs
for i, item in enumerate(content):
    if 'Table' not in item:
        continue
    table = item['Table']
    rows = table.get('rows', [])
    for ri, row in enumerate(rows):
        cells = row.get('cells', [])
        for ci, cell in enumerate(cells):
            cell_content = cell.get('content', [])
            for pi, para in enumerate(cell_content):
                if not isinstance(para, dict):
                    continue
                runs = para.get('content', [])
                for run in runs:
                    if 'Text' not in run:
                        continue
                    text_obj = run['Text']
                    text = text_obj.get('text', '').strip()
                    style = text_obj.get('style', {})
                    font = style.get('font_name', '?')
                    size = style.get('font_size', 0)
                    
                    # Show all 20pt text (the "blue" headlines)
                    if size and size >= 20 and text:
                        print(f'T{i}/R{ri}/C{ci}/P{pi} | {font} {size}pt | {text[:120]}')
                    
                    # Show sub-headings (starts with ㅇ or contains 보유 역량 etc)
                    if text and ('보유 역량' in text or '해결하고자' in text or '사업 아이템' in text or '시장분석' in text or '고객 및 시장 검증' in text or '대표자 및 팀' in text):
                        print(f'T{i}/R{ri}/C{ci}/P{pi} | {font} {size}pt | {text[:120]}')
