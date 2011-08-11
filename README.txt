Introduction
============
This package provides a sword namespace for plone. By default it allows you
to upload files to folders, pretty similar to webdav.

Adapters
========
This package uses a lot of adapters and attempts to be very pluggible.

ISWORDContentUploadAdapter
--------------------------
When you upload content to a container, the context and request is adapted to
this interface. The returned object must be callable, and should perform the
required task of creating content within the container.

ISWORDContentAdapter
--------------------
When the Deposit Receipt is requested for an uploaded item we provide a
default deposit receipt that uses the usual attributes common to plone. If
you want to override some of these values, register an adapter that provides
ISWORDContentAdapter, and an information method that returns a dictionary
with the extra values.

ISWORDServiceDocument
---------------------
When the service document is requested for the site, we adapt it to
ISWORDServiceDocument first, then call it. The returned value must be
a publishable object, such as a page template or a browser view. This allows
you to register another browser view to provide this functionality, should
you want to.

ISWORDDepositReceipt
--------------------
When a deposit receipt is requested for an uploaded item, we adapt it to an
ISWORDServiceDocument first. The returned object must be callable and must
return a publishable object, such as a page template or a browser view. You
should probably not have to override this, but you can use zcml to glue this
to your content types. Content types that cannot be adapted to
ISWORDServiceDocument have no edit-iri and no document receipt.


Files of interest
=================
 rhaptos.swordservice.plone/rhaptos/swordservice/plone/browser/sword.py
 rhaptos.atompub.plone/rhaptos/atompub/plone/browser/atompub.py
 rhaptos.atompub.plone/rhaptos/atompub/plone/tests/data/good_atom.xml
 rhaptos.atompub.plone/rhaptos/atompub/plone/tests/test_atompub.py
 raptos.atompub.plone/rhaptos/atompub/plone/browser/atom_entry_document.pt
 rhaptos.atompub.plone/rhaptos/atompub/plone/tests/data/atom_post_expected_result.xml

 Products/Archetypes/Marshall.py
 Products/Archetypes/BaseObject.py
 Products/CMFPlone/PloneTool.py
 Products/CMFDefault/Document.py
 Products/Archetypes/ExtensibleMetadata.py
 Products/CMFDefault/DublinCore.py
