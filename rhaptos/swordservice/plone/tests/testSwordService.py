from StringIO import StringIO
from base64 import decodestring
from zope.publisher.interfaces.http import IHTTPRequest
from zope.component import getAdapter, getMultiAdapter
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import Interface, directlyProvides, directlyProvidedBy
from Acquisition import aq_base
from ZPublisher.HTTPRequest import HTTPRequest
from ZPublisher.HTTPResponse import HTTPResponse
from Products.Five import BrowserView

from Products.PloneTestCase import PloneTestCase

from rhaptos.swordservice.plone.browser.sword import ISWORDService

PloneTestCase.setupPloneSite()

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
        assert bool(view.publishTraverse(request, 'service-document')())

        # Upload a zip file
        env = {
            'CONTENT_TYPE': 'application/zip',
            'CONTENT_DISPOSITION': 'attachment; filename=perry.zip',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'nohost',
            'SERVER_PORT': '80'
        }
        uploadresponse = HTTPResponse(stdout=StringIO())
        uploadrequest = clone_request(self.app.REQUEST, uploadresponse, env)
        uploadrequest.set('BODYFILE', StringIO(decodestring(ZIPFILE)))

        # Call the sword view on this request to perform the upload
        self.setRoles(('Manager',))
        xml = getMultiAdapter(
            (self.portal, uploadrequest), Interface, 'sword')()
        assert bool(xml), "Upload view does not return a result"

        # Test that we can still reach the edit-iri
        view = self.portal.restrictedTraverse('perry-zip/sword')
        assert bool(view.publishTraverse(request, 'edit')())

# base64 representation of a small test zip file
ZIPFILE="""\
UEsDBAoAAAAAAOKC/T4AAAAAAAAAAAAAAAACABwAeC9VVAkAA0jCMk5OwjJOdXgLAAEE6AMAAATo
AwAAUEsDBAoAAAAAAOKC/T4AAAAAAAAAAAAAAAAEABwAeC95L1VUCQADSMIyTk7CMk51eAsAAQTo
AwAABOgDAABQSwMECgAAAAAA6IL9PgAAAAAAAAAAAAAAAAYAHAB4L3kvei9VVAkAA1PCMk52wjJO
dXgLAAEE6AMAAAToAwAAUEsDBAoAAAAAAOiC/T4AAAAAAAAAAAAAAAAHABwAeC95L3ovYVVUCQAD
U8IyTlPCMk51eAsAAQToAwAABOgDAABQSwMECgAAAAAA6IL9PgAAAAAAAAAAAAAAAAcAHAB4L3kv
ei9mVVQJAANTwjJOU8IyTnV4CwABBOgDAAAE6AMAAFBLAwQKAAAAAADogv0+AAAAAAAAAAAAAAAA
BwAcAHgveS96L2NVVAkAA1PCMk5TwjJOdXgLAAEE6AMAAAToAwAAUEsDBAoAAAAAAOiC/T4AAAAA
AAAAAAAAAAAHABwAeC95L3ovZFVUCQADU8IyTlPCMk51eAsAAQToAwAABOgDAABQSwMECgAAAAAA
6IL9PgAAAAAAAAAAAAAAAAcAHAB4L3kvei9iVVQJAANTwjJOU8IyTnV4CwABBOgDAAAE6AMAAFBL
AwQKAAAAAADogv0+AAAAAAAAAAAAAAAABwAcAHgveS96L2VVVAkAA1PCMk5TwjJOdXgLAAEE6AMA
AAToAwAAUEsBAh4DCgAAAAAA4oL9PgAAAAAAAAAAAAAAAAIAGAAAAAAAAAAQAO1BAAAAAHgvVVQF
AANIwjJOdXgLAAEE6AMAAAToAwAAUEsBAh4DCgAAAAAA4oL9PgAAAAAAAAAAAAAAAAQAGAAAAAAA
AAAQAO1BPAAAAHgveS9VVAUAA0jCMk51eAsAAQToAwAABOgDAABQSwECHgMKAAAAAADogv0+AAAA
AAAAAAAAAAAABgAYAAAAAAAAABAA7UF6AAAAeC95L3ovVVQFAANTwjJOdXgLAAEE6AMAAAToAwAA
UEsBAh4DCgAAAAAA6IL9PgAAAAAAAAAAAAAAAAcAGAAAAAAAAAAAAKSBugAAAHgveS96L2FVVAUA
A1PCMk51eAsAAQToAwAABOgDAABQSwECHgMKAAAAAADogv0+AAAAAAAAAAAAAAAABwAYAAAAAAAA
AAAApIH7AAAAeC95L3ovZlVUBQADU8IyTnV4CwABBOgDAAAE6AMAAFBLAQIeAwoAAAAAAOiC/T4A
AAAAAAAAAAAAAAAHABgAAAAAAAAAAACkgTwBAAB4L3kvei9jVVQFAANTwjJOdXgLAAEE6AMAAATo
AwAAUEsBAh4DCgAAAAAA6IL9PgAAAAAAAAAAAAAAAAcAGAAAAAAAAAAAAKSBfQEAAHgveS96L2RV
VAUAA1PCMk51eAsAAQToAwAABOgDAABQSwECHgMKAAAAAADogv0+AAAAAAAAAAAAAAAABwAYAAAA
AAAAAAAApIG+AQAAeC95L3ovYlVUBQADU8IyTnV4CwABBOgDAAAE6AMAAFBLAQIeAwoAAAAAAOiC
/T4AAAAAAAAAAAAAAAAHABgAAAAAAAAAAACkgf8BAAB4L3kvei9lVVQFAANTwjJOdXgLAAEE6AMA
AAToAwAAUEsFBgAAAAAJAAkArAIAAEACAAAAAA==\
"""
