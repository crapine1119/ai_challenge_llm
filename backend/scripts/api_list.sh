
# 테스트
curl http://localhost:8000/healthz

# 크롤링
curl -X POST "http://localhost:8000/api/collect/jobkorea" \
  -H "Content-Type: application/json" \
    -d '{"company_id":1517115,"company_code":"jobkorea","job_code":"1000242","max_details":5}'


# 스타일 GET
## 프리셋 목록:
curl "http://localhost:8000/api/styles/presets"

## 특정 프리셋:
curl "http://localhost:8000/api/styles/presets/Notion"


## 생성 스타일 최신:
curl "http://localhost:8000/api/styles/generated/latest?company_code=jobkorea&job_code=1000242"


## 생성 스타일 목록(필터/페이지):
curl "http://localhost:8000/api/styles/generated?company_code=jobkorea&job_code=1000242&limit=10&offset=0"



# 모델별 예시
curl -X POST "http://localhost:8000/api/company-analysis/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "language":"ko",
    "provider":"openai",
    "model":"gpt-4o-mini",
    "json_format": true
  }'

curl -X POST "http://localhost:8000/api/company-analysis/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "language":"ko",
    "provider":"gemini",
    "model":"gemini-2.5-flash",
    "json_format": true
  }'




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


## 회사 분석(전체):
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

## 스타일만:
...

# JD Generation
## JD 생성(생성 스타일 우선 사용, 없으면 기본으로 폴백):
curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "language":"ko",
    "provider":"openai",
    "model":"gpt-4o-mini",
    "style_source":"generated",
    "default_style_name":"일반적"
  }'


## JD 생성(프리셋만 사용):
curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "style_source":"default",
    "default_style_name":"Notion"
  }'


## JD 생성(지식/스타일 직접 주입):
curl -X POST "http://localhost:8000/api/jd/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "company_code":"jobkorea",
    "job_code":"1000242",
    "knowledge_override": { "requirements": { "competencies": ["문제해결"] }, "preferred": {}, "extras": {} },
    "style_override": { "style_label": "간결", "tone_keywords": [], "section_outline": [], "templates": {} }
  }'
