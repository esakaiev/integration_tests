# -*- coding: utf-8 -*-
import attr
from navmazing import NavigateToAttribute
from navmazing import NavigateToSibling
from widgetastic.widget import NoSuchElementException
from widgetastic.widget import Text
from widgetastic.widget import View
from widgetastic_patternfly import BreadCrumb
from widgetastic_patternfly import Button
from widgetastic_patternfly import Dropdown

from cfme.base.ui import BaseLoggedInPage
from cfme.common import CustomButtonEventsMixin
from cfme.common import PolicyProfileAssignable
from cfme.common import Taggable
from cfme.common import TagPageView
from cfme.exceptions import ItemNotFound
from cfme.modeling.base import BaseCollection
from cfme.modeling.base import BaseEntity
from cfme.utils.appliance.implementations.ui import CFMENavigateStep
from cfme.utils.appliance.implementations.ui import navigate_to
from cfme.utils.appliance.implementations.ui import navigator
from cfme.utils.providers import get_crud_by_name
from widgetastic_manageiq import Accordion
from widgetastic_manageiq import ManageIQTree
from widgetastic_manageiq import PaginationPane
from widgetastic_manageiq import SummaryTable
from widgetastic_manageiq import Table


class StorageManagerToolbar(View):
    """The toolbar on the Storage Manager or Provider page"""
    configuration = Dropdown('Configuration')
    policy = Dropdown('Policy')


class StorageManagerDetailsToolbar(View):
    """The toolbar on the Storage Manager or Provider detail page"""
    reload = Button(title='Refresh this page')
    configuration = Dropdown('Configuration')
    policy = Dropdown('Policy')
    monitoring = Dropdown('Monitoring')
    download = Button(title='Download summary in PDF format')


class StorageManagerEntities(View):
    """The entities on the main list Storage Manager or Provider page"""
    table = Table(".//div[@id='list_grid' or @class='miq-data-table']/table")


class StorageManagerDetailsEntities(View):
    """The entities on the Storage Manager or Provider details page"""
    breadcrumb = BreadCrumb()
    properties = SummaryTable('Properties')
    relationships = SummaryTable('Relationships')
    smart_management = SummaryTable('Smart Management')
    status = SummaryTable('Status')


class StorageManagerDetailsAccordion(View):
    """The accordion on the Storage Manager or Provider details page"""
    @View.nested
    class properties(Accordion):  # noqa
        tree = ManageIQTree()

    @View.nested
    class relationships(Accordion):  # noqa
        tree = ManageIQTree()


class StorageManagerView(BaseLoggedInPage):
    """A base view for all the Storage Manager or Provider pages"""
    title = Text('.//div[@id="center_div" or @id="main-content"]//h1')

    @property
    def in_manager(self):
        navigation_path = self.context['object'].navigation_path
        return(
            self.logged_in_as_current_user and
            self.navigation.currently_selected == navigation_path)


class StorageManagerAllView(StorageManagerView):
    """The all Storage Manager or Provider page"""
    @property
    def is_displayed(self):
        return (
            self.in_manager and
            self.title.text in ('Storage Managers', self.context['object'].manager_type))

    toolbar = View.nested(StorageManagerToolbar)
    entities = View.nested(StorageManagerEntities)
    paginator = PaginationPane()


class ProviderStorageManagerAllView(StorageManagerAllView):

    @property
    def is_displayed(self):
        return (
            self.logged_in_as_current_user and
            self.navigation.currently_selected == ['Compute', 'Clouds', 'Providers'] and
            self.title.text == '{} (All Storage Managers)'.format(self.context['object'].name)
        )


class StorageManagerDetailsView(StorageManagerView):
    """The details page for Storage Manager or Provider"""
    @property
    def is_displayed(self):
        expected_title = '{} (Summary)'.format(self.context['object'].name)

        return(
            self.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title)

    toolbar = View.nested(StorageManagerDetailsToolbar)
    sidebar = View.nested(StorageManagerDetailsAccordion)
    entities = View.nested(StorageManagerDetailsEntities)


@attr.s
class StorageManager(BaseEntity, CustomButtonEventsMixin, Taggable, PolicyProfileAssignable):
    """ Model of an storage manager in cfme

    Args:
        collection: Instance of collection
        name: Name of the object manager.
        provider: Provider
    """

    name = attr.ib()
    provider = attr.ib()
    storage_title = 'Storage Manager'

    @property
    def navigation_path(self):
        return self.parent.navigation_path

    @property
    def manager_type(self):
        return self.parent.manager_type

    def refresh(self, cancel=False):
        """Refresh storage manager"""
        view = navigate_to(self, 'Details')
        view.toolbar.configuration.item_select('Refresh Relationships and Power States',
                                               handle_alert=not cancel)

        if not cancel:
            view.flash.assert_no_error()

    def delete(self):
        """Delete storage manager"""
        view = navigate_to(self, 'Details')

        if self.appliance.version < '5.9':
            remove_item = 'Remove this {}'.format(self.storage_title)
        else:
            remove_item = 'Remove this {} from Inventory'.format(self.storage_title)
        view.toolbar.configuration.item_select(remove_item, handle_alert=True)

        view = self.create_view(StorageManagerDetailsView)
        view.flash.assert_no_error()


@attr.s
class BlockManagerCollection(BaseCollection):
    """Collection object [block manager] for the :py:class:'cfme.storage.manager'"""
    ENTITY = StorageManager
    manager_type = 'Block Storage Managers'
    navigation_path = ['Storage', 'Block Storage', 'Managers']

    def all(self):
        """returning all block storage manager objects and support filtering as per provider"""
        provider = self.filters.get("provider")
        blocks = ("Cinder Manager", "EBS Storage Manager")
        prov_db = {prov.id: prov for prov in self.appliance.rest_api.collections.providers.all}
        managers = [
            prov for prov in prov_db.values() if any(block in prov.name for block in blocks)
        ]

        if provider:
            return [
                self.instantiate(name=mag.name, provider=provider)
                for mag in managers
                if provider.id == mag.parent_ems_id
            ]
        else:
            return [
                self.instantiate(
                    name=mag.name, provider=get_crud_by_name(prov_db[mag.parent_ems_id].name)
                )
                for mag in managers
            ]


@attr.s
class ObjectManagerCollection(BaseCollection):
    """Collection object [object manager] for the :py:class:'cfme.storage.manager'"""
    ENTITY = StorageManager
    manager_type = 'Object Storage Managers'
    navigation_path = ['Storage', 'Object Storage', 'Managers']

    def all(self):
        """returning all object storage manager objects and support filtering as per provider"""
        provider = self.filters.get("provider")
        prov_db = {prov.id: prov for prov in self.appliance.rest_api.collections.providers.all}
        managers = [
            prov for prov in prov_db.values() if "Swift Manager" in prov.name
        ]

        if provider:
            return [
                self.instantiate(name=mag.name, provider=provider)
                for mag in managers
                if provider.id == mag.parent_ems_id
            ]
        else:
            return [
                self.instantiate(
                    name=mag.name, provider=get_crud_by_name(prov_db[mag.parent_ems_id].name)
                )
                for mag in managers
            ]


@navigator.register(BlockManagerCollection, 'All')
@navigator.register(ObjectManagerCollection, 'All')
class StorageManagerAll(CFMENavigateStep):
    VIEW = StorageManagerAllView
    prerequisite = NavigateToAttribute('appliance.server', 'LoggedIn')

    def step(self, *args, **kwargs):
        self.prerequisite_view.navigation.select(*self.obj.navigation_path)


@navigator.register(StorageManager, 'Details')
class StorageManagerDetails(CFMENavigateStep):
    VIEW = StorageManagerDetailsView
    prerequisite = NavigateToAttribute('parent', 'All')

    def step(self, *args, **kwargs):
        try:
            row = self.prerequisite_view.paginator.find_row_on_pages(
                self.prerequisite_view.entities.table, Name=self.obj.name)
            row.click()
        except NoSuchElementException:
            raise ItemNotFound('Could not locate {}'.format(self.obj.name))


@navigator.register(StorageManager, 'EditTagsFromDetails')
class StorageManagerDetailEditTag(CFMENavigateStep):
    """ This navigation destination help to WidgetasticTaggable"""
    VIEW = TagPageView
    prerequisite = NavigateToSibling('Details')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.policy.item_select('Edit Tags')
