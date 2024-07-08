from enum import Enum

class TaskState(Enum):
    RUNNING = 1
    CLOSED = 2

class DataType(Enum):
    STATERESPONSE = 1
    ERROR = 2 
    MATCHDATA = 3
    IMPORTRUNNING = 4