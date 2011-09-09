import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from StringIO import StringIO
from base64 import decodestring
from xml.dom.minidom import parse, parseString

from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import getAdapter, getMultiAdapter
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import Interface, directlyProvides, directlyProvidedBy
from ZPublisher.HTTPRequest import HTTPRequest
from ZPublisher.HTTPResponse import HTTPResponse
from Products.Five import BrowserView

from Products.PloneTestCase import PloneTestCase

from rhaptos.swordservice.plone.browser.sword import ISWORDService, ISWORDEditIRI
from rhaptos.swordservice.plone.browser.sword import ServiceDocument
from rhaptos.swordservice.plone.interfaces import ISWORDStatement

PloneTestCase.setupPloneSite()

DIRNAME = os.path.dirname(__file__)

def clone_request(req, response=None, env=None):
    # Return a clone of the current request object.
    environ = req.environ.copy()
    environ['REQUEST_METHOD'] = 'GET'
    if req._auth:
        environ['HTTP_AUTHORIZATION'] = req._auth
    if env is not None:
        environ.update(env)
    if response is None:
        if req.response is not None:
            response = req.response.__class__()
        else:
            response = None
    clone = req.__class__(None, environ, response, clean=1)
    directlyProvides(clone, *directlyProvidedBy(req))
    return clone

class TestSwordService(PloneTestCase.PloneTestCase):
    def afterSetup(self):
        pass

    def testSwordService(self):
        request = self.portal.REQUEST

        # Check that 'sword' ends up at a browser view
        view = self.portal.restrictedTraverse('sword')
        assert isinstance(view, BrowserView)

        # Test service-document
        view = self.portal.unrestrictedTraverse('sword/servicedocument')
        assert isinstance(view, ServiceDocument)
        assert "<sword:error" not in view()

        # Upload a zip file
        zipfilename = os.path.join(DIRNAME, 'data', 'multipart.txt')
        zipfile = open(zipfilename, 'r')
        env = {
            'CONTENT_TYPE': 'application/zip',
            'CONTENT_LENGTH': os.path.getsize(zipfilename),
            'CONTENT_DISPOSITION': 'attachment; filename=multipart.txt',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80',
            'IN_PROGRESS': 'true',
        }
        uploadresponse = HTTPResponse(stdout=StringIO())
        uploadrequest = clone_request(self.app.REQUEST, uploadresponse, env)
        uploadrequest.set('BODYFILE', zipfile)
        # Fake PARENTS
        uploadrequest.set('PARENTS', [self.folder])

        # Call the sword view on this request to perform the upload
        self.setRoles(('Manager',))
        xml = getMultiAdapter(
            (self.folder, uploadrequest), Interface, 'sword')()
        zipfile.close()
        assert bool(xml), "Upload view does not return a result"
        assert "<sword:error" not in xml, xml

        # Test that we can still reach the edit-iri
        assert self.folder.unrestrictedTraverse('multipart-txt/sword/edit')

        # Test publish
        env = {
            'CONTENT_LENGTH': '0',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80'
        }
        publishresponse = HTTPResponse(stdout=StringIO())
        publishrequest = clone_request(self.app.REQUEST, publishresponse, env)
        publishrequest.set('PARENTS', [self.folder])
        xml = getMultiAdapter(
            (self.folder['multipart-txt'], publishrequest), ISWORDEditIRI)()
        self.assertTrue(bool(xml), "Publish returned nothing")
        self.assertTrue("<sword:error" not in xml, xml)

    def testMultipart(self):
        view = self.portal.restrictedTraverse('sword')
        # Upload a zip file
        body_content = os.path.join(DIRNAME, 'data', 'multipart.txt')
        file = open(body_content, 'r')
        env = {
            'CONTENT_TYPE': 'multipart/related; boundary="===============1338623209=="',
            'SLUG': 'multipart',
            'CONTENT_LENGTH': os.path.getsize(body_content),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80'
        }
        uploadresponse = HTTPResponse(stdout=StringIO())
        uploadrequest = clone_request(self.app.REQUEST, uploadresponse, env)
        uploadrequest.stdin = file
        # Fake PARENTS
        uploadrequest.set('PARENTS', [self.folder])

        # Call the sword view on this request to perform the upload
        self.setRoles(('Manager',))
        adapter = getMultiAdapter(
            (self.folder, uploadrequest), Interface, 'sword')
        xml = adapter()
        file.close()
        self.assertTrue(bool(xml), "Upload view does not return a result")
        self.assertTrue("<sword:error" not in xml, xml)
        self.assertTrue('multipart' in self.folder.objectIds(), "upload failed")

    def testContentRetrieve(self):
        id = self.folder.invokeFactory('Folder', 'workspace')
        workspace = self.folder[id]

        id = workspace.invokeFactory('File', 'content_file')
        content_file = workspace[id]
        zipfilename = os.path.join(DIRNAME, 'data', 'multipart.txt')
        file = open(zipfilename, 'r')
        content_file.setFile(file)
    
        env = {
            'REQUEST_METHOD': 'GET',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80'
        }
        getresponse = HTTPResponse(stdout=StringIO())
        getrequest = clone_request(self.app.REQUEST, getresponse, env)

        self.setRoles(('Manager',))
        adapter = getMultiAdapter(
            (content_file, getrequest), Interface, 'sword')
        zipfile = adapter()
        file.close()

    def testSwordServiceStatement(self):
        self.folder.invokeFactory('Folder', 'workspace')
        xml = os.path.join(DIRNAME, 'data', 'entry.xml')
        file = open(xml, 'rb')
        content = file.read()
        file.close()
        env = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': len(content),
            'CONTENT_TYPE': 'application/atom+xml;type=entry',
            'CONTENT_DISPOSITION': 'attachment; filename=entry.xml',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80'
        }
        uploadresponse = HTTPResponse(stdout=StringIO())
        uploadrequest = clone_request(self.app.REQUEST, uploadresponse, env)
        uploadrequest.set('BODYFILE', StringIO(content))
        uploadrequest.set('PARENTS', [self.folder.workspace])
        adapter = getMultiAdapter(
                (self.folder.workspace, uploadrequest), Interface, 'atompub')
        xml = adapter()
        assert "<sword:error" not in xml, xml

        id = self.folder.workspace.objectIds()[0]
        file = self.folder.workspace[id]
        adapter = getMultiAdapter((file, self.portal.REQUEST), ISWORDStatement)
        xml = adapter()
        assert "<sword:error" not in xml, xml
        dom = parseString(xml)
        returned_statement = dom.toxml()

        obj = self.folder.workspace.objectValues()[0]
        file = open(os.path.join(DIRNAME, 'data', 'entry_statement.xml'), 'r')
        dom = parse(file)
        file.close()
        dates = dom.getElementsByTagName('updated')
        dates[0].firstChild.nodeValue = obj.modified()
        reference_statement = dom.toxml()
        # still lotsa tests to add here.
        #self.assertEqual(returned_statement, reference_statement,
        #    'Result does not match reference doc')


    def test_handlePUT(self):
        self.fail()


    def writecontents(self, contents, filename):
        file = open(os.path.join(DIRNAME, 'data', filename), 'w')
        file.write(contents)
        file.close()


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSwordService))
    return suite
