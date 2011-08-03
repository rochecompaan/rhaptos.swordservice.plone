from zope.interface import Interface

class ISWORDContentUploadAdapter(Interface):
    """ Marker interface for adapters that adapt content for sword upload
        functionality. """

class ISWORDServiceDocument(Interface):
    """ Marker interface for content that can be adapted to show a service
        document. """

class ISWORDDepositReceipt(Interface):
    """ Marker interface for contant that can be adapted to show an edit
        document. """
