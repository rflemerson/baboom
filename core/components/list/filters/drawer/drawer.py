from django_components import component


@component.register("list.filters.drawer")
class FilterDrawer(component.Component):
    template_name = "drawer.html"

    def get_context_data(self, filter_obj, request):
        return {
            "filter": filter_obj,
            "component_request": request,
        }
