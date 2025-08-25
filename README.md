# JobKorea GenAI Job Description (JD) Generation Project

> 본 프로젝트는 korcen (Apache-2.0)을 포함하고 있으며, 패키징 이슈로 경로만 일부 수정하여 사용합니다.


---
# 설치 방법
### Git
> git clone https://github.com/crapine1119/ai_challenge_llm.git

### Backend
1. docker 설치
> https://docs.docker.com/desktop/setup/install/mac-install/
2. uv 설치
> curl -LsSf https://astral.sh/uv/install.sh | sh
3. env 설정
> cd {project_root}/backend \
> cp .env.example .env

**! .env의 OPENAI_API_KEY에 api key를 반드시 등록해주세요** 


### Frontend
1. macOS/Linux nvm: Node LTS 설치 (권장: 20.x 또는 22.x)\
   (이미 설치 되어있다면 넘어가셔도 됩니다.)
> curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

2. 모듈 설치 (새로운 터미널에서 실행)
> nvm install --lts \
> nvm use --lts \
> cd {project_root}/frontend \
> npm install

# 실행 방법 
1. backend 실행
> cd {project_root} \
> chmod +x scripts/run_backend.sh \
> scripts/run_backend.sh start

2. frontend 실행
> cd {project root}/frontend \
> npm run dev

3. 브라우저 실행
> http://localhost:5173

* 기타
>./scripts/run_backend.sh stop \
>./scripts/run_backend.sh logs \

>./scripts/run_frontend.sh status \
>./scripts/run_frontend.sh logs \
>./scripts/run_frontend.sh stop

# 앱 설명
접속시: 회사 / 직무 선택 (다른 회사 / 직무를 원할 경우 3으로 이동합니다. 이외에는 순서대로 진행합니다)
1. 직무 분석하기:
   - 분석하기를 누를 경우 먼저 회사의 스타일을 추출하고, 현재 화면에 보이는 스타일들을 활용하여 JD 생성을 진행합니다.
   - 해당 스타일은 사전에 설정한 3가지 템플릿 (간결, 상세, 트렌디)을 기준과, JD를 기반으로 LLM이 생성한 결과입니다.
   - 해당 페이지는 실서비스에서 배치 (사용자가 적은 시간에 자동으로)로 실행되는 것을 목표로 합니다. 

2. 실시간 JD 생성하기
   - 분석하기에서 사전에 생성한 JD를, 마치 실시간 서비스인것 처럼 보여주는 페이지입니다.
   - 추후에 생성된 JD를 사용자의 입력을 받아 수정하고, 이를 기반으로 LLM을 재생성하는 기능을 추가할 예정입니다. \
     (backend에만 해당 기능이 존재하고 frontend에는 반영되지 않았습니다.)
   - 또한, 생성 기능이 추가될 경우 아래의 전략에서 제시할 JD 갤러리 페이지를 팝업으로 보여줄 예정입니다. 

3. 직무 추가하기
   - 잡코리아 웹에 표시되는 회사 및 직무명의 코드를 기입할 경우, 새로운 직무에 대한 JD를 생성할 수 있습니다.

4. 주의사항
   - PoC용 앱으로 LLM을 활용하여 빠르게 frontend 코드를 구현하여, 안정성이 떨어질 수 있습니다. \
   페이지 로드가 안된다면 새로 고침을 누르거나 재접속해주시면 감사하겠습니다.
   - 직무 추가하기의 경우 PoC용으로 잡코리아 backend를 모방하기 위해 임시로 구현하였습니다. \
   과하게 요청할 경우 접속 인증이 필요하여, 실패하는 경우가 발생합니다. 이 경우에는 해당 페이지로 직접 접속하여 인증을 해제해주시면 다시 정상적으로 작동합니다.


---

# 1. 문제 정의

### JD 생성 서비스의 문제점
📌 이슈1. LLM의 부정확한 응답 및 민감 정보 처리 문제
> 기업 정보에 없는 내용을 임의로 생성하거나, 성별·연령 등 부적절한 조건이 포함되는 경우 발생 \
> 욕설 또는 민감한 정보(예: 연봉)에 대한 비판 없는 응답 문제 발생

📌이슈2. LLM 응답 지연으로 인한 사용자 이탈

본 프로젝트에서는 LLM 서비스를 운영하면서 피할 수 없는 위 두가지 문제를 다음의 방법들을 통해 해결하려고 한다.

1) Prompt Engineering 기반의 사전 Entity 추출 및 통제
2) 가드레일 (input, output) 정책과 통제된 정보를 기반으로 한 JD 생성
3) Queue 관리에 기반한 실시간 대기 정보 제공

## 1.1. Targets & Strategies Summary

- **Entity Extraction**: 기업·JD·질의에서 도메인 필드 추출 (역량, 우대, 근무형태 등)
  - 사전에 내용을 미리 추출함으로써 RAG 방식으로 Hallucination 및 민감 정보를 통제하기 위함
  - 템플릿 형태로 가공하여 사용자에게 보여줌
- **JD Generation**: 템플릿 (섹션, 스타일, 기타 요구사항)을 반영하여 최종 JD 출력
  - 사전 생성된 내용을 보여줌으로써 사용자 경험을 개선하고, 운영 안정성을 높일 수 있음 (일배치로 미리 JD를 생성하는 방식)
  - 사용자가 원할 경우, 사전 생성된 JD를 수정하고 LLM을 통하여 2차 가공
  - 생성된 내용이 있고, 사전 생성 프롬프트보다 적은 수의 토큰만 사용하기 때문에 빠른 응답이 가능 (다중 요청 상황 대응)
- **LLM queue**: 사용자에게 실시간으로 남은 대기시간을 보여주는 기능
  - Background에서 생성이 진행되며, 처리 평균 시간을 계산하여 응답 예상 시간을 제공 
  - (TODO) 대기 시간이 일정 시간 이상 길어질 경우, JD 갤러리 (타 회사에서 생성한 JD를 확인하고, 댓글/좋아요 등의 기능) 화면을 보여줌
  - (TODO) 다중 API 운영을 통한 응답 시간 최소화 (gateway 서버 개발 필요)
- **Guardrail**: 사용자가 부적절한 요청을 했을 때, 이를 막기 위한 기능
  - korcen과 같은 룰 기반의 패키지지로 빠르게 1차 방어
  - (TODO) Deeplearning-based API (e.g. openai omni-moderation-latest; 비용 발생)를 활용하여 2차 방어 
  - (TODO) LLM-finetuning을 활용하여 sLLM 기반의 guardrail model을 직접 운영

# 2. Method
## 2.1. Entity Extraction

* 서비스 상황에서 사용자 또는 LLM에 의해 부적절한 요청, 답변이 생성되는 것은 매우 위험 (가드레일 필수) 

* 이러한 문제를 “사전 생성 데이터 중심 RAG” 기반으로 정확도·안전 확보하는 것이 목적

* 사전에 정보를 추출할 수 있는 소스는, Job Korea에 존재하는 채용 공고와 직무에 대한 정보
  * 해당 정보들로부터 JD의 스타일, 직무에 대한 기술 정보 (역량, 세부 기술 등)을 추출


* Workflow
  - JD + 직무명 (few shot): 스타일 추출, 기술 추출 
  - 직무명 (zero shot): 일반적으로 요구되는 지식/기술명 추출

* Entity 설계 정보
  * CompanyKnowledge: 기업 소개·문화·가치관·핵심 역량(없으면 null 유지)
  * StylePreset: 정형적, 트렌디(Notion류), 기술상세, 회사 고유 톤

(데이터의 경우 크롤링을 통해 Job Korea 홈페이지에서 수집하였습니다.)

## 2.2 JD Generation
* 사전에 생성한 "Entity"를 기반으로 JD를 생성하여, API/GPU 사용량을 최소화

* 템플릿 별 N개의 JD를 제공하고 사용자가 수정할 수 있는 기능을 제공
  * 수정하는 경우:
    * 사전 DB의 정보가 아닌, 정제된 적은 토큰을 입력하고 Task가 단순하기 때문에 (Rewriting) 
    
      적은 리소스만 가지고도 효율적으로 TTFT를 개선할 수 있음 
  * 수정하지 않는 경우:
    * 생성된 JD를 사용자가 선택할 경우 확인을 위한 경고 문구를 호출하고 (TODO), 웹사이트에 공고를 업로드함 (기존 시스템과의 연동)

* 마지막으로, 노출되는 **모든 생성되는 JD**는 반드시 streaming으로 처리하여, 사용자 경험을 극대화할 수 있도록 한다.   

## 2.3. LLM Queue
* 2.2에서 제시한 전략은 하드웨어 리소스 관점에서의 최적화인 반면, LLM Queue의 경우 사용자 경험 관점에서의 대응 전략이다.
* 자원이 무한하다면 수많은 API를 gateway 서버와 함께 사용하는 것이 가능하다 (라운드로빈 또는 vllm 등의 패키지에서 제공하는 token 처리량을 활용하여 개발이 가능하다).
* 그러나, 현실적인 비용을 생각해봤을때, 실시간 대기 시간과 퍼센티지 등을 제공하여 사용자 경험을 개선하는 것이 더 효율적일 수 있다.
* 단순 대기 시간만으로는 사용자 이탈을 막기 어렵기 때문에, 인사 담당자들이 업무에 도움이 되는 정보들을 얻을 수 있는 "JD 갤러리"를 운영하는 것이 이탈 방지에 도움이 될 것이라고 생각한다. 

### 2.3.1 JD 갤러리
* JD 생성을 기다리는 동안 자연스럽게 경쟁사 또는 관련 직무 JD를 보여주고, 생성된 JD의 수정에 도움이 될만한 정보를 제공한다. 
* 특히, 관련 직무/경쟁사의 인기 지원 공고, 지원자 현황, 통계 차트, 합격률, 팁, 좋아요/댓글 기능들을 함께 제공하여, 정보와 재미를 동시에 느낄 수 있도록 유도한다 (TODO)
* 이러한 검색 기능을 제공하기 위해선, 간단한 키워드 / 벡터 검색을 제공하는 검색엔진을 활용할 수 있으며, 서비스 고도화를 위해 Splade와 같은 Hybrid Search 또는 Embedding Model fine-tuning을 진행할 수 있다. 
* 또한, 대기 시간이 아니더라도 별도의 페이지를 상시 운영하며, 인사 담당자 뿐 아니라 일반 사용자들도 함께 소통할 수 있도록 설계한다.

## 2.4. Guardrail
* 우선 korcen 룰 기반의 패키지로 입/출력을 모두 빠르게 1차적으로 방어하며, 룰에 새로운 규칙을 추가하여 문제가 재발하는 경우를 방지할 수 있다. 
* 그러나 문맥이 고려되지 않기 때문에, AI 기반의 가드레일이 추가적인 전략이 될 수 있다.
* 현재 공개된 모델 (e.g. openai omni-moderation-latest) 들이 텍스트의 위험 정도를 수치로서 제공해주고 있지만, 한국어 이해는 상대적으로 떨어지는 모습을 보인다. 
* 따라서, 장기적인 관점에서 sLLM fine-tuning을 통한 가드레일 모델 운영이 반드시 필요하다고 생각한다. 
* 마지막으로, GenAI 서비스에서 모든 과정의 승인은 사용자의 선택으로 결정되어야하므로, 이를 사용자에게 분명히 고지하고 서비스를 운영하는 것이 중요할 것이다. 

---
# 3. Prompt / Context Engineering 전략
- 기술/스타일 영역의 경우 반복해서 뽑았을때도 일정하게 유지되는 것을 목표 \
  어느정도의 자유도를 주면서도 재생성시 값이 크게 달라지지 않도록 하기 위해 temperature는 0.3으로 설정
- seed 고정, top_k / top_p를 낮추는 방법으로도 적용 가능
- JD 생성의 경우 오히려 다양한 형식으로 생성하도록 temperature를 0.7로 설정하여, 사용자가 항상 정형화된 답변을 받는다는 느낌을 들지 않도록 유도

### 3.1. 프롬프트 역할 / 목록
* JD를 활용하여 회사만의 고유 스타일 생성
> backend/src/prompts/ko/company.analysis.jd_style.v1.yaml

* JD를 활용한 회사에 필요한 직무 관련 지식 / 기술 생성
> backend/src/prompts/ko/company.analysis.job_competency_few_shot.v1.yaml

* 직무명만 입력하여, 직무 관련 지식 / 기술을 폭넓게 생성 (추후에 검색 tool을 연동함으로써, 빠르게 바뀌는 직무 지식을 보완)
> backend/src/prompts/ko/company.analysis.job_competency_zero_shot.v1.yaml

* 앞서 생성한 스타일, 지식을 활용하여 템플릿에 맞는 JD를 생성
> backend/src/prompts/ko/jd.generation.v1.yaml

### 3.2. 설계 전략
- 개인정보 및 민감정보를 사용자가 임의로 수정할 수 없게 만들기 위해, 시스템 프롬프트는 사용자가 수정할 수 없도록 설계했습니다.
- company.analysis 유저 프롬프트는 회사의 정보들을 사전에 생성하는 것을 목표로 합니다.
- 이를 위해 RAG와 같이 JD를 fewshot으로 제공하였고, 생성 예시를 한번 더 제공하여 json 형식을 맞추도록 유도했습니다.
- jd.generation 프롬프트는 실제 JD를 입력하지 않고 company.analysis로 생성한 지식과 스타일만 입력으로 들어가게 됩니다.
- 이때, 생성 단계에서 사용자의 입력이 들어갈 수 없기 때문에, 부적절한 내용을 생성하는 것을 방지할 수 있는 효과가 있습니다.


### 4. 기타 Backend Service API
Frontend에 반영하지 못했으나, Backend에 PoC 수준의 기능 구현이 완료된 API들을 기재합니다.
(backend/scripts/api_list.sh에 정리되어있습니다.)

* JD 수정 api
knowledge_override, style_override 입력을 통해, 사용자가 수정한 내용을 반영하여 재생성할 수 있도록 만들었습니다.
> curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "company_code": "jobkorea",
    "job_code": "1000242",
    "knowledge_override": {
      "introduction": "비판적이고 직관적으로 생각합니다.",
      "culture": "실험 중심, 데이터 기반 의사결정",
      "values": ["고객집착", "학습과 공유", "끝까지 실행"],
      "ideal_traits": ["문제정의 능력", "협업", "주도성"],
      "requirements": {
        "competencies": ["데이터 해석", "문제해결"],
        "skills": ["Python", "PyTorch", "SQL"],
        "project_experience": ["추천모델 운영", "실시간 서빙"]
      },
      "preferred": {
        "competencies": ["성능최적화", "A/B 테스트 설계"],
        "skills": ["TensorFlow", "ONNX", "Triton"],
        "project_experience": ["대규모 트래픽 환경"]
      },
      "extras": {
        "benefits": ["자기계발비", "리모트 옵션"],
        "locations": ["서울 본사"],
        "hiring_process": ["서류", "실무면접", "임원면접", "처우협의"]
      }
    },
    "style_override": {
      "style_label": "기술 중심-협력적",
      "tone_keywords": ["혁신적", "협력적", "실험적"],
      "section_outline": ["About Us", "Team Introduction", "Responsibilities", "Qualifications", "Preferred Qualifications", "Hiring Process"],
      "templates": {
        "About Us": "회사의 미션과 임팩트를 간결히 소개합니다.",
        "Team Introduction": "팀이 해결하는 문제와 협업 방식을 설명합니다.",
        "Responsibilities": "핵심 역할과 기대 결과를 불릿으로 정리합니다.",
        "Qualifications": "필수 요건을 구체적으로 나열합니다.",
        "Preferred Qualifications": "우대 조건을 구체적으로 나열합니다.",
        "Hiring Process": "전형 절차를 간단히 제공합니다."
      }
    }
  }'


* Concurrency Stress Test api
사용자가 몰려 대기해야하는 상황을 구현한 api입니다.
TASK_ID를 반환하며, 해당 url에 접근 시 현재 상태와 stream 기반의 output을 받을 수 있습니다.

> curl -sS -X POST "http://localhost:8000/api/llm/queue/sim-then-generate" \
  -H 'Content-Type: application/json' \
  -d '{
    "prequeue_count": 30,
    "sim": { "min_sec": 3, "max_sec": 5 },
    "jd": {
      "provider": "openai",
      "model": "gpt-4o",
      "language": "ko",
      "company_code": "jobkorea",
      "job_code": "1000242",
      "style_source": "default",
      "default_style_name": "일반적"
    },
    "wait_timeout_sec": 600
  }'

* guardrail
> curl -X POST "http://localhost:8000/api/guardrail/check" \
  -H "Content-Type: application/json" \
  -d '{"text": "이건 그냥 문장", "comment": "XX 같은 단어 포함"}'

# 진행도
curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/status"

# non-stream 결과
(stream에서 result를 호출하면 {"detail":"stream-mode task. Use /tasks/{task_id}/stream"}를 출력)

curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/result"

# 완료 결과 (stream인 경우)

curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/event"
