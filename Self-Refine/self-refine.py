# self_refine.py
# ------------------------------------------------------------
# Self-Refine (generate → critique → refine) minimal runner
# Provider: Ollama (via OLLAMA_BASE_URL, OLLAMA_MODEL, PROVIDER)
# Summarization + Codegen demo in one file (no external deps beyond requests)
# ------------------------------------------------------------
from __future__ import annotations
import os
import json
import requests
import re
import textwrap
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List

# =========================
# 0) ENV & Provider
# =========================
PROVIDER         = os.getenv("PROVIDER", "ollama").lower()
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# (OpenAI envs can remain; we ignore when PROVIDER=ollama)
# OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
# OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
# OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEMO_MODE = os.getenv("DEMO_MODE", "1")  # "1" show demo inputs

if PROVIDER != "ollama":
    raise RuntimeError("This script is wired for PROVIDER=ollama. Set PROVIDER=ollama to proceed.")

# =========================
# 1) Tiny LLM client (Ollama)
# =========================
class LLM:
    def __init__(self, model: str, base_url: str, temperature: float = 0.2, max_tokens: int = 1024):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens  # Ollama num_predict controls output length; we omit for simplicity.

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        url = f"{self.base_url}/api/generate"
        full = f"{system}\n{prompt}" if system else prompt
        payload = {
            "model": self.model,
            "prompt": full,
            "temperature": self.temperature,
            "stream": False,
            # "num_predict": self.max_tokens  # uncomment if you want to hard-limit outputs
        }
        r = requests.post(url, json=payload, timeout=600)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()

# =========================
# 2) Metrics & Helpers
# =========================
def _tok(text: str) -> List[str]:
    return [t for t in text.lower().replace("\n", " ").split() if t]

def rouge_like_f(pred: str, ref: str) -> float:
    p = set(_tok(pred))
    r = set(_tok(ref))
    if not p or not r:
        return 0.0
    inter = len(p & r)
    prec = inter / len(p)
    rec  = inter / len(r)
    return 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)

PY_SNIPPET_RE = re.compile(r"```python(.*?)```", re.S | re.I)
def extract_code(snippet: str) -> str:
    m = PY_SNIPPET_RE.search(snippet)
    return m.group(1).strip() if m else snippet.strip()

def code_tests_pass_score(generated: str, tests: str, timeout: int = 10) -> float:
    code = extract_code(generated)
    wrapper = textwrap.dedent(f"""
    # AUTO WRAP
    {code}
    def __run_tests__():
        {tests}
    if __name__ == '__main__':
        __run_tests__()
    """)
    with tempfile.NamedTemporaryFile('w', suffix='_eval.py', delete=False) as f:
        f.write(wrapper)
        path = f.name
    try:
        cp = subprocess.run(["python", path], capture_output=True, text=True, timeout=timeout)
        return 1.0 if cp.returncode == 0 else 0.0
    except subprocess.TimeoutExpired:
        return 0.0

# =========================
# 3) Self-Refine Loop
# =========================
@dataclass
class LoopConfig:
    max_iters: int = 3
    patience: int = 1      # stop if no improvement for 'patience' consecutive rounds
    maximize: bool = True  # whether higher score is better

class SelfRefine:
    def __init__(
        self,
        llm: LLM,
        system_prompt: Optional[str],
        gen_tmpl: str,
        crit_tmpl: str,
        refn_tmpl: str,
        score_fn: Callable[[str], float],
        ctx: Dict[str, Any],
        cfg: LoopConfig = LoopConfig(),
        run_id: str = "run",
    ):
        self.llm = llm
        self.system = system_prompt
        self.gen = gen_tmpl
        self.crit = crit_tmpl
        self.refn = refn_tmpl
        self.score_fn = score_fn
        self.ctx = ctx
        self.cfg = cfg
        self.run_id = run_id

    def _fmt(self, tmpl: str, **kw) -> str:
        return tmpl.format(**kw)

    def _better(self, a: float, b: float) -> bool:
        return a > b if self.cfg.maximize else a < b

    def run(self) -> Dict[str, Any]:
        history = []
        best_score = -1e9 if self.cfg.maximize else 1e9
        best_text = None
        no_improve = 0

        # 1) initial draft
        draft = self.llm.complete(self._fmt(self.gen, **self.ctx), self.system)
        score = self.score_fn(draft)
        history.append({"step": 0, "type": "draft", "text": draft, "score": score})
        if self._better(score, best_score):
            best_score, best_text = score, draft

        # 2) refine loop
        for step in range(1, self.cfg.max_iters + 1):
            feedback = self.llm.complete(self._fmt(self.crit, draft=draft, **self.ctx), self.system)
            revised  = self.llm.complete(self._fmt(self.refn, draft=draft, feedback=feedback, **self.ctx), self.system)
            score_r  = self.score_fn(revised)
            history.append({"step": step, "type": "feedback", "text": feedback})
            history.append({"step": step, "type": "revised",  "text": revised,  "score": score_r})

            if self._better(score_r, best_score):
                best_score, best_text = score_r, revised
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= self.cfg.patience:
                    break
            draft = revised

        return {"run_id": self.run_id, "best_score": best_score, "best_text": best_text, "history": history}

# =========================
# 4) Task Prompts (KOR)
# =========================
SYSTEM_PROMPT = "당신은 신중하고 엄격한 전문가입니다. 거짓 정보를 생성하지 않으며, 요구된 형식을 정확히 따릅니다."

GEN_SUMMARIZE = """[역할] 너는 신뢰할 수 있는 전문가야.
[목표] 아래 입력을 요약해라. 사실성 유지, 5문장 이내.
[입력]
{input}
[출력 형식]
<요약>
(문장1) ...
</요약>
"""

CRITIQUE_SUMMARIZE = """너는 리뷰어다. 아래 요약의 결함을 간결한 불릿으로 지적하고,
각 결함마다 "개선 가이드"를 붙여라.

[원문]
{input}

[요약 초안]
{draft}

[리뷰 기준]
- 사실성: 원문에 없는 내용 추가/왜곡 여부
- 범위: 핵심 누락/불필요한 군더더기
- 명료성: 중복/장황/애매 표현
- 형식: 지정 형식 준수 여부

[출력 형식]
<피드백>
- 문제: ...
  개선: ...
- 문제: ...
  개선: ...
</피드백>
"""

REFINE_GENERIC = """너는 작성자다. 아래 "피드백"을 모두 반영해 초안을 다시 작성하라.
피드백이 상충하면 사실성과 간결성을 우선하라.

[이전 초안]
{draft}

[피드백]
{feedback}

[출력 형식]
# 최종본만 제출
<최종>
(내용)
</최종>
"""

GEN_CODE = """너는 실용적인 파이썬 개발자다. 아래 요구사항을 만족하는 코드를 작성해라.
- 경계조건/예외처리 우선, 가독성 중시.
- 하나의 self-contained 파이썬 스니펫으로 출력한다.

[요구사항]
{prompt}
"""

CRITIQUE_CODE = """너는 시니어 코드 리뷰어다. 아래 코드 초안을 읽고 **테스트 통과**와 **경계조건**을 최우선으로 지적하고 개선 가이드를 제시하라.

[요구사항]
{prompt}

[코드 초안]
{draft}

[리뷰 기준]
- 정확성/경계조건/예외처리
- 효율성/가독성
- self-contained 스니펫 여부

[출력 형식]
<피드백>
- 문제: ...
  개선: ...
- 문제: ...
  개선: ...
</피드백>
"""

# =========================
# 5) Demo Data (inline)
# =========================
DEMO_SUMM = [
    {
        "id": "ex1",
        "input": "PatchTST는 시계열을 패치로 나눠 학습하는 트랜스포머 기반 모델이다. 장점은 긴 시퀀스 처리와 로버스트한 일반화이며, 단점은 데이터 스케일 민감도와 하이퍼파라미터 탐색 비용이다.",
        "reference": "PatchTST는 패치 기반 트랜스포머로 긴 시퀀스에 강점이 있다. 다만 스케일링과 튜닝이 필요하다."
    }
]
DEMO_CODE = [
    {
        "id": "fib",
        "prompt": "정수 n(0<=n<=1000)에 대해 피보나치 수 F(n)을 반환하는 함수 fibonacci(n)을 구현하라. 음수나 비정수 입력은 예외.",
        "tests": "assert fibonacci(0)==0; assert fibonacci(1)==1; assert fibonacci(10)==55; import pytest; import math; with pytest.raises(Exception): fibonacci(-1); with pytest.raises(Exception): fibonacci(1.2)"
    }
]

# =========================
# 6) Task Runners
# =========================
def run_summarization(llm: LLM, items: List[Dict[str, Any]]):
    results = []
    for row in items:
        rid = row["id"]
        inp = row["input"]
        ref = row.get("reference", inp)
        # score on content inside <최종>...</최종> or <요약>...</요약> if present
        def score_fn(text: str) -> float:
            t = text
            low = text.lower()
            if "<최종>" in text and "</최종>" in text:
                try:
                    t = text.split("<최종>", 1)[1].split("</최종>", 1)[0]
                except Exception:
                    t = text
            elif "<요약>" in text and "</요약>" in text:
                try:
                    t = text.split("<요약>", 1)[1].split("</요약>", 1)[0]
                except Exception:
                    t = text
            return rouge_like_f(t, ref)

        sr = SelfRefine(
            llm=llm,
            system_prompt=SYSTEM_PROMPT,
            gen_tmpl=GEN_SUMMARIZE,
            crit_tmpl=CRITIQUE_SUMMARIZE,
            refn_tmpl=REFINE_GENERIC,
            score_fn=score_fn,
            ctx={"input": inp},
            cfg=LoopConfig(max_iters=3, patience=1, maximize=True),
            run_id=f"summ_{rid}",
        ).run()
        results.append(sr)
        print(f"[SUMM DONE] {rid}: score={sr['best_score']:.3f}")
    return results

def run_codegen(llm: LLM, items: List[Dict[str, Any]]):
    results = []
    for row in items:
        rid = row["id"]
        prompt = row["prompt"]
        tests  = row.get("tests", "")

        def score_fn(text: str) -> float:
            return code_tests_pass_score(text, tests, timeout=12)

        sr = SelfRefine(
            llm=llm,
            system_prompt=SYSTEM_PROMPT,
            gen_tmpl=GEN_CODE,
            crit_tmpl=CRITIQUE_CODE,
            refn_tmpl=REFINE_GENERIC.replace("<최종>", "```python").replace("</최종>", "```"),
            score_fn=score_fn,
            ctx={"prompt": prompt},
            cfg=LoopConfig(max_iters=3, patience=1, maximize=True),
            run_id=f"code_{rid}",
        ).run()
        results.append(sr)
        print(f"[CODE DONE] {rid}: score={sr['best_score']:.3f}")
    return results

# =========================
# 7) Main
# =========================
def main():
    print(f"[INFO] PROVIDER={PROVIDER}, OLLAMA_MODEL={OLLAMA_MODEL}, OLLAMA_BASE_URL={OLLAMA_BASE_URL}")
    llm = LLM(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2, max_tokens=1024)

    # Demo switch
    do_demo = (str(DEMO_MODE).strip() != "0")

    # --- Summarization demo
    if do_demo:
        run_summarization(llm, DEMO_SUMM)
    # --- Codegen demo
    if do_demo:
        run_codegen(llm, DEMO_CODE)

    print("[DONE] self-refine finished.")

if __name__ == "__main__":
    main()
