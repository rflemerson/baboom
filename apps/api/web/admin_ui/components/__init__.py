"""Reusable django-components package for baboom admin."""

# isort: split

# Shell/layout
from .shell.admin_header.admin_header import AdminHeaderComponent
from .shell.admin_sidenav.admin_sidenav import AdminSidenavComponent
from .shell.breadcrumbs.breadcrumbs import BreadcrumbsComponent

# isort: split

# Dashboard
from .dashboard.app_list.app_list import AppListComponent
from .dashboard.recent_actions.recent_actions import RecentActionsComponent

# isort: split

# Changelist
from .changelist.actions.actions import ActionsComponent
from .changelist.change_list_object_tools.change_list_object_tools import (
    ChangeListObjectToolsComponent,
)
from .changelist.change_list_results.change_list_results import (
    ChangeListResultsComponent,
)
from .changelist.changelist_footer.changelist_footer import (
    ChangelistFooterComponent,
)
from .changelist.date_hierarchy.date_hierarchy import DateHierarchyComponent
from .changelist.empty_results.empty_results import EmptyResultsComponent
from .changelist.errornote.errornote import ErrorNoteComponent
from .changelist.filter.filter import FilterComponent
from .changelist.filter_sidebar.filter_sidebar import FilterSidebarComponent
from .changelist.pagination.pagination import PaginationComponent
from .changelist.search_form.search_form import SearchFormComponent

# isort: split

# Change form
from .changeform.change_form_object_tools.change_form_object_tools import (
    ChangeFormObjectToolsComponent,
)
from .changeform.fieldset.fieldset import FieldsetComponent
from .changeform.prepopulated_fields_js.prepopulated_fields_js import (
    PrepopulatedFieldsJsComponent,
)
from .changeform.submit_line.submit_line import SubmitLineComponent

# isort: split

# Auxiliary pages
from .pages.admin_message.admin_message import AdminMessageComponent
from .pages.admin_rich_message.admin_rich_message import AdminRichMessageComponent
from .pages.object_delete_summary.object_delete_summary import (
    ObjectDeleteSummaryComponent,
)
from .pages.object_history_list.object_history_list import (
    ObjectHistoryListComponent,
)
from .pages.popup_response.popup_response import PopupResponseComponent

__all__ = [
    "ActionsComponent",
    "AdminHeaderComponent",
    "AdminMessageComponent",
    "AdminRichMessageComponent",
    "AdminSidenavComponent",
    "AppListComponent",
    "BreadcrumbsComponent",
    "ChangeFormObjectToolsComponent",
    "ChangeListObjectToolsComponent",
    "ChangeListResultsComponent",
    "ChangelistFooterComponent",
    "DateHierarchyComponent",
    "EmptyResultsComponent",
    "ErrorNoteComponent",
    "FieldsetComponent",
    "FilterComponent",
    "FilterSidebarComponent",
    "ObjectDeleteSummaryComponent",
    "ObjectHistoryListComponent",
    "PaginationComponent",
    "PopupResponseComponent",
    "PrepopulatedFieldsJsComponent",
    "RecentActionsComponent",
    "SearchFormComponent",
    "SubmitLineComponent",
]
