from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName


class SWORDService(BrowserView):
    """SWORD Service for plone   """
    
    def collections(self):
        """Return all folders we have access to as collection targets"""
        pc = getToolByName(self.context, "portal_catalog")
        return pc(portal_type='Folder', allowedRolesAndUsers=['Contributor'])
        
        
        
        
    
