import sys
import zipfile
from cStringIO import StringIO

from zope.interface import Interface, implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryUtility
from zope.contenttype import guess_content_type
from Acquisition import aq_inner
from ZPublisher.BaseRequest import DefaultPublishTraverse
from zExceptions import Unauthorized
from webdav.NullResource import NullResource
from plone.i18n.normalizer.interfaces import IIDNormalizer

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish

from rhaptos.swordservice.plone.interfaces import ISWORDContentAdapter

class ISWORDService(Interface):
    """ Marker interface for SWORD service """

class SWORDService(BrowserView):

    implements(ISWORDService)

    servicedocument = ViewPageTemplateFile('servicedocument.pt')
    editdocument = ViewPageTemplateFile('editdocument.pt')

    def __call__(self):
        assert self.request.method == 'POST',"Method %s not supported" % (
            self.request.method)

        # Adapt and call
        adapter = getMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDContentAdapter)
        ob = adapter()

        # We must return status 201, and Location must be set to the edit IRI
        self.request.response.setHeader('Location', '%s/sword/edit' % ob.absolute_url())
        self.request.response.setStatus(201)

        # Return the optional deposit receipt
        view = ob.restrictedTraverse('sword')
        return ViewPageTemplateFile('editdocument.pt')(view, upload=True)


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
            return self.context.servicedocument
        elif name == 'edit':
            return self.context.editdocument
        else:
            return super(SWORDTraversel, self).publishTraverse(request, name)

class PloneFolderSwordAdapter(object):
    adapts(IFolderish, IHTTPRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
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
