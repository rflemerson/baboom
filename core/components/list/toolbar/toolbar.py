from django_components import component


@component.register("list.toolbar")
class Toolbar(component.Component):
    template_name = "toolbar.html"

    def get_context_data(self, filter_obj, request):
        return {
            "filter": filter_obj,
            "component_request": request,
        }
