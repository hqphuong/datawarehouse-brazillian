class StdResponse:
    def __init__(self, success: bool, message):
        self.success = success
        self.message = message
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message
        }

class StdError:
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
    def to_dict(self) -> dict:
        return {
            "success": False,
            "error_code": self.code,
            "message": self.message
        }