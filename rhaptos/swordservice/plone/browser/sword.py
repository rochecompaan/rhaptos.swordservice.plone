import zipfile
from cStringIO import StringIO


from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName


class SWORDServiceDocument(BrowserView):
    """ SWORD Service for plone   """
    
    def collections(self):
        """Return all folders we have access to as collection targets"""
        pc = getToolByName(self.context, "portal_catalog")
        return pc(portal_type='Folder', allowedRolesAndUsers=['contributor'])
        
        
        
        
    
class SWORDDeposit(BrowserView):
    """ Handle SWORD deposit """
    
    def __call__(self):
        """  """
        #import pdb; pdb.set_trace()
        
        if self.request.getHeader('content-type') == 'application/zip':
            bodyfile = StringIO(self.request.get('BODY'))
            zf = zipfile.ZipFile(bodyfile)
            
            #import pdb; pdb.set_trace() 
            for filepath in zf.namelist():
                fileobj = zf.read(filepath)
                
            
            
            