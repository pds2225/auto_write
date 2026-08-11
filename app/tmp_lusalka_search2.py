import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Search for specific keywords from the text I extracted earlier
keywords = ['1-1', '1-2', '3-1', '3-2', '4-1', '창업 동기', '아이템 개요', '고유 특징', '시장분석', '핵심 가설', '검증 실행', '보유 역량']
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
                para_text = ''
                for run in runs:
                    if 'Text' not in run:
                        continue
                    text_obj = run['Text']
                    text = text_obj.get('text', '')
                    para_text += text
                
                text = para_text.strip()
                if not text or len(text) < 3:
                    continue
                
                for kw in keywords:
                    if kw in text:
                        first_style = '?'
                        for run in runs:
                            if 'Text' in run:
                                s = run['Text'].get('style', {})
                                first_style = f"{s.get('font_name','?')} {s.get('font_size',0)}pt"
                                break
                        print(f'T{i}/R{ri}/C{ci}/P{pi} | {first_style} | {text[:150]}')
                        break
