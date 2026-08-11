import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Show T13 full structure
item = content[13]
print(f'T13 keys: {list(item.keys())}')
table = item['Table']
print(f'Table keys: {list(table.keys())}')
rows = table.get('rows', [])
print(f'Rows: {len(rows)}')
for ri, row in enumerate(rows):
    cells = row.get('cells', [])
    print(f'  Row {ri}: {len(cells)} cells')
    for ci, cell in enumerate(cells):
        cell_content = cell.get('content', [])
        print(f'    Cell {ci}: {len(cell_content)} paragraphs')
        for pi, para in enumerate(cell_content):
            if not isinstance(para, dict):
                continue
            runs = para.get('content', [])
            para_text = ''
            for run in runs:
                if 'Text' not in run:
                    continue
                text_obj = run['Text']
                text = text_obj.get('text', '')
                para_text += text
            if para_text.strip():
                print(f'      P{pi}: {para_text.strip()[:100]}')
