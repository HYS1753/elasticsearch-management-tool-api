from enum import Enum

class DictionaryStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
