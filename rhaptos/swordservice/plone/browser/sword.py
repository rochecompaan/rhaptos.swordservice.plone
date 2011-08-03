import sys
import traceback
import zipfile
from cStringIO import StringIO

from zope.interface import Interface, implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryAdapter, queryUtility
from Acquisition import aq_inner
from zExceptions import Unauthorized, MethodNotAllowed
from webdav.NullResource import NullResource

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish

from rhaptos.swordservice.plone.interfaces import ISWORDContentUploadAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDContentAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDDepositReceipt

try:
    from plone.i18n.normalizer.interfaces import IIDNormalizer
    normalize_filename = lambda c,f: queryUtility(IIDNormalizer).normalize(f)
except ImportError:
    normalize_filename = lambda c,f: getToolByName(c,
        'plone_utils').normalizeString(f)

try:
    from ZPublisher.BaseRequest import DefaultPublishTraverse
except ImportError:
    # Old plone, see below for patch
    DefaultPublishTraverse = object

try:
    from zope.contenttype import guess_content_type
except ImportError:
    from zope.app.content_types import guess_content_type

class ISWORDService(Interface):
    """ Marker interface for SWORD service """

def show_error_document(func):
    """ This is a decorator to be applied on the methods in the SwordService
        class. It checks for exceptions, and renders an error document
        with the stack trace embedded in the correct markup. """
    def wrapper(*args, **kwargs):
        self = args[0]
        def _show(status):
            formatted_tb = traceback.format_exc()
            self.request.response.setStatus(status)
            return self.errordocument(error=sys.exc_info()[1], 
                traceback=formatted_tb)
        try:
            value = func(*args, **kwargs)
        except MethodNotAllowed:
            return _show(405)
        except Unauthorized:
            return _show(401)
        except:
            return _show(400)
        return value
    return wrapper

class SWORDService(BrowserView):

    implements(ISWORDService)

    servicedocument = ViewPageTemplateFile('servicedocument.pt')
    depositreceipt = ViewPageTemplateFile('depositreceipt.pt')
    errordocument = ViewPageTemplateFile('errordocument.pt')

    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method != 'POST':
            raise MethodNotAllowed("Method %s not supported" % method)

        # Adapt and call
        adapter = getMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDContentUploadAdapter)
        ob = adapter()

        # We must return status 201, and Location must be set to the edit IRI
        self.request.response.setHeader('Location', '%s/sword/edit' % ob.absolute_url())
        self.request.response.setStatus(201)

        # Return the optional deposit receipt
        view = ob.restrictedTraverse('sword')
        return ViewPageTemplateFile('depositreceipt.pt')(view, upload=True)


    def collections(self):
        """Return all folders we have access to as collection targets"""
        pc = getToolByName(self.context, "portal_catalog")
        return pc(portal_type='Folder', allowedRolesAndUsers=['contributor'])

    def portal_title(self):
        try:
            return self.context.restrictedTraverse('@@plone_portal_state').portal_title()
        except AttributeError:
            return getToolByName(self.context, 'portal_url').getPortalObject().Title()

    def information(self, ob=None):
        """ Return additional or overriding information about our context. By
            default there is no extra information, but if you register an
            adapter for your context that provides us with a
            ISWORDContentAdapter, you can generate or override that extra
            information by implementing a method named information that
            returns a dictionary.  Valid keys are author and updated. """
        if ob is None:
            ob = self.context
        adapter = queryAdapter(ob, ISWORDContentAdapter)
        if adapter is not None:
            return adapter.information()
        return {}

class SWORDTraversel(DefaultPublishTraverse):
    """ Implement custom traversal for ISWORDService to allow the use
        of "sword" as a namespace in our path and use the sub path to
        determine the resource we want or action required.

        Basically this gives us nice RESTful URLs eg:

            <Plone Site>/sword/service-document
            <Folder>/sword
    """

    adapts(ISWORDService, IHTTPRequest)

    adapters = {
        'service-document': ISWORDServiceDocument,
        'edit': ISWORDDepositReceipt
    }

    def publishTraverse(self, request, name):
        adapter = self.adapters.get(name, None)
        if adapter is not None:
            # .context is the @@sword view
            # .context.context is the context of the @@sword view
            # We want an adapter for .context.context.
            return adapter(self.context.context)(self.context)
        else:
            return super(SWORDTraversel, self).publishTraverse(request, name)

class ServiceDocumentAdapter(object):
    """ Adapts a context and renders a service document for it. The real
        magic is in the zcml, where this class is set as the factory that
        adapts folderish items into sword collections. """

    implements(ISWORDServiceDocument)

    def __init__(self, context):
        self.context = context

    def __call__(self, swordview):
        return swordview.servicedocument

class DepositReceiptAdapter(object):
    """ Adapts a context and renders an edit document for it. This should
        only be possible for uploaded content. This class is therefore bound
        to ATFile (for the default plone installation) in zcml. """

    implements(ISWORDDepositReceipt)

    def __init__(self, context):
        self.context = context

    def __call__(self, swordview):
        return swordview.depositreceipt

class PloneFolderSwordAdapter(object):
    """ Adapts a context to an ISWORDContentUploadAdapter. An
        ISWORDContentUploadAdapter contains the functionality to actually
        create the content. It returns the created object. Write your own if
        you don't want the default behaviour, which is very webdav like, it
        just creates a file corresponding to whatever you uploaded. """
    adapts(IFolderish, IHTTPRequest)

    def getHeader(self, name, default=None):
        return getattr(self.request, 'getHeader', self.request.get_header)(
            name, default)
        
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        """ Calling the adapter does the actual work of importing the content.
        """
        content_type = self.getHeader('content-type')
        disposition = self.getHeader('content-disposition')
        filename = None
        if disposition is not None:
            try:
                filename = [x for x in disposition.split(';') \
                    if x.strip().startswith('filename=')][0][10:]
            except IndexError:
                pass

        # If no filename, make one up, otherwise just make sure its http safe
        if filename is None:
            safe_filename = self.context.generateUniqueId(
                type_name=content_type.replace('/', '_'))
        else:
            safe_filename = normalize_filename(self.context, filename)

        NullResource(self.context, safe_filename, self.request).__of__(
            self.context).PUT(self.request, self.request.response)

        # Look it up and finish up, then return it.
        ob = self.context._getOb(safe_filename)
        ob.PUT(self.request, self.request.response)
        ob.setTitle(filename)
        ob.reindexObject(idxs='Title')
        return ob

# This happens if we don't have DefaultPublishTraverse, ie, on old plones
if DefaultPublishTraverse is object:
    @show_error_document
    def _sword___bobo_traverse__(self, REQUEST, name):
        adapter = SWORDTraversel.adapters.get(name, None)
        if adapter is not None:
            return adapter(self.context.context)(self.context)
        raise AttributeError

    def _sword_getPhysicalPath(self):
        return self.context.getPhysicalPath() + (self.__name__,)

    SWORDService.__bobo_traverse__ = _sword___bobo_traverse__
    SWORDService.getPhysicalPath = _sword_getPhysicalPath
