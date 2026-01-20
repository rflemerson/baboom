from django_components import component


@component.register("list.filters")
class Filters(component.Component):
    template_name = "filters.html"

    def get_context_data(self, filter_obj):
        return {
            "filter": filter_obj,
        }
