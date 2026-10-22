"""AW ↔ Solar one-shot isolated comparison. No main/production changes."""
from __future__ import annotations
import argparse, hashlib, html, json, os, sys, tempfile, time, webbrowser
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace

sys.dont_write_bytecode=True
CASE={
"type":"new",
"instruction":"정부지원사업 사업계획서의 문제인식(Problem)을 약 500자 개조식 작성. 고객 문제, 현행 업무 한계, 개발 필요성 구분. 내부 시험 20건의 평균 6시간→4시간은 미검증 내부 실험임을 명시. 허위 매출·시장규모·성과·특허 생성 금지.",
"context":"[가상기업 문서웨이브]\n제품: AI 사업계획서 작성 지원 프로그램\n개발 단계: 시제품 내부 검증\n임직원: 4명\n시범사용 기업: 3개사\n유료고객: 0개사\n2026년 매출: 0원\n특허·인증: 없음\n내부 시험 문서: 20건\n기존 작성시간 6시간, 시제품 활용 시 4시간\n외부 고객환경 성능: 미검증\n시장규모, 경쟁사 성능, 고객 만족도: 확인되지 않음",
"strict":False}
MODEL="solar-pro4"

def repo_path(raw):
    dirs=[Path(raw)] if raw else []
    dirs += [Path.cwd(),Path.cwd().parent,Path("D:/auto_write"),Path.home()/"auto_write",Path.home()/"dev"/"auto_write",Path.home()/"Documents"/"auto_write",Path.home()/"Desktop"/"auto_write"]
    for x in dirs:
        if (x/"app"/"auto_write"/"config.py").is_file() and (x/"app"/"core"/"docx"/"services"/"openai_client.py").is_file():
            return x.resolve()
    raise RuntimeError("AW_REPO_NOT_FOUND")

def load_aw(root):
    os.environ.setdefault("AUTO_WRITE_WORKSPACE_ROOT",str(Path(tempfile.gettempdir())/"aw_solar_test_workspace"))
    os.environ.setdefault("AUTO_WRITE_RESULTS_ROOT",str(Path(tempfile.gettempdir())/"aw_solar_test_results"))
    sys.path.insert(0,str(root/"app"))
    from auto_write.config import get_settings
    from auto_write.services.openai_client import OpenAIService
    return get_settings(),OpenAIService

def base_model(settings,klass):
    if settings.has_anthropic:
        return "anthropic",os.getenv("AUTO_WRITE_ANTHROPIC_WRITING_MODEL","").strip() or klass.DEFAULT_ANTHROPIC_WRITING_MODEL
    if settings.has_openai:
        return "openai",settings.openai_model
    raise RuntimeError("BASELINE_KEY_MISSING")

def clients(AW):
    class Clean(AW):
        def _record_generation_trace(self,**kw): pass
        def _complete_text_openai(self,system_prompt,user_prompt,model,temperature,tools=None):
            if self._client is None: raise RuntimeError("OPENAI_CLIENT_MISSING")
            r=self._client.responses.create(model=model or self.settings.openai_model,instructions=system_prompt,input=user_prompt,temperature=temperature,tools=tools or [],max_output_tokens=4096)
            usage=getattr(r,"usage",None)
            self.local_usage={"input":getattr(usage,"input_tokens",None),"output":getattr(usage,"output_tokens",None)}
            return (r.output_text or "").strip()
        def _complete_text_anthropic(self,system_prompt,user_prompt,model,temperature,tools=None,max_tokens=4096):
            import httpx
            body={"model":model or self.settings.anthropic_model,"max_tokens":min(4096,max_tokens),"temperature":temperature,"system":system_prompt,"messages":[{"role":"user","content":user_prompt}]}
            if tools: body["tools"]=tools
            with httpx.Client(timeout=100) as client:
                r=client.post("https://api.anthropic.com/v1/messages",json=body,headers={"x-api-key":self.settings.anthropic_api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                r.raise_for_status()
            d=r.json()
            self.local_usage={"input":d.get("usage",{}).get("input_tokens"),"output":d.get("usage",{}).get("output_tokens")}
            return "\n".join(str(x.get("text","")) for x in d.get("content",[]) if x.get("type")=="text").strip()
    class Solar(Clean):
        def __init__(self,settings):
            super().__init__(settings)
            from openai import OpenAI
            self._client=OpenAI(api_key=os.environ["UPSTAGE_API_KEY"],base_url="https://api.upstage.ai/v1",max_retries=0,timeout=100)
        def provider_available(self,provider):
            return provider=="openai" and bool(os.getenv("UPSTAGE_API_KEY"))
    return Clean,Solar

def run(which,settings,AW):
    baseline,model=base_model(settings,AW)
    Clean,Solar=clients(AW)
    if which=="solar":
        if not os.getenv("UPSTAGE_API_KEY"): raise RuntimeError("SOLAR_KEY_MISSING")
        obj=Solar(settings);provider="openai";model=MODEL
    else:
        obj=Clean(settings);provider=baseline
        if baseline=="openai":
            from openai import OpenAI
            obj._client=OpenAI(api_key=settings.openai_api_key,max_retries=0,timeout=100)
        else:
            obj.settings=replace(settings,anthropic_model=model)
    prompt=[{"question_id":"test_answer","label":CASE["instruction"],"description":CASE["instruction"],"target":{"kind":"section","field_id":"test_answer"}}]
    t=time.perf_counter()
    d=obj.draft_missing_answers(prompt,CASE["context"],provider_override=provider,model_override=model,strict_preserve=CASE["strict"])
    answer=d.get("test_answer","") if isinstance(d,dict) else ""
    if not isinstance(answer,str) or not answer.strip(): raise RuntimeError("EMPTY_JSON_OR_RESPONSE")
    return {"ok":True,"model":model,"text":answer.strip(),"seconds":round(time.perf_counter()-t,2),"characters":len(answer.strip()),"usage":getattr(obj,"local_usage",None)}

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(temp,path)

def report(state):
    def column(k,name):
        d=state["results"].get(k,{})
        ok=d.get("ok")
        metric=(str(d.get("seconds"))+"초 · "+str(d.get("characters"))+"자 · "+str(d.get("model"))) if ok else str(d.get("error","미실행"))
        text=d.get("text","") if ok else "실제 응답 미생성"
        return "<section><h2>"+html.escape(name)+"</h2><small>"+html.escape(("실생성 성공" if ok else "미완료")+" | "+metric)+"</small><pre>"+html.escape(text)+"</pre></section>"
    style="body{margin:0;font:15px/1.7 system-ui,'Malgun Gothic';background:#f4f6fa;color:#16243a}header{background:#152541;color:#fff;padding:24px 6%}main{max-width:1200px;margin:20px auto;padding:0 15px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}section{background:white;border:1px solid #dce5f0;border-radius:10px;padding:20px;min-width:0}pre{white-space:pre-wrap;word-break:break-word;font:14px/1.8 'Malgun Gothic',sans-serif}small{color:#6f7f94}@media(max-width:700px){.grid{grid-template-columns:1fr}}"
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AW Solar 결과</title><style>'+style+'</style><header><h1>AUTOWRITE vs Upstage Solar</h1>실제 문안 비교 · 동일 입력 · AW 기존 프롬프트</header><main><div class="grid">'+column("baseline","A. 기존 AUTOWRITE")+column("solar","B. Solar Pro 4")+'</div><section><h3>테스트 조건</h3><p>가상기업 / 신규작성 / 기존 초안 없음 / 문안생성만 검증 (HWP 전체 작성 미검증)</p><h4>작성 지시</h4><pre>'+html.escape(CASE["instruction"])+'</pre><h4>기업정보</h4><pre>'+html.escape(CASE["context"])+'</pre></section></main></html>'

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default="")
    p.add_argument("--output",default=str(Path(os.getenv("LOCALAPPDATA",tempfile.gettempdir()))/"AW-Solar-Compare"))
    p.add_argument("--no-browser",action="store_true")
    a=p.parse_args()
    out=Path(a.output).resolve()
    suffix=hashlib.sha256(json.dumps(CASE,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:14]
    data_file=out/("compare-"+suffix+".json")
    html_file=out/("compare-"+suffix+".html")
    state={"case":CASE,"created_utc":datetime.now(timezone.utc).isoformat(),"attempts":{},"results":{}}
    if data_file.exists():
        state=json.loads(data_file.read_text(encoding="utf-8"))
        if state.get("case")!=CASE:raise RuntimeError("CASE_MISMATCH")
    if not all(state["results"].get(k,{}).get("ok") for k in ("baseline","solar")):
        root=repo_path(a.repo)
        settings,AW=load_aw(root)
        base_model(settings,AW)
        if not os.getenv("UPSTAGE_API_KEY"):raise RuntimeError("SOLAR_KEY_MISSING")
        for name in ("baseline","solar"):
            if state["results"].get(name,{}).get("ok"):
                print("[REUSE]",name);continue
            if state["attempts"].get(name,0)>0:
                print("[STOP]",name,"이전 API 호출 가능성이 있어 재호출 차단");continue
            state["attempts"][name]=1
            atomic(data_file,state)
            print("[CALL]",name)
            try:
                state["results"][name]=run(name,settings,AW)
                print("[PASS]",name)
            except Exception as e:
                state["results"][name]={"ok":False,"error":type(e).__name__}
                print("[FAIL]",name,type(e).__name__)
            atomic(data_file,state)
    html_file.parent.mkdir(parents=True,exist_ok=True)
    html_file.write_text(report(state),encoding="utf-8")
    print("[REPORT]",html_file)
    if not a.no_browser:webbrowser.open(html_file.as_uri())
    ok=all(state["results"].get(k,{}).get("ok") for k in ("baseline","solar"))
    print("[DONE]" if ok else "[PARTIAL]")
    return 0 if ok else 2

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as e:
        msg=str(e)
        print("[BLOCKED]",msg if msg in {"AW_REPO_NOT_FOUND","BASELINE_KEY_MISSING","SOLAR_KEY_MISSING","CASE_MISMATCH"} else type(e).__name__)
        sys.exit(3)
