from fastapi import APIRouter, HTTPException

from api.schemas.collect_schema import CollectRequest, CollectResponse
from service.collector import crawl_jobkorea_and_store

router = APIRouter(prefix="/collect", tags=["collector"])


@router.post("/jobkorea", response_model=CollectResponse)
async def collect_jobkorea_data(request: CollectRequest):
    try:
        result = await crawl_jobkorea_and_store(
            company_id=request.company_id,
            company_code=request.company_code,
            job_code=request.job_code,
            list_params=request.list_params,
            max_details=request.max_details,
            save_meta=request.save_meta,
        )
        return CollectResponse(saved_raw=result["saved_raw"], saved_meta=result["saved_meta"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
