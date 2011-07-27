from zope.component import getAdapter
from Products.Five import BrowserView

from Products.PloneTestCase import PloneTestCase

PloneTestCase.setupPloneSite()

class TestSwordService(PloneTestCase.PloneTestCase):
    def afterSetup(self):
        pass

    def testSwordService(self):
        import pdb; pdb.set_trace()
        # Check that 'sword' ends up at a browser view
        self.portal.restrictedTraverse('sword')
        assert isinstance(self.portal.restrictedTraverse('sword'),
            BrowserView)

        # Check that we can look up a traversal adapter for ISwordService
        # TODO
