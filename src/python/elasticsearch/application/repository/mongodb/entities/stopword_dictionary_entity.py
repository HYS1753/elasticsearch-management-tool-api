from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import DictionaryBaseEntity

class StopwordDictionaryEntity(DictionaryBaseEntity):
    word: str
