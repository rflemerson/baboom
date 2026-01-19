from django_components import component


@component.register("list.pagination")
class Pagination(component.Component):
    template_name = "pagination.html"

    def get_context_data(self, page_obj, component_request=None, per_page=None):
        return {
            "page_obj": page_obj,
            "component_request": component_request,
            "per_page": per_page,
        }
