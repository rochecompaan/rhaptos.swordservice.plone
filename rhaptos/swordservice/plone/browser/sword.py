import sys
import traceback
import zipfile
from cStringIO import StringIO
from DateTime import DateTime
from email import message_from_file
from xml.dom.minidom import parse
from base64 import encodestring as b64encode
import transaction

from zope.interface import implements
from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryAdapter, queryUtility

from AccessControl import ClassSecurityInfo
from Acquisition import aq_inner
from zExceptions import Unauthorized, MethodNotAllowed, NotFound
from webdav.NullResource import NullResource

from Products.CMFCore.permissions import View
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish
from Products.ATContentTypes.interface.file import IATFile
from Products.Archetypes.Marshall import formatRFC822Headers

from rhaptos.atompub.plone.browser.atompub import PloneFolderAtomPubAdapter
from rhaptos.atompub.plone.browser.atompub import METADATA_MAPPING

from rhaptos.swordservice.plone.interfaces import ISWORDContentUploadAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDDepositReceipt
from rhaptos.swordservice.plone.interfaces import ISWORDRetrieveContentAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDService
from rhaptos.swordservice.plone.interfaces import ISWORDStatement

try:
    from zope.contenttype import guess_content_type
except ImportError:
    from zope.app.content_types import guess_content_type


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
        if method == 'POST':
            return self._handlePost()
        elif method == 'GET':
            return self._handleGet()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)

    def _handlePost(self):
        # Adapt and call
        adapter = getMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDContentUploadAdapter)
        ob = adapter()

        # We must return status 201, and Location must be set to the edit IRI
        self.request.response.setHeader('Location', '%s/sword/edit' % ob.absolute_url())
        self.request.response.setStatus(201)

        # Return the optional deposit receipt
        ob = ob.__of__(self.context)
        view = ob.unrestrictedTraverse('sword/edit')
        return view(upload=True)

    def _handleGet(self):
        """ Get files as sword packages """
        adapter = getMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDRetrieveContentAdapter)
        return adapter()

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
            adapter = getMultiAdapter(
                (aq_inner(self.context), self.request), iface)
            return adapter.__of__(self.context)
        return getattr(self, name)


class ServiceDocument(BrowserView):
    """ Adapts a context and renders a service document for it. The real
        magic is in the zcml, where this class is set as the factory that
        adapts folderish items into sword collections. """
    __name__ = "servicedocument"
    implements(ISWORDServiceDocument)

    servicedocument = ViewPageTemplateFile('servicedocument.pt')

    def __call__(self):
        return self.servicedocument()

    def collections(self):
        """Return all folders we have access to as collection targets"""
        pc = getToolByName(self.context, "portal_catalog")
        return pc(portal_type='Folder', allowedRolesAndUsers=['contributor'])

    def portal_title(self):
        """ Return the portal title. """
        return getToolByName(self.context, 'portal_url').getPortalObject().Title()


class DepositReceipt(BrowserView):
    """ Adapts a context and renders an edit document for it. This should
        only be possible for uploaded content. This class is therefore bound
        to ATFile (for the default plone installation) in zcml. """
    __name__ = "edit"
    implements(ISWORDDepositReceipt)

    depositreceipt = ViewPageTemplateFile('depositreceipt.pt')

    def __call__(self, upload=False):
        return self.depositreceipt(upload=upload)

class PloneFolderSwordAdapter(PloneFolderAtomPubAdapter):
    """ Adapts a context to an ISWORDContentAdapter. An ISWORDContentAdapter
        contains the functionality to actually create the content. Write
        your own if you don't want the default behaviour, which is very
        webdav like, it just creates a file corresponding to whatever you
        uploaded. 
        
        This one needs to handle multipart requests too.
    """
    adapts(IFolderish, IHTTPRequest)

    def createObject(self, context, name, content_type, request):
        """ If the content_type is multipart/related, then this is
            a multipart deposit which is in the sword domain. It is
            therefore implemented in this package. """

        if content_type.startswith('multipart/'):
            request.stdin.seek(0)
            message = message_from_file(request.stdin)

            # A multipart post has two parts, the first is the atom part, the
            # second is a zipfile. The spec requires that these be named atom
            # and payload. So here goes...
            atom, payload = message.get_payload()

            # We'll use the atom part to obtain the right content type
            registry = getToolByName(context, 'content_type_registry')
            typeObjectName = registry.findTypeName(name, atom.get_content_type(), atom)
            context.invokeFactory(typeObjectName, name)
            return context._getOb(name)
        else:
            return super(PloneFolderSwordAdapter, self).createObject(
                context, name, content_type, request)

    def _updateRequest(self, request, content_type):
        """ Similar to the same method in atompub. We change the request so
            that the metadata is in the right place, then append the content.
            This is only called for multipart posts. """

        # This seems to be the safest place to get hold of the actual message
        # body.
        request.stdin.seek(0)
        message = message_from_file(request.stdin)
        atom, payload = message.get_payload()

        # Call get_payload with decode=True, so it can handle the transfer
        # encoding for us, if any.
        dom = parse(StringIO(atom.get_payload(decode=True)))

        # Get the payload
        content = payload.get_payload(decode=True)

        # Assemble a new request
        title = self.getValueFromDOM('title', dom)
        request['Title'] = title
        headers = self.getHeaders(dom, METADATA_MAPPING)
        headers.append(('Content-Transfer-Encoding', 'base64'))
        header = formatRFC822Headers(headers)

        # make sure content is not None
        data = '%s\n\n%s' % (header, b64encode(content))
        request['Content-Length'] = len(data)
        request['BODYFILE'] = StringIO(data)
        return request

    def updateObject(self, obj, filename, request, response, content_type):
        """ If the content_type is multipart/related, then this is
            a multipart sword deposit. This complements the above. """
        if content_type.startswith('multipart/'):
            request = self._updateRequest(request, content_type)
            obj.PUT(request, response)
            obj.setTitle(request.get('Title', filename))
            obj.reindexObject(idxs='Title')
            return obj
        else:
            return super(PloneFolderSwordAdapter, self).updateObject(
                obj, filename, request, response, content_type)


class RetrieveContent(object):
    """
    """
    adapts(IATFile, IHTTPRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request


    def __call__(self):
        data = self.context.getFile().data
        response = self.request.response
        filename = self.context.Title()
        response.setHeader(
                'Content-disposition', 'attachment; filename=%s' %filename)
        response.setHeader('Content-type', 'application/zip')
        response.setHeader("Content-Length", len(data))
        return data


class SWORDStatement(BrowserView):

    implements(ISWORDStatement)


    def treatment(self):
        return 'Stored'
    

    def state_description(self):
        obj = self.context.aq_inner
        state = self.workflow_state(obj)
        return "The item state is:%s" %state

    
    def workflow_state(self, obj):
        state = 'private'
        wft = getToolByName(obj, 'portal_workflow')
        if wft.getChainFor(obj):
            state = wft.getInfoFor(obj, 'review_state')
        return state

    
    def packaging(self):
        """ This can be elaborated to return the actual packacking.
            At the moment we put simple xhtml in the file.
        """
        return 'application/xhtml+xml'
