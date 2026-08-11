import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Show cell content structure
for i, item in enumerate(content[:5]):
    if 'Table' not in item:
        continue
    table = item['Table']
    rows = table.get('rows', [])
    for ri, row in enumerate(rows[:2]):
        cells = row.get('cells', [])
        for ci, cell in enumerate(cells[:2]):
            cell_content = cell.get('content', [])
            print(f'T{i}/R{ri}/C{ci}: content type={type(cell_content)}, len={len(cell_content)}')
            if cell_content:
                first = cell_content[0]
                print(f'  First: type={type(first)}, keys={list(first.keys()) if isinstance(first, dict) else first}')
                if isinstance(first, dict):
                    print(f'  Full first: {json.dumps(first, ensure_ascii=False)[:300]}')
