from rhaptos.atompub.plone.exceptions import PreconditionFailed
from rhaptos.atompub.plone.exceptions import UnsupportedMediaType

class SwordException(Exception):
    """ Base class for Sword Exceptions. Each of these has a status, and an
        href with the url that corresponds to the error. It also has a title
        and the docstring serves as the summary. Whatever value is raised
        with the exception is used as the value for the
        <sword:verboseDescription> tag. """
    @property
    def status(self):
        return self._status

    @property
    def href(self):
        return self._href

    @property
    def title(self):
        return self._title

    @property
    def summary(self):
        return self.__doc__

    @property
    def treatment(self):
        if len(self.args)>0:
            return self.args[0]

    @property
    def verbose(self):
        if len(self.args)>1:
            return self.args[1]

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

class ErrorChecksumMismatch(SwordException):
    """ Checksum does not match. """
    _status = 412
    _title = "Checksum Mismatch"
    _href = "http://purl.org/net/sword/error/ErrorChecksumMismatch"

class BadRequest(SwordException):
    """Bad Request"""
    # Similar to the one in zExceptions, but specific to POST requests
    # that are not fully comprehensible.
    _status = 400
    _title = "Bad Request"
    _href = "http://purl.org/net/sword/error/ErrorBadRequest"

class MediationNotAllowed(SwordException):
    """ Mediation is not allowed. """
    _status = 412
    _title = "Mediation Not Allowed"
    _href = "http://purl.org/net/sword/error/MediationNotAllowed"
