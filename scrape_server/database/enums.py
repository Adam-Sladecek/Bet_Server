from enum import Enum

class TaskState(Enum):
    RUNNING = 1
    CLOSED = 2

class DataType(Enum):
    STATERESPONSE = 1
    ERROR = 2 
    MATCHDATA = 3
    IMPORTRUNNING = 4

class Command(Enum):
    REFRESH = 1
    IMPORT = 2 

class Movement(Enum):
    NONE = 0
    UP = 1    
    DOWN = 2     
