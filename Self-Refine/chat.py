# chat_repl.py
from __future__ import annotations
import os, re
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
import requests

# ---- Minimal Ollama client ----
class LLM:
    def __init__(self, model: str, base_url: str, temperature: float = 0.2):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        url = f"{self.base_url}/api/generate"
        full = f"{system}\n{prompt}" if system else prompt
        payload = {"model": self.model, "prompt": full, "temperature": self.temperature, "stream": False}
        r = requests.post(url, json=payload, timeout=600)
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

@dataclass
class LoopConfig:
    max_iters: int = 2
    patience: int = 1

class SelfRefine:
    def __init__(self, llm: LLM, system: str, gen: str, crit: str, refn: str, ctx: Dict[str, Any], score_fn: Callable[[str], float] | None, cfg: LoopConfig):
        self.llm, self.system, self.gen, self.crit, self.refn = llm, system, gen, crit, refn
        self.ctx, self.score_fn, self.cfg = ctx, score_fn, cfg

    def _fmt(self, t: str, **kw):
        return t.format(**kw)

    def run(self) -> str:
        draft = self.llm.complete(self._fmt(self.gen, **self.ctx), self.system)
        best, best_s = draft, -1e9
        if self.score_fn:
            try:
                s = self.score_fn(draft)
                best_s = s
            except Exception:
                pass
        no_imp = 0
        for _ in range(self.cfg.max_iters):
            fb = self.llm.complete(self._fmt(self.crit, draft=draft, **self.ctx), self.system)
            rev = self.llm.complete(self._fmt(self.refn, draft=draft, feedback=fb, **self.ctx), self.system)
            if self.score_fn:
                try:
                    s = self.score_fn(rev)
                    if s > best_s:
                        best, best_s = rev, s
                        draft = rev
                        no_imp = 0
                        continue
                    else:
                        no_imp += 1
                        if no_imp >= self.cfg.patience:
                            break
                except Exception:
                    best = rev
                    break
            else:
                best = rev
                draft = rev
        return best

SYSTEM = "당신은 신중하고 엄격한 전문가입니다. 거짓 정보를 생성하지 않으며, 요구된 형식을 정확히 따릅니다."

GEN_GENERIC = """[역할] 유용하고 정확한 어시스턴트.
[목표] 사용자 질문에 간결하고 정확하게 답하라.
[질문]\n{query}\n[출력]\n<답변>\n(내용)\n</답변>\n"""

CRIT_GENERIC = """너는 리뷰어다. 아래 답변의 결함을 간단한 불릿으로 지적하고 개선안을 제시하라. 사실성/명료성/간결성/형식 준수를 보라.\n[질문]\n{query}\n[답변 초안]\n{draft}\n<피드백>\n- 문제: ...\n  개선: ...\n</피드백>\n"""

REFN_GENERIC = """너는 작성자다. 피드백을 반영해 답변을 다시 작성하라.\n[이전]\n{draft}\n[피드백]\n{feedback}\n<답변>\n(내용)\n</답변>\n"""

# Optional simple scoring: prefer shorter (<= 2000 chars) and remove vacuous phrases
def simple_quality_score(text: str) -> float:
    t = re.sub(r"\s+", " ", text)
    penalty = 0.0
    if len(t) > 2000:
        penalty += (len(t) - 2000) / 1000
    filler = sum(t.lower().count(x) for x in ["아시다시피", "당신", "독자", "여러분"])
    return 1.0 - penalty - 0.1 * filler


def main():
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    llm = LLM(model=model, base_url=base)
    print(f"[REPL] model={model} base={base}  (Ctrl+C to exit)")
    while True:
        try:
            q = input("you> ").strip()
            if not q:
                continue
            if q.lower() in {"/quit", "/exit"}:
                break
            ctx = {"query": q}
            sr = SelfRefine(llm, SYSTEM, GEN_GENERIC, CRIT_GENERIC, REFN_GENERIC, ctx, simple_quality_score, LoopConfig(max_iters=2, patience=1))
            ans = sr.run()
            print("bot>", ans)
        except KeyboardInterrupt:
            print("\nbye!")
            break

if __name__ == "__main__":
    main()

