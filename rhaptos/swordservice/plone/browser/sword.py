import sys
import zipfile
from cStringIO import StringIO

from zope.interface import Interface, implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter
from zope.contenttype import guess_content_type

from Acquisition import aq_inner
from ZPublisher.BaseRequest import DefaultPublishTraverse
from zExceptions import Unauthorized
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName

class ISWORDService(Interface):
    """ Marker interface for SWORD service """

class SWORDService(BrowserView):

    implements(ISWORDService)

    servicedocument = ViewPageTemplateFile('servicedocument.pt')

    def __call__(self):
        assert self.request.method == 'POST',"Method %s not supported" % (
            self.request.method)
        context = aq_inner(self.context)
        content_type = self.request.getHeader('content-type')
        disposition = self.request.getHeader('content-disposition')
        filename = None
        if disposition is not None:
            try:
                filename = [x for x in disposition.split(';') \
                    if x.strip().startswith('filename=')][0][10:]
            except IndexError:
                pass

        body = self.request.get('BODY')
        if content_type is None and not (filename is None and body is None):
            content_type, encoding = guess_content_type(filename, body)

        # If we couldn't guess either, assume its octet-stream
        if content_type is None:
            content_type = "application/octet-stream"

        # If no filename, make one up
        if filename is None:
            filename = context.generateUniqueId(
                type_name=content_type.replace('/', '_'))

        # PUT_factory is implemented by PortalFolder
        factory = getattr(context, 'PUT_factory', None)
        assert factory is not None, "Parent does not implement PUT_factory"

        ob = factory(filename, content_type, body)

        # Persist ob in context
        try:
            context._verifyObjectPaste(ob.__of__(context), 0)
        except CopyError:
             sMsg = 'Unable to create object of class %s in %s: %s' % \
                    (ob.__class__, repr(context), sys.exc_info()[1],)
             raise Unauthorized, sMsg

        context._setObject(filename, ob)
        ob = context._getOb(filename)
        ob.PUT(self.request, self.request.response)
        ob.setTitle(filename)
        ob.reindexObject(idxs='Title')

        self.request.response.setHeader('Location', ob.absolute_url())
        self.request.response.setStatus(201)
        self.request.response.setBody('')
        return None

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
            return self.context.servicedocument()
        else:
            return super(SWORDTraversel, self).publishTraverse(request, name)

