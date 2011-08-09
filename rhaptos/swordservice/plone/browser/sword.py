import sys
import traceback
import zipfile
from cStringIO import StringIO
import transaction

from zope.interface import Interface, implements
from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryAdapter, queryUtility
from Acquisition import aq_inner, aq_base
from zExceptions import Unauthorized, MethodNotAllowed, NotFound
from webdav.NullResource import NullResource

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish

from rhaptos.atompub.plone.browser.atompub import PloneFolderAtomPubAdapter

from rhaptos.swordservice.plone.interfaces import ISWORDContentUploadAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDContentAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDDepositReceipt

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
        def _abort_and_show(status):
            transaction.abort()
            formatted_tb = traceback.format_exc()
            self.request.response.setStatus(status)
            return self.errordocument(error=sys.exc_info()[1], 
                traceback=formatted_tb)
        try:
            value = func(*args, **kwargs)
        except MethodNotAllowed:
            return _abort_and_show(405)
        except Unauthorized:
            return _abort_and_show(401)
        except:
            return _abort_and_show(400)
        return value
    return wrapper


class SWORDService(BrowserView):

    implements(ISWORDService, IPublishTraverse)

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
        return ob.unrestrictedTraverse('sword/edit')(upload=True)

    def __bobo_traverse__(self, request, name):
        """ Implement custom traversal for ISWORDService to allow the use
            of "sword" as a namespace in our path and use the sub path to
            determine the resource we want or action required.

            Basically this gives us nice RESTful URLs eg:

                <Plone Site>/sword/servicedocument
                <Folder>/sword
        """
        ifaces = {
            'servicedocument': ISWORDServiceDocument,
            'edit': ISWORDDepositReceipt
        }
        iface = ifaces.get(name, None)
        if iface is not None:
            return getMultiAdapter((self.context, self.request), iface)()
        return getattr(self, name)

class ServiceDocument(BrowserView):
    """ Adapts a context and renders a service document for it.
    """
    implements(ISWORDServiceDocument)


    def collections(self):
        """Return all folders we have access to as collection targets"""
        pc = getToolByName(self.context, "portal_catalog")
        return pc(portal_type='Folder', allowedRolesAndUsers=['contributor'])

    def portal_title(self):
        """ Return the portal title. """
        return getToolByName(self.context, 'portal_url').getPortalObject().Title()


    def getPhysicalPath(self):
        """ The publisher calls this while recording metadata. More
            specifically, the page template's getPhysicalPath method is called
            by the publisher, and it calls us. """
        return self.context.getPhysicalPath() + (self.__name__,)


class DepositReceipt(BrowserView):
    """ Adapts a context and renders an edit document for it. This should
        only be possible for uploaded content. This class is therefore bound
        to ATFile (for the default plone installation) in zcml. """
    implements(ISWORDDepositReceipt)


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

    def getPhysicalPath(self):
        """ The publisher calls this while recording metadata. More
            specifically, the page template's getPhysicalPath method is called
            by the publisher, and it calls us. """
        return self.context.getPhysicalPath() + (self.__name__,)


class PloneFolderSwordAdapter(PloneFolderAtomPubAdapter):
    """ Adapts a context to an ISWORDContentAdapter. An ISWORDContentAdapter
        contains the functionality to actually create the content. Write
        your own if you don't want the default behaviour, which is very
        webdav like, it just creates a file corresponding to whatever you
        uploaded. 
        
        This one needs to handle multipart requests too.
    """
    adapts(IFolderish, IHTTPRequest)
