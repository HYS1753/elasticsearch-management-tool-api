from pydantic import BaseModel
from typing import List, Optional
from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus

class DictionaryBaseCreateReq(BaseModel):
    status: DictionaryStatus = DictionaryStatus.DRAFT
    comment: str
    author: str

class DictionaryBaseUpdateReq(BaseModel):
    status: Optional[DictionaryStatus] = None
    comment: Optional[str] = None
    approver: Optional[str] = None

# User Dictionary
class UserDictionaryCreateReq(DictionaryBaseCreateReq):
    word: str

class UserDictionaryUpdateReq(DictionaryBaseUpdateReq):
    pass

# Decompound Dictionary
class DecompoundDictionaryCreateReq(DictionaryBaseCreateReq):
    compound_word: str
    components: List[str]

class DecompoundDictionaryUpdateReq(DictionaryBaseUpdateReq):
    components: Optional[List[str]] = None

# Synonym Dictionary
class SynonymDictionaryCreateReq(DictionaryBaseCreateReq):
    synonyms: List[str]

class SynonymDictionaryUpdateReq(DictionaryBaseUpdateReq):
    synonyms: Optional[List[str]] = None

# Correction Dictionary
class CorrectionDictionaryCreateReq(DictionaryBaseCreateReq):
    incorrect: str
    corrected: List[str]
    
class CorrectionDictionaryUpdateReq(DictionaryBaseUpdateReq):
    corrected: Optional[List[str]] = None

# Stopword Dictionary
class StopwordDictionaryCreateReq(DictionaryBaseCreateReq):
    word: str

class StopwordDictionaryUpdateReq(DictionaryBaseUpdateReq):
    pass
