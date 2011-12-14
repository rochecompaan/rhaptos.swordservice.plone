import pkg_resources
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class UtilsView(BrowserView):

    VERSION = ""
    GENERATOR_URI = ""
    
    _generator_template = ViewPageTemplateFile('generator.pt')

    def __init__(self, context, request):
        super(UtilsView, self).__init__(context, request)
        name = 'rhaptos.swordservice.plone' 
        dist = pkg_resources.get_distribution(name)
        self.VERSION = dist.version
        self.GENERATOR_URI = name

    def generatorURI(self):
        return self.GENERATOR_URI

    def generatorVersion(self):
        return self.VERSION

    def generatorTag(self, **kw):
        view = self.__of__(self.context)
        pt = self._generator_template.__of__(view)
        return pt(**kw)
