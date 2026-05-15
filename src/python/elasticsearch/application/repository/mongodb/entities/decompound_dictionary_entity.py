from typing import List
from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import DictionaryBaseEntity

class DecompoundDictionaryEntity(DictionaryBaseEntity):
    compound_word: str
    components: List[str]
