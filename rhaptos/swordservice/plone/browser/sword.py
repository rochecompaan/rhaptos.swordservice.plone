import zipfile
from cStringIO import StringIO

from zope.interface import Interface, implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter

from ZPublisher.BaseRequest import DefaultPublishTraverse
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName

class ISWORDService(Interface):
    """ Marker interface for SWORD service """

class SWORDService(BrowserView):

    implements(ISWORDService)

    servicedocument = ViewPageTemplateFile('servicedocument.pt')

    def __call__(self):
        if self.request.getHeader('content-type') == 'application/zip':
            bodyfile = StringIO(self.request.get('BODY'))
            zf = zipfile.ZipFile(bodyfile)
            
            for filepath in zf.namelist():
                fileobj = zf.read(filepath)

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

