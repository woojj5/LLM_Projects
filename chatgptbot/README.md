# ChatGPT Bot — Ollama 버전 (FastAPI × Next.js)

로컬 LLM **Ollama**로 동작하는 스트리밍 챗봇. Windows 기준으로 빠르게 돌릴 수 있는 TL;DR와 폴더 구조, 동작 개요, 환경변수, 실행 방법, API 명세, 트러블슈팅 등을 정리했습니다.

---

## TL;DR (Windows)

```powershell
# 0) Ollama 설치 & 모델 준비
winget install Ollama.Ollama
ollama pull llama3.1:8b        # 또는 qwen2.5:7b-instruct 등
ollama serve                    # 보통 자동으로 뜸(11434)

# 1) API(.venv) 실행
cd C:\Users\jeon9\chatgptbot
.\apps\.venv\Scripts\activate
python -m uvicorn apps.main:app --host 127.0.0.1 --port 8000

# 2) Web 실행
cd .\apps\web
npm run dev
# http://localhost:3000
```

---

## 폴더/파일 구조

```
chatgptbot/
├─ .env                        # 서버 공용 환경변수 (PROVIDER/OLLAMA/OPENAI 등)
├─ apps/                       # FastAPI 서버 루트
│  ├─ __init__.py
│  ├─ main.py                  # FastAPI 엔트리포인트(app), 라우터 포함
│  ├─ config.py                # 환경변수 로딩(load_dotenv) + Settings
│  ├─ deps.py                  # CORS 미들웨어 적용 등
│  ├─ models.py                # Pydantic 모델(ChatRequest/Response 등)
│  ├─ services/
│  │  └─ llm.py                # ★ 핵심: PROVIDER 스위치 (ollama / openai / demo)
│  ├─ routers/
│  │  ├─ chat.py               # /chat/completions, /chat/stream (SSE)
│  │  ├─ auth.py               # (선택) 로그인 예시, 현재는 미사용 가능
│  │  └─ upload.py             # (선택) 파일 업로드 예시, RAG 확장용
│  ├─ requirements.txt
│  └─ .venv/                   # Python 가상환경 (로컬)
└─ apps/web/                   # Next.js(App Router) 프런트엔드
   ├─ app/
   │  ├─ layout.tsx            # 필수: <html><body> 렌더
   │  └─ page.tsx              # 채팅 UI (SSE 수신)
   ├─ app/api/stream/route.ts  # (선택) 프록시 라우트(현재는 직접 API 호출도 가능)
   ├─ next.config.mjs          # (선택) turbopack root 고정용
   ├─ .env.local               # NEXT_PUBLIC_API_BASE 등 프런트 환경변수
   ├─ package.json
   └─ node_modules/
```

---

## 동작 개요

### Frontend (Next.js, 3000)
- `app/page.tsx`에서 입력 → `fetch(${API_BASE}/chat/stream)` POST
- 서버가 흘려주는 **SSE(`delta`)**를 읽어 토큰 단위로 말풍선에 렌더

### Backend (FastAPI, 8000)
- `routers/chat.py`
  - `POST /chat/stream` : SSE로 delta 전송
  - `POST /chat/completions` : 비스트리밍 단답
- `services/llm.py`
  - `PROVIDER=ollama` → Ollama `/api/chat`(line-delimited JSON)을 받아 **SSE(delta)**로 변환
  - `PROVIDER=openai` → OpenAI `/chat/completions` 스트리밍 사용
  - `DEMO_MODE=1` → 모델 없이 로컬에서 **타이핑 효과**로 데모 텍스트 스트리밍

---

## 환경변수

### 서버 (`chatgptbot/.env`)

```env
# 기본 프로바이더
PROVIDER=ollama            # ollama | openai

# Ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b   # 예: llama3.1:8b-q4_K_M, qwen2.5:7b-instruct 등

# OpenAI(옵션: PROVIDER=openai 때 사용)
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# 데모 모드(모델 없이 UI 테스트)
DEMO_MODE=0
```

> `apps/config.py`는 `from dotenv import load_dotenv; load_dotenv()`로 `.env`를 로드합니다.

### 프런트 (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000   # API 포트와 동일해야 함
```

> `.env.local`을 수정하면 **반드시** `npm run dev` 재시작.

---

## 실행 방법

### 1) Ollama 준비

```powershell
winget install Ollama.Ollama
ollama pull llama3.1:8b
ollama serve
curl.exe "http://127.0.0.1:11434/api/tags"   # 모델 목록 확인
```

### 2) API(백엔드)

```powershell
cd C:\Users\jeon9\chatgptbot
.\apps\.venv\Scripts\activate
python -m uvicorn apps.main:app --host 127.0.0.1 --port 8000
# 브라우저: http://127.0.0.1:8000/health  -> {"ok": true}
```

### 3) Web(프런트)

```powershell
cd C:\Users\jeon9\chatgptbot\apps\web
npm run dev
# http://localhost:3000
```

### 4) 결과

<img width="850" height="468" alt="ChatGPT Bot(stream + Ollama)" src="https://github.com/user-attachments/assets/bd2834c7-a7e6-4852-94e0-3ae765d9949f" />

---

## 주요 파일 역할

### `apps/services/llm.py` (핵심 스위치)

- **`PROVIDER=ollama`**  
  - `POST /api/chat`(Ollama) 스트림 수신 → delta 텍스트만 추출 → **SSE로 변환**

- **`PROVIDER=openai`**  
  - OpenAI `/chat/completions` SSE를 직접 파싱 → **delta 전달**

- **`DEMO_MODE=1`**  
  - 외부 호출 없이 로컬에서 **데모 텍스트를 토큰처럼** 흘림

### `apps/routers/chat.py`

- `POST /chat/stream` :  
  `llm.chat_stream()`이 반환하는 문자열 조각을  
  `data: {"delta": "..."}\n\n` 형태로 클라이언트에 전송.  
  오류 발생 시 `data: {"error": "...", "status": N}\n\n` 으로 내려 **UI에 표시**.

- `POST /chat/completions` : 단일 응답(디버그/테스트용)

### `apps/deps.py`

- `apply_cors(app)` :  
  `allow_origins=["http://localhost:3000","http://127.0.0.1:3000"]`  
  프런트가 API를 **직접 호출**할 때 CORS 문제 방지

### `apps/web/app/page.tsx`

- 입력 → 전체 히스토리와 함께 `/chat/stream` 호출  
- 수신한 SSE를 파싱해 **한 글자씩 누적 렌더**  
- 서버에서 내려준 `{error,status}` 이벤트를 **경고 말풍선**으로 표시

---

## API 명세 (요약)

### `GET /health`
- 응답: `{"ok": true}`

### `POST /chat/completions`

**Request**
```json
{
  "session_id": "demo",
  "messages": [{"role":"user","content":"안녕"}],
  "temperature": 0.7
}
```

**Response**
```json
{"output":"..."}
```

### `POST /chat/stream` (SSE)

**요청 바디**: `completions`와 동일

**응답**
```
data: {"delta":"첫 부분"}

data: {"delta":"다음 부분"}

...
data: [DONE]
```

**오류 시**
```
data: {"error":"...상세 메시지...","status":429}

data: [DONE]
```

---

## 트러블슈팅

### 포트 충돌 (WinError 10048)
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
# 또는 --port 8800으로 변경하고 NEXT_PUBLIC_API_BASE도 함께 수정
```

### `network error: Failed to fetch`
- API가 안 떠 있음 / 주소·포트 불일치 / CORS
- `http://127.0.0.1:8000/health` 확인
- `apps/web/.env.local`의 API 주소가 실제와 같아야 함
- 수정 후 `npm run dev` 재시작

### Next.js 워크스페이스 루트 경고
- `apps\package-lock.json` 삭제  
  (또는 `apps/web/next.config.mjs`에 `turbo.root = __dirname`)

### Ollama 연결 실패
```powershell
ollama serve                          # 실행 중인지
curl.exe "http://127.0.0.1:11434/api/tags"  # 모델 목록 확인
ollama pull <모델>                    # 모델 미설치 시
```

### OpenAI 429/결제 문제
- `PROVIDER=openai` 경로 사용 중이면 한도/결제 확인
- 당장은 `PROVIDER=ollama`로 전환하거나 `DEMO_MODE=1`로 UI만 테스트

---

## 확장 아이디어
- Provider 토글 UI(OpenAI ↔ Ollama) + 서버 설정 자동 전파
- RAG: 파일 업로드 → 텍스트 추출 → 임베딩(pgvector) → 검색 + 컨텍스트 주입
- 스트리밍 마크다운 렌더(코드블록 하이라이트)
- 역할/프리셋 시스템 메시지(assistant persona)
- JWT 인증 + 사용자별 히스토리 저장

---

## 검증용 명령어(옵션)

```powershell
# API 헬스
curl.exe "http://127.0.0.1:8000/health"

# Ollama 모델 목록
curl.exe "http://127.0.0.1:11434/api/tags"

# 스트림 직접 호출 (PowerShell에서 JSON 파일로)
'{"session_id":"demo","messages":[{"role":"user","content":"안녕"}],"temperature":0.7}' | Out-File -Encoding ASCII req.json
curl.exe -N -X POST "http://127.0.0.1:8000/chat/stream" -H "Content-Type: application/json" --data-binary "@req.json"
```

---
