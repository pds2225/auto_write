"""IP디딤돌 원본의 복사본을 한 COM 객체로 진단하고 수정 저장까지 검증한다."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import importlib
import json
import shutil
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from core.docx.services import hwp_docx_convert as conv
from core.docx.services.hancom_com_guard import snapshot_hancom_com

FOLDER = Path(__file__).parent
ORIGINAL = Path(r'C:\Users\ekth3\Downloads\2._2026년_IP디딤돌_프로그램_아이디어_권리화_신청서.hwp')
SOURCE = FOLDER / 'ipdidim_source.hwp'
CONTROL = FOLDER / 'com-command.json'
PROOF = FOLDER / 'pdf-real-proof.json'
shutil.copy2(ORIGINAL, SOURCE)
source_hash = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
snapshot = snapshot_hancom_com()
assert snapshot.hwpframe_is_2022, '한글 2022 COM 등록이 아니다'
before = conv._hangul_image_pids()
assert getattr(before, 'query_ok', True)
state = {'hancom_2022': True, 'dispatch_count': 0, 'source_sha256': source_hash,
         'existing_hwp': sorted(before), 'stages': [], 'dialogs': [], 'saves': []}
owned = set()
hwp = None

def record():
    PROOF.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def stage(name, operation):
    started = time.monotonic()
    print('STAGE', name, flush=True)
    result = conv._run_com_stage(name, operation, timeout_cleanup=lambda: conv._kill_owned_pids(owned))
    state['stages'].append({'name':name, 'seconds':round(time.monotonic()-started,3), 'result':str(result)})
    record()
    return result

user32 = ctypes.WinDLL('user32', use_last_error=True)
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

def window_text(hwnd):
    buf=ctypes.create_unicode_buffer(2048)
    user32.GetWindowTextW(hwnd,buf,len(buf))
    return buf.value

def windows():
    found=[]
    @CALLBACK
    def each(hwnd, _):
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value not in owned:
            return True
        children=[]
        @CALLBACK
        def child(chwnd, _):
            cls=ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(chwnd,cls,len(cls))
            children.append({'hwnd':int(chwnd),'class':cls.value,'text':window_text(chwnd),'id':user32.GetDlgCtrlID(chwnd)})
            return True
        user32.EnumChildWindows(hwnd,child,0)
        cls=ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd,cls,len(cls))
        if children and (cls.value=='#32770' or any(c['class'].lower()=='button' for c in children)):
            found.append({'hwnd':int(hwnd),'pid':pid.value,'class':cls.value,'title':window_text(hwnd),'children':children})
        return True
    user32.EnumWindows(each,0)
    return found

def save(name, operation, dismiss_baseline=False):
    stop=threading.Event()
    seen=set()
    def inspect():
        while not stop.wait(.5):
            for dialog in windows():
                text=' '.join(c['text'] for c in dialog['children'])
                key=(dialog['hwnd'],text)
                if key in seen:
                    continue
                seen.add(key)
                state['dialogs'].append({'save':name, **dialog})
                record()
                print('OWNED_DIALOG', json.dumps({'save':name,'pid':dialog['pid'],'text':text},ensure_ascii=False),flush=True)
                # 기존 호출의 대기 원인을 기록한 후 소유 경고만 확인한다. 사용자 창·보안승인창은 제외.
                if dismiss_baseline and ('변경' in text or '추적' in text):
                    buttons=[c for c in dialog['children'] if c['class'].lower()=='button'
                             and c['text'].startswith(('확인','계속','예'))]
                    if len(buttons)==1:
                        time.sleep(2)
                        user32.PostMessageW(buttons[0]['hwnd'],0x00F5,0,0)
                        state['baseline_dialog_acknowledged']=True
                        record()
    observer=threading.Thread(target=inspect,daemon=True)
    observer.start()
    started=time.monotonic()
    dst=FOLDER/name
    try:
        result=stage('SaveAs[PDF]',operation)
        item={'name':name,'saved':bool(result),'seconds':round(time.monotonic()-started,3)}
        if dst.exists():
            import fitz
            with fitz.open(dst) as pdf:
                item.update(pages=len(pdf),bytes=dst.stat().st_size,
                            has_expected_text=any('아이디어' in p.get_text() for p in pdf))
        state['saves'].append(item)
        record()
        print('SAVE_RESULT',json.dumps(item,ensure_ascii=False),flush=True)
    except Exception as exc:
        state['saves'].append({'name':name,'saved':False,'seconds':round(time.monotonic()-started,3),'error':str(exc)})
        record()
        print('SAVE_ERROR',str(exc),flush=True)
    finally:
        stop.set()
        observer.join(timeout=2)

try:
    hwp=stage('Dispatch',conv._dispatch_hwp)
    state['dispatch_count']=1
    pid=conv._hwp_object_pid(hwp)
    if pid is not None and pid not in before:
        owned.add(pid)
    elif pid is None:
        owned.update(conv._fallback_owned_hwp_pids(before))
    assert len(owned)==1 and not owned & before, 'COM 객체 소유 PID를 확인할 수 없다'
    state['owned_pid']=next(iter(owned))
    record()
    hwp.XHwpWindows.Item(0).Visible=False
    stage('RegisterModule',lambda:hwp.RegisterModule('FilePathCheckDLL','FilePathCheckerModule'))
    stage('SetMessageBoxMode',lambda:hwp.SetMessageBoxMode(conv._HANGUL_AUTO_CONFIRM_MODE))
    assert stage('Open',lambda:hwp.Open(str(SOURCE),'',''))
    for name in ('Version','IsTrackChange','PageCount'):
        try:
            state[name]=str(getattr(hwp,name))
        except Exception as exc:
            state[name]=type(exc).__name__
    record()
    save('baseline.pdf',lambda:hwp.SaveAs(str(FOLDER/'baseline.pdf'),'PDF',''),True)
    print('WAITING_FOR_FIXED_CODE',flush=True)
    deadline=time.monotonic()+900
    last_id=None
    while time.monotonic()<deadline:
        time.sleep(.5)
        if not CONTROL.exists():
            continue
        command=json.loads(CONTROL.read_text(encoding='utf-8-sig'))
        if command.get('id')==last_id:
            continue
        last_id=command.get('id')
        if command.get('action')=='finish':
            break
        if command.get('action')=='fixed':
            conv=importlib.reload(conv)
            save('fixed.pdf',lambda:conv._save_as_pdf(hwp,FOLDER/'fixed.pdf'))
        elif command.get('action')=='save-mode':
            mode=int(command['mode'])
            stage('SetMessageBoxMode',lambda:hwp.SetMessageBoxMode(mode))
            name='mode-'+str(mode)+'.pdf'
            save(name,lambda:hwp.SaveAs(str(FOLDER/name),'PDF',''))
finally:
    if hwp is not None and owned:
        try:
            stage('Clear',lambda:hwp.Clear(1))
            stage('Quit',hwp.Quit)
        except Exception as exc:
            state['cleanup_error']=str(exc)
        conv._kill_owned_pids(owned)
    after=conv._hangul_image_pids()
    state.update(original_hash_preserved=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==source_hash,
                 source_copy_hash_preserved=hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash,
                 existing_hwp_preserved=before<=after,remaining_owned=sorted(owned & after))
    record()
    print('FINAL',json.dumps({k:state[k] for k in ('dispatch_count','original_hash_preserved','source_copy_hash_preserved','existing_hwp_preserved','remaining_owned')},ensure_ascii=False),flush=True)
