import unhwp, json

hwp_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'

result = unhwp.parse(hwp_path)
data = json.loads(result.json)

sec = data['sections'][0]
content = sec['content']

# Check T14 structure
for i in range(14, 20):
    item = content[i]
    print(f'T{i}: keys={list(item.keys())}')
    for key in item:
        val = item[key]
        if isinstance(val, dict):
            print(f'  {key}: dict keys={list(val.keys())[:5]}')
            # Check for text content
            if 'content' in val:
                c = val['content']
                if isinstance(c, list) and c:
                    print(f'    content: list of {len(c)}, first keys={list(c[0].keys()) if isinstance(c[0], dict) else type(c[0])}')
            if 'text' in val:
                print(f'    text: {str(val["text"])[:100]}')
        elif isinstance(val, list):
            print(f'  {key}: list of {len(val)}')
        else:
            print(f'  {key}: {type(val).__name__} = {str(val)[:100]}')
