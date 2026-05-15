from fastapi import APIRouter, Depends, Request
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

dictionary_endpoint = APIRouter()

# ==========================================
# User Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/user/search")
async def search_user_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/user/admin/search")
async def admin_search_user_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/user")
async def create_user_dict(request: Request, req: UserDictionaryCreateReq):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/user/{word}")
async def update_user_dict(request: Request, word: str, req: UserDictionaryUpdateReq):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.update(word, req)

@dictionary_endpoint.delete("/user/{word}")
async def delete_user_dict(request: Request, word: str):
    db = get_mongodb_database(request.app)
    svc = UserDictionaryService(db)
    return await svc.delete(word)


# ==========================================
# Decompound Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/decompound/search")
async def search_decompound_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/decompound/admin/search")
async def admin_search_decompound_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/decompound")
async def create_decompound_dict(request: Request, req: DecompoundDictionaryCreateReq):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/decompound/{compound_word}")
async def update_decompound_dict(request: Request, compound_word: str, req: DecompoundDictionaryUpdateReq):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.update(compound_word, req)

@dictionary_endpoint.delete("/decompound/{compound_word}")
async def delete_decompound_dict(request: Request, compound_word: str):
    db = get_mongodb_database(request.app)
    svc = DecompoundDictionaryService(db)
    return await svc.delete(compound_word)


# ==========================================
# Synonym Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/synonym/search")
async def search_synonym_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/synonym/admin/search")
async def admin_search_synonym_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/synonym")
async def create_synonym_dict(request: Request, req: SynonymDictionaryCreateReq):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/synonym/{synonym_first_word}")
async def update_synonym_dict(request: Request, synonym_first_word: str, req: SynonymDictionaryUpdateReq):
    # 단일 문자열 키를 list로 캐스팅하여 저장소 키로 사용 (구현에 따라 수정 필요)
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.update([synonym_first_word], req)

@dictionary_endpoint.delete("/synonym/{synonym_first_word}")
async def delete_synonym_dict(request: Request, synonym_first_word: str):
    db = get_mongodb_database(request.app)
    svc = SynonymDictionaryService(db)
    return await svc.delete([synonym_first_word])


# ==========================================
# Correction Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/correction/search")
async def search_correction_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/correction/admin/search")
async def admin_search_correction_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/correction")
async def create_correction_dict(request: Request, req: CorrectionDictionaryCreateReq):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/correction/{incorrect}")
async def update_correction_dict(request: Request, incorrect: str, req: CorrectionDictionaryUpdateReq):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.update(incorrect, req)

@dictionary_endpoint.delete("/correction/{incorrect}")
async def delete_correction_dict(request: Request, incorrect: str):
    db = get_mongodb_database(request.app)
    svc = CorrectionDictionaryService(db)
    return await svc.delete(incorrect)


# ==========================================
# Stopword Dictionary Endpoints
# ==========================================
@dictionary_endpoint.get("/stopword/search")
async def search_stopword_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    total, items = await svc.get_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.get("/stopword/admin/search")
async def admin_search_stopword_dict(request: Request, keyword: str = "", skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    total, items = await svc.get_admin_list(keyword, skip, limit, sort_by, sort_order)
    return DictionaryListRes(total_count=total, items=items)

@dictionary_endpoint.post("/stopword")
async def create_stopword_dict(request: Request, req: StopwordDictionaryCreateReq):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.create(req)

@dictionary_endpoint.put("/stopword/{word}")
async def update_stopword_dict(request: Request, word: str, req: StopwordDictionaryUpdateReq):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.update(word, req)

@dictionary_endpoint.delete("/stopword/{word}")
async def delete_stopword_dict(request: Request, word: str):
    db = get_mongodb_database(request.app)
    svc = StopwordDictionaryService(db)
    return await svc.delete(word)
