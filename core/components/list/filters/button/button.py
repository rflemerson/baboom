from django_components import component


@component.register("list.filters.button")
class FilterButton(component.Component):
    template_name = "button.html"

    def get_context_data(self, filter_obj):
        return {
            "filter": filter_obj,
        }
