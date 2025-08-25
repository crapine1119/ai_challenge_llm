
# 테스트
curl http://localhost:8000/healthz

# 크롤링
curl -X POST "http://localhost:8000/api/collect/jobkorea" \
  -H "Content-Type: application/json" \
    -d '{"company_id":1517115,"company_code":"jobkorea","job_code":"1000242","max_details":3}'



curl -X POST "http://localhost:8000/api/collect/jobkorea" \
  -H "Content-Type: application/json" \
    -d '{"company_id":1392633,"company_code":"hwocean","job_code":"1000201","max_details":3}'

curl -X POST "http://localhost:8000/api/collect/jobkorea" \
  -H "Content-Type: application/json" \
    -d '{"company_id":1392633,"company_code":"hwocean","job_code":"1000242","max_details":3}'


# 스타일 GET
## 프리셋 목록:
curl "http://localhost:8000/api/styles/presets"

## 특정 프리셋:
curl "http://localhost:8000/api/styles/presets/Notion"

## 생성 스타일 최신:
curl "http://localhost:8000/api/styles/generated/latest?company_code=jobkorea&job_code=1000242"


## 생성 스타일 목록(필터/페이지):
curl "http://localhost:8000/api/styles/generated?company_code=jobkorea&job_code=1000242&limit=10&offset=0"


# Company Analysis

## zero shot
curl -X POST "http://localhost:8000/api/company-analysis/knowledge/zero-shot" \
  -H "Content-Type: application/json" \
  -d '{
    "job_code":"1000242",
    "language":"ko",
    "provider":"openai",
    "model":"gpt-4o",
    "json_format": true
  }'

## 회사 분석 (fewshot + style)
curl -X POST "http://localhost:8000/api/company-analysis/analyze-all" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "language":"ko",
    "provider":"openai",
    "model":"gpt-4o",
    "json_format": true
  }'
## Option: few shot only
curl -X POST "http://localhost:8000/api/company-analysis/knowledge/few-shot" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "language": "ko",
    "top_k": 3,
    "min_chars_per_doc": 200,
    "save": true,
    "json_format": true,
    "provider": "openai",
    "model": "gpt-4o"
  }'

## Option: style only
curl -X POST "http://localhost:8000/api/company-analysis/style" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "language": "ko",
    "top_k": 3,
    "save": true,
    "json_format": true,
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  }'

# JD Generation
## simple
curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "provider": "openai",
    "model": "gpt-4o",
    "style_source": "generated",
    "language": "ko"
  }'

curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "provider": "openai",
    "model": "gpt-4o",
    "default_style_name": "Notion",
    "language": "ko"
  }'

curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "provider": "openai",
    "model": "gpt-4o",
    "default_style_name": "일반적",
    "language": "ko"
  }'

## stream
curl -X POST "http://localhost:8000/api/jd/generate/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "jobkorea",
    "job_code": "1000242",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "style_source": "generated",
    "language": "ko"
  }'


## with style override (사용자가 수정을 원할 경우, 수정한 텍스트를 override 변수로 받아서 요청)
curl -X POST "http://localhost:8000/api/jd/generate" \
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


## 최신 JD 조회
curl "http://localhost:8000/api/jd/latest?company_code=jobkorea&job_code=1000242"
## ID로 조회
curl "http://localhost:8000/api/jd/123"
## 목록 조회
curl "http://localhost:8000/api/jd?company_code=jobkorea&job_code=1000242&limit=10"



# non-stream queue 테스트 (내부 테스트용으로 실제 서비스에서 쓸 일은 없음)
## 동기 처리; 10명 대기(가짜) → 다 끝나면 실제 /jd/generate를 내부 호출, 결과 반환
curl -sS -X POST "http://localhost:8000/api/llm/queue/sim-then-generate?mode=sync&stream=false" \
  -H 'Content-Type: application/json' \
  -d '{
    "prequeue_count": 10,
    "sim": { "min_sec": 1, "max_sec": 3 },
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


# async stream queue 테스트 (기본값으로 실제 서비스용. 차례까지 대기한 후에 stream output)
## 비동기 + stream
curl -sS -X POST "http://localhost:8000/api/llm/queue/sim-then-generate" \
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

# 진행도
curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/status"

# non-stream 결과 (stream에서 result를 호출하면 {"detail":"stream-mode task. Use /tasks/{task_id}/stream"}를 출력)
curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/result"

# 완료 결과 (stream인 경우)
curl -sS "http://localhost:8000/api/llm/queue/tasks/<TASK_ID>/event"


# guardrail
curl -X POST "http://localhost:8000/api/guardrail/check" \
  -H "Content-Type: application/json" \
  -d '{"text": "이건 그냥 문장", "comment": "damn 같은 단어 포함"}'


# 회사 목록
curl "http://localhost:8000/api/catalog/companies/collected"
# => {"companies":["jobkorea"]}

# 직무 목록
curl "http://localhost:8000/api/catalog/jobs/collected?company_code=잡코리아(유)"
# => {"company_code":"jobkorea","jobs":[{"code":"1000242","name":"AI/ML 엔지니어"}]}