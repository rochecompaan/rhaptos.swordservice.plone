from rhaptos.atompub.plone.exceptions import PreconditionFailed
from rhaptos.atompub.plone.exceptions import UnsupportedMediaType

class SwordException(Exception):
    @property
    def status(self):
        return self._status

    @property
    def href(self):
        return self._href

    @property
    def title(self):
        return self._title

class ContentNotAcceptable(SwordException):
    """ Content is not acceptable. """
    _status = 406
    _title = "Content Not Acceptable"
    _href = "http://purl.org/net/sword/error/ErrorContent"

class ContentUnsupported(SwordException):
    """ Content is not supported. """
    _status = 415
    _title = "Content Not Supported"
    _href = "http://purl.org/net/sword/error/ErrorContent"

class MaxUploadSizeExceeded(SwordException):
    """ Uploaded document is too large. """
    _status = 413
    _title = "Maximum Upload Size Exceeded"
    _href = "http://purl.org/net/sword/error/MaxUploadSizeExceeded"

class ErrorChecksumMismath(SwordException):
    """ Checksum does not match. """
    _status = 412
    _title = "Checksum Mismatch"
    _href = "http://purl.org/net/sword/error/ErrorChecksumMismatch"

class BadRequest(SwordException):
    """ Similar to the one in zExceptions, but specific to POST requests
        that are not fully comprehensible. """
    _status = 400
    _title = "Bad Request"
    _href = "http://purl.org/net/sword/error/ErrorBadRequest"

class MediationNotAllowed(SwordException):
    """ Mediation is not allowed. """
    _status = 412
    _title = "Mediation Not Allowed"
    _href = "http://purl.org/net/sword/error/MediationNotAllowed"
