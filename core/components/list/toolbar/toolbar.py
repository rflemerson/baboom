from django_components import component


@component.register("list.toolbar")
class Toolbar(component.Component):
    template_name = "toolbar.html"

    def get_context_data(self, filter_obj, query_params=None):
        params = query_params or {}
        search_values = params.get("search", [])
        return {
            "filter": filter_obj,
            "search": search_values[0] if search_values else "",
        }
