from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import DictionaryBaseEntity

class CorrectionDictionaryEntity(DictionaryBaseEntity):
    incorrect: str
    corrected: str
