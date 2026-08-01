# FlowOS Shared Errors — kodovi grešaka i ApiErrorResponse
#
# ApiErrorResponse je standardni format za sve API greške:
# { "code": "ERROR_CODE", "message": "...", "details": {}, "correlation_id": "uuid" }
# Interni traceback se ne vraća GUI-ju.
