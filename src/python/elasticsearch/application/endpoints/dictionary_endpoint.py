import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status
from src.python.elasticsearch.config.connections.mongodb_connection_manager import get_mongodb_database
from src.python.elasticsearch.application.services.api.dictionary_service import (
    UserDictionaryService, DecompoundDictionaryService, SynonymDictionaryService,
    CorrectionDictionaryService, StopwordDictionaryService
)
from src.python.elasticsearch.application.schemas.requests.dictionary.dictionary_req import (
    UserDictionaryCreateReq, UserDictionaryUpdateReq,
    DecompoundDictionaryCreateReq, DecompoundDictionaryUpdateReq,
    SynonymDictionaryCreateReq, SynonymDictionaryUpdateReq,
    CorrectionDictionaryCreateReq, CorrectionDictionaryUpdateReq,
    StopwordDictionaryCreateReq, StopwordDictionaryUpdateReq
)
from src.python.elasticsearch.application.schemas.responses.dictionary.dictionary_res import DictionaryListRes
from src.python.elasticsearch.application.endpoints.auth_endpoint import get_current_user
from src.python.elasticsearch.application.endpoints.rbac import require_role
from src.python.elasticsearch.common.enums.user_role import UserRole
from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus

dictionary_endpoint = APIRouter()
logger = logging.getLogger(__name__)

# ==========================================
# User Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/user/search")
async def search_user_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/user/admin/search")
async def admin_search_user_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/user")
async def create_user_dict(request: Request, req: UserDictionaryCreateReq, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/user/{word}")
async def update_user_dict(request: Request, word: str, req: UserDictionaryUpdateReq, current_user=Depends(get_current_user)):
    # If status change is requested, only ADMIN can do it
    if req.status is not None and req.status in (DictionaryStatus.APPROVED, DictionaryStatus.REJECTED):
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can approve or reject dictionary entries")
        req.approver = current_user.user_id
    elif current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIEWER cannot modify dictionary entries")
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.update(word, req)

@dictionary_endpoint.delete("/user/{word}")
async def delete_user_dict(request: Request, word: str, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.delete(word)


# ==========================================
# Decompound Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/decompound/search")
async def search_decompound_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/decompound/admin/search")
async def admin_search_decompound_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/decompound")
async def create_decompound_dict(request: Request, req: DecompoundDictionaryCreateReq, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/decompound/{compound_word}")
async def update_decompound_dict(request: Request, compound_word: str, req: DecompoundDictionaryUpdateReq, current_user=Depends(get_current_user)):
    if req.status is not None and req.status in (DictionaryStatus.APPROVED, DictionaryStatus.REJECTED):
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can approve or reject dictionary entries")
        req.approver = current_user.user_id
    elif current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIEWER cannot modify dictionary entries")
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.update(compound_word, req)

@dictionary_endpoint.delete("/decompound/{compound_word}")
async def delete_decompound_dict(request: Request, compound_word: str, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.delete(compound_word)


# ==========================================
# Synonym Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/synonym/search")
async def search_synonym_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/synonym/admin/search")
async def admin_search_synonym_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/synonym")
async def create_synonym_dict(request: Request, req: SynonymDictionaryCreateReq, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/synonym/{synonym_first_word}")
async def update_synonym_dict(request: Request, synonym_first_word: str, req: SynonymDictionaryUpdateReq, current_user=Depends(get_current_user)):
    if req.status is not None and req.status in (DictionaryStatus.APPROVED, DictionaryStatus.REJECTED):
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can approve or reject dictionary entries")
        req.approver = current_user.user_id
    elif current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIEWER cannot modify dictionary entries")
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.update([synonym_first_word], req)

@dictionary_endpoint.delete("/synonym/{synonym_first_word}")
async def delete_synonym_dict(request: Request, synonym_first_word: str, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.delete([synonym_first_word])


# ==========================================
# Correction Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/correction/search")
async def search_correction_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/correction/admin/search")
async def admin_search_correction_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/correction")
async def create_correction_dict(request: Request, req: CorrectionDictionaryCreateReq, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/correction/{incorrect}")
async def update_correction_dict(request: Request, incorrect: str, req: CorrectionDictionaryUpdateReq, current_user=Depends(get_current_user)):
    if req.status is not None and req.status in (DictionaryStatus.APPROVED, DictionaryStatus.REJECTED):
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can approve or reject dictionary entries")
        req.approver = current_user.user_id
    elif current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIEWER cannot modify dictionary entries")
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.update(incorrect, req)

@dictionary_endpoint.delete("/correction/{incorrect}")
async def delete_correction_dict(request: Request, incorrect: str, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.delete(incorrect)


# ==========================================
# Stopword Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/stopword/search")
async def search_stopword_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/stopword/admin/search")
async def admin_search_stopword_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "updated_at", sort_order: int = -1, _=Depends(get_current_user)):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/stopword")
async def create_stopword_dict(request: Request, req: StopwordDictionaryCreateReq, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/stopword/{word}")
async def update_stopword_dict(request: Request, word: str, req: StopwordDictionaryUpdateReq, current_user=Depends(get_current_user)):
    if req.status is not None and req.status in (DictionaryStatus.APPROVED, DictionaryStatus.REJECTED):
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can approve or reject dictionary entries")
        req.approver = current_user.user_id
    elif current_user.role == UserRole.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIEWER cannot modify dictionary entries")
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.update(word, req)

@dictionary_endpoint.delete("/stopword/{word}")
async def delete_stopword_dict(request: Request, word: str, _=Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.delete(word)


# ==========================================
# Deploy & Validate Endpoints (ADMIN ONLY)
# ==========================================
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import get_elasticsearch_client
from src.python.elasticsearch.application.services.api.dictionary_deploy_service import DictionaryDeployService
from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes

@dictionary_endpoint.post("/validate", response_model=CommonRes)
async def validate_dictionaries(request: Request, _=Depends(require_role(UserRole.ADMIN))):
    db = get_mongodb_database(request.app)
    es_client = get_elasticsearch_client(request.app)
    svc = DictionaryDeployService(db, es_client)
    res = await svc.validate_dictionaries()
    return CommonRes(data=res)

@dictionary_endpoint.post("/publish", response_model=CommonRes)
async def publish_dictionaries(request: Request, _=Depends(require_role(UserRole.ADMIN))):
    db = get_mongodb_database(request.app)
    es_client = get_elasticsearch_client(request.app)
    svc = DictionaryDeployService(db, es_client)
    res = await svc.publish_dictionaries()
    return CommonRes(data=res)


import json
from fastapi.responses import StreamingResponse
from src.python.elasticsearch.application.endpoints.auth_endpoint import require_admin_sse

@dictionary_endpoint.get("/validate/stream")
async def stream_validate_dictionaries(
    request: Request,
    current_user=Depends(require_admin_sse)
):
    db = get_mongodb_database(request.app)
    es_client = get_elasticsearch_client(request.app)
    svc = DictionaryDeployService(db, es_client)

    async def event_generator():
        try:
            async for step in svc.validate_dictionaries_generator():
                yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Error in validation stream")
            err_msg = str(e.detail) if hasattr(e, "detail") else str(e)
            yield f"data: {json.dumps({'step': 'ERROR', 'message': err_msg, 'status': 'FAILED'}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@dictionary_endpoint.get("/publish/stream")
async def stream_publish_dictionaries(
    request: Request,
    current_user=Depends(require_admin_sse)
):
    db = get_mongodb_database(request.app)
    es_client = get_elasticsearch_client(request.app)
    svc = DictionaryDeployService(db, es_client)

    async def event_generator():
        try:
            async for step in svc.publish_dictionaries_generator():
                yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Error in publishing stream")
            err_msg = str(e.detail) if hasattr(e, "detail") else str(e)
            yield f"data: {json.dumps({'step': 'ERROR', 'message': err_msg, 'status': 'FAILED'}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
