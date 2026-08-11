import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']
char_styles = data['styles']['char_styles']

# Debug: show structure of first few items
for i, item in enumerate(content[:3]):
    print(f'=== Item {i} ===')
    print(f'  Keys: {list(item.keys())}')
    if 'Table' in item:
        table = item['Table']
        print(f'  Table keys: {list(table.keys())}')
        rows = table.get('rows', [])
        print(f'  Rows: {len(rows)}')
        if rows:
            row = rows[0]
            print(f'  Row keys: {list(row.keys())}')
            cells = row.get('cells', row.get('cell', []))
            if isinstance(cells, dict):
                cells = [cells]
            print(f'  Cells type: {type(cells)}, len: {len(cells) if isinstance(cells, list) else "N/A"}')
            if cells and isinstance(cells, list) and len(cells) > 0:
                cell = cells[0]
                print(f'  Cell keys: {list(cell.keys())}')
                paras = cell.get('paragraphs', cell.get('p', []))
                if isinstance(paras, dict):
                    paras = [paras]
                print(f'  Paras type: {type(paras)}, len: {len(paras) if isinstance(paras, list) else "N/A"}')
                if paras and isinstance(paras, list) and len(paras) > 0:
                    p = paras[0]
                    print(f'  Para keys: {list(p.keys())}')
                    runs = p.get('runs', p.get('run', []))
                    if isinstance(runs, dict):
                        runs = [runs]
                    print(f'  Runs: {len(runs) if isinstance(runs, list) else type(runs)}')
                    if runs and isinstance(runs, list) and len(runs) > 0:
                        print(f'  Run 0: {runs[0]}')
