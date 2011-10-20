import sys
import traceback
import zipfile
from cStringIO import StringIO
from DateTime import DateTime
from email import message_from_file
from xml.dom.minidom import parse
from base64 import encodestring as b64encode
import logging
import transaction

from zope.interface import implements
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import adapts, getMultiAdapter, queryMultiAdapter
from OFS.interfaces import IObjectManager

from AccessControl import ClassSecurityInfo
from Acquisition import aq_inner
from zExceptions import Unauthorized, MethodNotAllowed, NotFound
from webdav.NullResource import NullResource

from Products.CMFCore.permissions import View
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.Five.browser.pagetemplatefile import ZopeTwoPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish
from Products.ATContentTypes.interface.file import IATFile
from Products.Archetypes.Marshall import formatRFC822Headers

from rhaptos.atompub.plone.browser.atompub import PloneFolderAtomPubAdapter
from rhaptos.atompub.plone.browser.atompub import getHeader
from rhaptos.atompub.plone.browser.atompub import METADATA_MAPPING
from rhaptos.atompub.plone.exceptions import PreconditionFailed

from rhaptos.swordservice.plone.interfaces import ISWORDContentUploadAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDEditIRI
from rhaptos.swordservice.plone.interfaces import ISWORDEMIRI
from rhaptos.swordservice.plone.interfaces import ISWORDService
from rhaptos.swordservice.plone.interfaces import ISWORDStatement
from rhaptos.swordservice.plone.interfaces import ISWORDStatementAtomAdapter
from rhaptos.swordservice.plone.interfaces import ISWORDListCollection
from rhaptos.swordservice.plone.exceptions import MediationNotAllowed
from rhaptos.swordservice.plone.exceptions import SwordException
from rhaptos.swordservice.plone.exceptions import ContentUnsupported
from rhaptos.swordservice.plone.exceptions import BadRequest

logger = logging.getLogger(__name__)

def show_error_document(func):
    """ This is a decorator to be applied on the methods in the SwordService
        class. It checks for exceptions, and renders an error document
        with the stack trace embedded in the correct markup. """
    def wrapper(*args, **kwargs):
        self = args[0]
        def _abort_and_show(status, **kw):
            transaction.abort()
            self.request.response.setStatus(status)
            view = ViewPageTemplateFile('errordocument.pt')
            if view.__class__.__name__ == 'ZopeTwoPageTemplateFile':
                # Zope 2.9
                return ViewPageTemplateFile('errordocument.pt').__of__(
                    self.context)(**kw)
            else:
                # Everthing else
                return ViewPageTemplateFile('errordocument.pt')(self, **kw)
        try:
            if getHeader(self.request, 'On-Behalf-Of') is not None:
                raise MediationNotAllowed, "Mediation not allowed"
            value = func(*args, **kwargs)
        except MethodNotAllowed, e:
            return _abort_and_show(405, title="Method Not Allowed",
                summary="Method not allowed",
                treatment=str(e),
                href="http://purl.org/net/sword/error/MethodNotAllowed")
        except Unauthorized:
            return _abort_and_show(401, title="Unauthorized")
        except PreconditionFailed, e:
            return _abort_and_show(412, title="Precondition Failed",
                summary="Precondition Failed",
                treatment=str(e))
        except SwordException, e:
            return _abort_and_show(e.status, href=e.href, title=e.title,
                summary=e.summary, treatment=e.treatment, verbose=e.verbose)
        except Exception:
            formatted_tb = traceback.format_exc()
            logger.error(formatted_tb)
            return _abort_and_show(400, title="Bad request",
                summary=sys.exc_info()[1], verbose=formatted_tb)
        return value
    wrapper.__doc__ = func.__doc__
    return wrapper


class SWORDService(BrowserView):

    implements(ISWORDService)
    
    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method == 'POST':
            return self._handlePost()
        elif method == 'GET':
            return self._handleGet()
        elif method == 'PUT':
            return self._handlePut()
        elif method == 'DELETE':
            return self._handleDelete()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)

    def _handlePost(self):
        # First attempt to treat the content as something with an EditIRI.
        # Collections won't have one. We have to do it this way round
        # as our content is often Folderish and is mistaken for collections.
        adapter = queryMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDEditIRI)
        if adapter:
            return adapter._handlePost()

        # If our context does not have an Edit-IRI, treat it as a collection
        adapter = getMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDContentUploadAdapter)
        ob = adapter()

        # Get the Edit-IRI
        ob = ob.__of__(self.context)
        view = getMultiAdapter((ob, self.request), ISWORDEditIRI)

        # Optionally publish
        if getHeader(self.request, 'In-Progress', 'false') == 'false':
            view._handlePublish()

        # We must return status 201, and Location must be set to the edit IRI
        self.request.response.setHeader('Location', '%s/sword' % ob.absolute_url())
        self.request.response.setStatus(201)

        # Return the optional deposit receipt
        return view._handleGet(upload=True)

    def _handleGet(self):
        """ Lookup EditIRI adapter, call it to get a deposit receipt. """
        adapter = queryMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDEditIRI)
        if adapter is None:
            adapter = queryMultiAdapter(
                (self.context, self.request), ISWORDListCollection)
        if adapter is None:
            raise MethodNotAllowed("Method GET is not supported for %s" % \
                                   self.request['PATH_INFO'])
        return adapter._handleGet()

    def _handlePut(self):
        adapter = queryMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDEditIRI)
        if adapter is None:
            raise MethodNotAllowed("Method PUT is not supported in this context")
        return adapter._handlePut()

    def _handleDelete(self):
        adapter = queryMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDEditIRI)
        if adapter is None:
            raise MethodNotAllowed("Method DELETE is not supported in this context")
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
            'editmedia': ISWORDEMIRI,
            'statement.atom': ISWORDStatement,
            'atom': ISWORDStatementAtomAdapter,
        }
        iface = ifaces.get(name, None)
        if iface is not None:
            adapter = queryMultiAdapter(
                (aq_inner(self.context), self.request), iface)
            if adapter is None:
                raise AttributeError, name
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


class EditIRI(object):
    """ Adapts a context and renders an edit document for it. This should
        only be possible for uploaded content. This class is therefore bound
        to ATFile (for the default plone installation) in zcml. """
    implements(ISWORDEditIRI)

    depositreceipt = ViewPageTemplateFile('depositreceipt.pt')

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method == 'POST':
            return self._handlePost()
        elif method == 'GET':
            return self._handleGet()
        elif method == 'PUT':
            return self._handlePut()
        elif method == 'DELETE':
            return self._handleDelete()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)

    def _handleDelete(self):
        """ Delete the module (self.context) completely.
        """
        #FIXME:
        #Refactor this to get the aquisition wrapping correct.
        #Then use module.DELETE(self.request, self.request.response)
        uid_catalog = getToolByName(self.context, 'uid_catalog')
        modules = uid_catalog(UID=self.context.UID())
        if not modules:
            return self.request.response.setStatus(204)
        module = modules[0].getObject()
        container = module.aq_parent
        if not container:
            return self.request.response.setStatus(204)
        container.manage_delObjects(module.id)
        return self.request.response.setStatus(200)

    def _handleGet(self, **kw):
        """ A GET on the Edit-IRI should return the deposit receipt. You
            can override this method in your subclasses, or provide an
            equivalent in your adapters. """
        return self.depositreceipt(**kw)

    def _handlePost(self):
        """ A POST fo the Edit-IRI can do one of two things. You can either add
            more metadata by posting an atom entry, or you can publish the
            module with an empty request and In-Progress set to false.
        """
        context = aq_inner(self.context)
        content_type = getHeader(self.request, 'Content-Type', '')
        if content_type.startswith('application/atom+xml'):
            # Apply more metadata to the item
            parent = context.aq_parent
            adapter = getMultiAdapter(
                (parent, self.request), ISWORDContentUploadAdapter)

            body = self.request.get('BODYFILE')
            body.seek(0)
            adapter.updateMetadata(self.context, parse(body))
        elif content_type:
            # A content type is provided, and its not atom+xml
            raise BadRequest(
                "You cannot POST content of type %s to the SE-IRI" % content_type)

        # If In-Progress is set to false or omitted, try to publish
        in_progress = getHeader(self.request, 'In-Progress', 'false')
        if in_progress == 'false':
            self._handlePublish()
            # We SHOULD return a deposit receipt, status code 200, and the
            # Edit-IRI in the Location header.
            self.request.response.setHeader('Location',
                '%s/sword' % context.absolute_url())
            self.request.response.setStatus(200)

        view = context.unrestrictedTraverse('@@sword')
        return view._handleGet()

    def _handlePublish(self):
        """ Default implementation does nothing, because ATFile has no
            workflow. """
        pass

    def _handlePut(self):
        """ PUT against an existing item should update it.
        """
        obj = self.context
        obj.PUT(self.request, self.request.response)
        obj.setTitle(self.request.get('Title', filename))
        obj.reindexObject(idxs='Title')
        return obj


class PloneFolderSwordAdapter(PloneFolderAtomPubAdapter):
    """ Adapts a context to an ISWORDContentUploadAdapter. An
        ISWORDContentUploadAdapter contains the functionality to 
        create content in a collection. Write your own if you don't want the
        default behaviour, which is very webdav like, it just creates a file
        corresponding to whatever you uploaded. 
        
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
            try:
                context.invokeFactory(typeObjectName, name)
            except ValueError, e:
                raise ContentUnsupported(str(e))
            return context._getOb(name)
        else:
            try:
                return super(PloneFolderSwordAdapter, self).createObject(
                    context, name, content_type, request)
            except ValueError, e:
                raise ContentUnsupported(str(e))

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


class SWORDStatementAdapter(BrowserView):
    __name__ = "statement"

    implements(ISWORDStatement)
    
    statement = ViewPageTemplateFile('statement.pt')


    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method == 'GET':
            return self.statement()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)


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


class SWORDStatementAtomAdapter(BrowserView):
    __name__ = "atom"

    implements(ISWORDStatementAtomAdapter)
    
    atom = ViewPageTemplateFile('atom.pt')


    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method == 'GET':
            return self.atom()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)


class EditMedia(BrowserView):
    __name__ = "editmedia"
    adapts(IATFile, IHTTPRequest)
    
    def __init__(self, context, request):
        super(BrowserView, self).__init__(context, request)
        self.callmap = {'PUT': self.PUT,
                        'GET': self.GET,
                        'POST': self.POST,
                        'DELETE': None,}

    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        call = self.callmap.get(method)
        if call is None:
            raise MethodNotAllowed("Method %s not supported" % method)
        return call()

    def PUT(self):
        context = self.context
        context.PUT(self.request, self.request.response)
        context.setTitle(self.request.get('Title', filename))
        context.reindexObject(idxs='Title')
        return context

    def GET(self):
        data = self.context.getFile().data
        response = self.request.response
        filename = self.context.Title()
        response.setHeader(
                'Content-disposition', 'attachment; filename=%s' %filename)
        response.setHeader('Content-type', 'application/zip')
        response.setHeader("Content-Length", len(data))
        return data

    @show_error_document
    def POST(self):
        # If you post on the EM-IRI, its supposed to add media to the item. But
        # that item could be anything as specified by the content_type_registry,
        # so this might not be supported. The idea here is to upload into
        # anything that is folderish, so that you could in theory have types
        # that know how to create themselves from a request (using the webdav
        # PUT pattern), yet are still folderish and can contain other media.
        # We therefore lookup an upload adapter on the context and request, and
        # do the usual thing, otherwise we raise ContentUnsupported.
        adapter = queryMultiAdapter(
            (aq_inner(self.context), self.request), ISWORDContentUploadAdapter)
        if adapter:
            return adapter()
        raise ContentUnsupported, "Container is not Folderish"

class ListCollection(BrowserView):
    """
    """
    implements(ISWORDListCollection)

    collections_list = ViewPageTemplateFile('collections_list.pt')


    @show_error_document
    def __call__(self):
        method = self.request.get('REQUEST_METHOD')
        if method == 'GET':
            return self._handleGet()
        else:
            raise MethodNotAllowed("Method %s not supported" % method)

    def _handleGet(self):
        """
        """
        view = self.__of__(self.context)
        pt = self.collections_list.__of__(view)
        return pt()

    def getItems(self):
        return self.context.objectValues()
