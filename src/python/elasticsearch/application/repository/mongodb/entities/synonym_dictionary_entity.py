from typing import List
from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import DictionaryBaseEntity

class SynonymDictionaryEntity(DictionaryBaseEntity):
    synonyms: List[str]
