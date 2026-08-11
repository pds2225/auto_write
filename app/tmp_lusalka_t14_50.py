import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Check T14-T50 for content
for i in range(14, 52):
    if i >= len(content):
        break
    item = content[i]
    if 'Table' not in item:
        print(f'T{i}: NOT A TABLE')
        continue
    table = item['Table']
    rows = table.get('rows', [])
    total_text = ''
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
                    text = text_obj.get('text', '')
                    total_text += text
    
    if total_text.strip():
        print(f'T{i}: {total_text.strip()[:120]}')
    else:
        print(f'T{i}: (empty)')
