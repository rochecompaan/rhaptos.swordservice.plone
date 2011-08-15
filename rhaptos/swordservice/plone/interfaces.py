from zope.interface import Interface

class ISWORDContentUploadAdapter(Interface):
    """ Marker interface for adapters that adapt content for sword upload
        functionality. """

class ISWORDRetrieveContentAdapter(Interface):
    """ Marker interface for adapters that adapt content for sword download
        functionality. """

class ISWORDContentAdapter(Interface):
    """ Marker interface for adapters that provide more information about
        the adapted context. """

class ISWORDServiceDocument(Interface):
    """ Marker interface for content that can be adapted to show a service
        document. """

class ISWORDDepositReceipt(Interface):
    """ Marker interface for content that can be adapted to show an edit
        document. """
