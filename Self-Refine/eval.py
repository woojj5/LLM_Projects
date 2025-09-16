
# eval.py
from __future__ import annotations
import os, json, time
from typing import List, Dict, Any, Optional
import requests, re, tempfile, subprocess, textwrap

# ---- Utils ----
def _tok(s: str):
    return [t for t in s.lower().replace('\n', ' ').split() if t]

def rouge_like_f(pred: str, ref: str) -> float:
    p, r = set(_tok(pred)), set(_tok(ref))
    if not p or not r: return 0.0
    inter = len(p & r)
    prec = inter / len(p)
    rec  = inter / len(r)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)

PY_RE = re.compile(r"```python(.*?)```", re.S|re.I)

def extract_code(x: str) -> str:
    m = PY_RE.search(x); return m.group(1).strip() if m else x.strip()

def run_tests(code: str, tests: str, timeout=12) -> float:
    wrap = textwrap.dedent(f"""
    {code}
    def __run_tests__():
        {tests}
    if __name__ == '__main__':
        __run_tests__()
    """)
    with tempfile.NamedTemporaryFile('w', suffix='_t.py', delete=False) as f:
        f.write(wrap); path = f.name
    try:
        cp = subprocess.run(["python", path], capture_output=True, text=True, timeout=timeout)
        return 1.0 if cp.returncode == 0 else 0.0
    except subprocess.TimeoutExpired:
        return 0.0

# ---- LLM ----
class LLM:
    def __init__(self, model: str, base_url: str):
        self.model=model; self.base=base_url.rstrip('/')
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        full = f"{system}\n{prompt}" if system else prompt
        r = requests.post(f"{self.base}/api/generate", json={"model": self.model, "prompt": full, "stream": False}, timeout=600)
        r.raise_for_status(); return (r.json().get('response') or '').strip()

SYSTEM="당신은 신중하고 엄격한 전문가입니다."
GEN_S="[목표] 다음 텍스트를 4문장 이내로 사실 유지 요약\n{text}\n<요약>(내용)</요약>"
CRIT_S="[원문]{text}\n[요약]{draft}\n<피드백>- 문제: ...\n  개선: ...</피드백>"
REFN_S="[이전]{draft}\n[피드백]{feedback}\n<요약>(내용)</요약>"

GEN_C="파이썬 스니펫만 출력. 요구사항: {prompt}\n```python\n# code here\n```"
CRIT_C="[요구]{prompt}\n[코드]{draft}\n<피드백>- 문제: ...\n  개선: ...</피드백>"
REFN_C="[이전]{draft}\n[피드백]{feedback}\n```python\n# 개선 코드\n```"

# ---- Datasets (sample) ----
SUMM = [
  {"id":"s1","text":"PatchTST는 시계열을 패치로 나눠 학습하는 트랜스포머 기반 모델이다. 장점은 긴 시퀀스 처리와 일반화이며 단점은 스케일 민감도와 튜닝 비용이다.","ref":"PatchTST는 패치 기반 트랜스포머로 긴 시퀀스에 강점이 있으나 스케일링/튜닝이 필요하다."}
]
CODE = [
  {"id":"c1","prompt":"정수 n(0<=n<=1000) 피보나치 함수 fibonacci(n)","tests":"assert fibonacci(0)==0; assert fibonacci(1)==1; assert fibonacci(10)==55"}
]

# ---- Self-Refine core ----
def self_refine(llm: LLM, gen: str, crit: str, refn: str, ctx: Dict[str, Any], score_fn):
    draft = llm.complete(gen.format(**ctx), SYSTEM)
    fb = llm.complete(crit.format(draft=draft, **ctx), SYSTEM)
    rev = llm.complete(refn.format(draft=draft, feedback=fb, **ctx), SYSTEM)
    s0 = score_fn(draft); s1 = score_fn(rev)
    return {"draft": draft, "revised": rev, "draft_score": s0, "revised_score": s1}

# ---- Eval Runner ----
def main():
    base = os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434")
    model= os.getenv("OLLAMA_MODEL","llama3.1:8b")
    llm = LLM(model, base)

    report = {"model": model, "base_url": base, "summ": [], "code": []}

    # Summarization
    for ex in SUMM:
        ctx = {"text": ex["text"]}
        # base
        base_out = llm.complete(GEN_S.format(**ctx), SYSTEM)
        base_txt = base_out.split("<요약>")[-1].split("</요약>")[0] if "</요약>" in base_out else base_out
        base_score = rouge_like_f(base_txt, ex["ref"])
        # self-refine
        sr = self_refine(llm, GEN_S, CRIT_S, REFN_S, ctx, lambda t: rouge_like_f(t.split("</요약>")[0] if "</요약>" in t else t, ex["ref"]))
        report["summ"].append({"id": ex["id"], "base_score": base_score, "sr_draft": sr["draft_score"], "sr_revised": sr["revised_score"]})

    # Codegen
    for ex in CODE:
        ctx = {"prompt": ex["prompt"]}
        # base
        base_out = llm.complete(GEN_C.format(**ctx), SYSTEM)
        base_code = extract_code(base_out)
        base_score = run_tests(base_code, ex["tests"])  # 0/1
        # self-refine
        sr = self_refine(llm, GEN_C, CRIT_C, REFN_C, ctx, lambda t: run_tests(extract_code(t), ex["tests"]))
        report["code"].append({"id": ex["id"], "base_score": base_score, "sr_draft": sr["draft_score"], "sr_revised": sr["revised_score"]})

    # Print summary
    print("=== Summarization ===")
    for r in report["summ"]:
        print(r)
    print("=== Codegen ===")
    for r in report["code"]:
        print(r)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/eval_report.json","w",encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved -> outputs/eval_report.json")

if __name__ == '__main__':
    main()
