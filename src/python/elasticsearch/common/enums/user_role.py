from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    WRITER = "WRITER"
    VIEWER = "VIEWER"
