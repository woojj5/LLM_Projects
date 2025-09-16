# Self-Refine (Ollama Slim Kit)

> **Self-Refine = Generate → Critique → Refine**  
> 이 프로젝트는 OpenAI 의존성 없이 **Ollama 전용**으로 동작하는 **슬림 구조** Self-Refine 데모입니다.  
> 챗봇 REPL, 오프라인 평가, 단일 데모 스크립트를 포함합니다.

---

## 📂 폴더 구조

```
Self-Refine/
├─ .venv/              # 파이썬 가상환경
├─ chat.py             # Self-Refine 챗봇 REPL
├─ eval.py             # Base vs Self-Refine 성능 평가
├─ self-refine.py      # 단일 데모 (요약 + 코드 생성)
└─ README.md           # 안내 문서 (본 파일)
```

---

## ⚙️ 설치 & 준비

### 1) 가상환경
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2) 의존성
```bash
pip install requests
```

### 3) Ollama 설치 & 실행
- **macOS**
  ```bash
  brew install ollama
  ollama serve
  ```
- **Linux**
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ollama serve
  ```
- **Windows (PowerShell)**
  ```powershell
  winget install Ollama.Ollama
  ```

### 4) 모델 받기
```bash
ollama pull llama3.1:8b           # 요약/범용
ollama pull qwen2.5:7b-instruct   # 코드 생성 친화
```

---

## 🔧 환경변수 (.env 예시)

```
PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b

# (OpenAI 값이 있어도 무시됨. PROVIDER=ollama면 OpenAI 사용 안 함)
OPENAI_API_KEY=***
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

DEMO_MODE=1   # 1=내장 데모 실행, 0=비활성화
```

---

## ▶️ 실행 방법

### 1) 단일 데모 (요약 + 코드)
```bash
python self-refine.py
```
- `DEMO_MODE=1`이면 내장 샘플로 요약/코드 테스트 자동 실행

### 2) 챗봇 REPL
```bash
python chat.py
```
- 콘솔에 입력하면 Self-Refine 루프(초안 → 비평 → 재작성) 2스텝 적용된 답변 출력

### 3) 오프라인 평가
```bash
python eval.py
```
- Base vs Self-Refine 결과 점수를 비교 (요약=ROUGE-like, 코드=테스트 통과율)
- 결과는 콘솔 + `outputs/eval_report.json` 저장

---

## 🧪 좋은 데모 입력 예시
- **형식 강제**: “정확히 3개의 불릿으로만 답하라”  
- **누락 보완**: “반례 1개, 한계 1개 포함”  
- **다중 제약**: 길이 + 톤 + 금지어 동시에 요구  
- **코드 생성**: 간단한 알고리즘(피보나치, 소수 판별 등)

이런 입력은 Self-Refine 개선 효과가 눈에 띄게 드러납니다.

---

## 🛡️ 주의사항
- 코드생성 테스트는 로컬 파이썬 프로세스를 실행합니다. **신뢰할 수 없는 입력으로는 실행하지 마세요.**
- 외부에서 Ollama 서버에 접속할 경우 방화벽/보안 설정을 반드시 확인하세요.

---

## 📄 라이선스
본 예제 코드는 자유롭게 수정/내부 활용 가능합니다.
