import sys
import traceback
import zipfile
from cStringIO import StringIO

from zope.interface import Interface, implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryUtility
from zope.contenttype import guess_content_type
from Acquisition import aq_inner
from ZPublisher.BaseRequest import DefaultPublishTraverse
from zExceptions import Unauthorized, MethodNotAllowed
from webdav.NullResource import NullResource
from plone.i18n.normalizer.interfaces import IIDNormalizer

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish

from rhaptos.swordservice.plone.interfaces import ISWORDContentUploadAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDDepositReceipt

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
        if self.request.method != 'POST':
            raise MethodNotAllowed("Method %s not supported" % self.request.method)

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
    

class SWORDTraversel(DefaultPublishTraverse):
    """ Implement custom traversal for ISWORDService to allow the use
        of "sword" as a namespace in our path and use the sub path to
        determine the resource we want or action required.

        Basically this gives us nice RESTful URLs eg:

            <Plone Site>/sword/service-document
            <Folder>/sword
    """

    adapts(ISWORDService, IHTTPRequest)

    def publishTraverse(self, request, name):
        if name == 'service-document':
            # .context is the @@sword view
            # .context.context is the context of the @@sword view
            # We want an adapter for .context.context.
            return ISWORDServiceDocument(self.context.context)(self.context)
        elif name == 'edit':
            return ISWORDDepositReceipt(self.context.context)(self.context)
        else:
            return super(SWORDTraversel, self).publishTraverse(request, name)

class ServiceDocumentAdapter(object):
    """ Adapts a context and renders a service document for it. The real
        magic is in the zcml, where this class is set as the factory that
        adapts folderish items into sword collections. """
    def __init__(self, context):
        self.context = context

    def __call__(self, swordview):
        return swordview.servicedocument

class EditDocumentAdapter(object):
    """ Adapts a context and renders an edit document for it. This should
        only be possible for uploaded content. This class is therefore bound
        to ATFile (for the default plone installation) in zcml. """
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

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        """ Calling the adapter does the actual work of importing the content.
        """
        content_type = self.request.getHeader('content-type')
        disposition = self.request.getHeader('content-disposition')
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
            safe_filename = queryUtility(IIDNormalizer).normalize(filename)

        NullResource(self.context, safe_filename, self.request).__of__(
            self.context).PUT(self.request, self.request.response)

        # Look it up and finish up, then return it.
        ob = self.context._getOb(safe_filename)
        ob.PUT(self.request, self.request.response)
        ob.setTitle(filename)
        ob.reindexObject(idxs='Title')
        return ob
