from zope.interface import Interface

class ISWORDContentUploadAdapter(Interface):
    """ Marker interface for adapters that adapt content for sword upload
        functionality. """

class ISWORDContentAdapter(Interface):
    """ Marker interface for adapters that provide more information about
        the adapted context. """

class ISWORDServiceDocument(Interface):
    """ Marker interface for content that can be adapted to show a service
        document. """

class ISWORDEditIRI(Interface):
    """ Marker interface for content that can be sword resources, which means
        they hand you a deposit receipt on GET, and provide PUT and POST
        functionality to otherwise modify the content. """

class ISWORDEMIRI(Interface):
    """ Marker interface for adapters that adapt content to something that
        implements PUT and DELETE for media. """

class ISWORDService(Interface):
    """ Marker interface for SWORD service """

class ISWORDStatement(Interface):
    """ Marker interface for SWORD service """

class ISWORDStatementAtomAdapter(Interface):
    """ Marker interface for Atom feed adapter.
    """

class ISWORDListCollection(Interface):
    """ Marker interface for Atom adapters that lists collection contents.
    """
